from sqlalchemy.exc import IntegrityError

from app.data.db import (Session, ModeloVeiculo, Veiculo, Pecas, ComposicaoVeiculo,
                         AtividadeVeiculo, ItemEspecial, ResolverMaterial)
from app.data.doc.Calculos import ATIVIDADE_PADRAO

CHASSI_REF = "REF-PDF-0001"
FONTE_PDF = "PDF de referência (hipotético)"          # texto curto: aparece em tabelas e no PDF do QR
FONTES_ANTIGAS = ('PDF "Parte 1 - Modelo hipotético de cálculo da pegada de carbono"',)

MASSA_TOTAL_KG = 1200.0
# Dados hipotéticos do PDF de referência atual (seção 2 = componentes, 3 = composição global, 5 = especiais).
# O PDF NÃO informa a composição de cada componente: só a massa dele e a composição global do veículo.
COMPONENTES_PDF = [          # [("Componente", massa_kg), ...]  -> 24 itens, somam 1.200 kg
    ("Carroceria e painéis estruturais", 390), ("Chassi e subestruturas", 110), ("Motor", 130),
    ("Transmissão", 65), ("Suspensão e direção", 50), ("Sistema de freios", 28), ("Rodas", 28),
    ("Pneus", 40), ("Vidros", 32), ("Bancos", 65), ("Painel e revestimentos internos", 50),
    ("Para-choques e acabamentos", 35), ("Chicote elétrico", 15), ("Módulos eletrônicos", 15),
    ("Bateria 12 V", 15), ("Sistema de escapamento", 16), ("Catalisador", 4),
    ("Arrefecimento/climatização", 30), ("Sistema de combustível", 18),
    ("Airbags/dispositivos de segurança", 10), ("Faróis e lanternas", 8), ("Isolamentos", 10),
    ("Fixadores", 25), ("Fluidos/resíduos", 11),
]
COMPOSICAO_GLOBAL_PDF = [    # [("Material", massa_kg), ...]  -> 1.189 kg sólidos + 11 kg fluidos = 1.200 kg
    ("Aço", 585), ("Ferro fundido", 128), ("Alumínio", 101), ("Cobre", 28), ("Plásticos", 193),
    ("Vidro", 33), ("Borracha", 50), ("Chumbo", 13), ("Outros", 58), ("Fluidos", 11),
]
ITENS_ESPECIAIS_PDF = [      # seção 5: ("Item", quantidade, "unidade", "destino")
    ("Óleo lubrificante", 4.5, "L", "Coleta e tratamento"),
    ("Fluido de arrefecimento", 5.0, "L", "Tratamento"),
    ("Fluido de freio", 1.0, "L", "Tratamento especializado"),
    ("Combustível residual", 0.5, "L", "Recuperação/tratamento"),
    ("Bateria 12 V", 15, "kg", "Reciclagem específica"),
    ("Pneus", 40, "kg", "Rotas específicas"),
    ("Catalisador", 4, "kg", "Recuperação de materiais"),
    ("Componentes eletrônicos", 15, "kg", "Reciclagem especializada"),
]


def _validar(componentes, composicao):
    #Devolve (erros, avisos). Erros impedem o seed.#
    erros, avisos = [], []
    if len(componentes) != 24:
        avisos.append(f"O PDF descreve 24 componentes; a lista tem {len(componentes)}")
    for nome, kg in [*componentes, *composicao]:
        if not str(nome).strip() or kg is None or kg < 0:
            erros.append(f"Item inválido: {nome!r} / {kg!r}")
    soma_c = sum(kg for _, kg in componentes)
    if soma_c > MASSA_TOTAL_KG + 0.01:
        erros.append(f"A soma dos componentes ({soma_c:g} kg) é maior que a massa do veículo ({MASSA_TOTAL_KG:g} kg)")
    soma_m = sum(kg for _, kg in composicao)
    if abs(soma_m - MASSA_TOTAL_KG) > 0.5:
        avisos.append(f"Composição global soma {soma_m:g} kg (veículo: {MASSA_TOTAL_KG:g} kg)")
    return erros, avisos


def _completar_existente(s, v):
    #Bancos criados antes desta versão: acrescenta os itens especiais e encurta o texto da fonte. Idempotente.#
    mudou = False
    if not v.itens_especiais:
        for item, qtd, un, destino in ITENS_ESPECIAIS_PDF:
            s.add(ItemEspecial(veiculo=v, item=item, quantidade=qtd, unidade=un, destino=destino, origem="referencia"))
        mudou = True
    for c in v.composicao_agregada:
        if c.fonte in FONTES_ANTIGAS:
            c.fonte = FONTE_PDF
            mudou = True
    if mudou:
        s.commit()
        print("SeedReferenciaPDF: cenário de referência atualizado (itens especiais / texto da fonte).")


def SeedReferenciaPDF(componentes=None, composicao=None):
    componentes = COMPONENTES_PDF if componentes is None else componentes
    composicao = COMPOSICAO_GLOBAL_PDF if composicao is None else composicao
    with Session() as s:
        existente = s.query(Veiculo).filter_by(Chassi=CHASSI_REF).first()
        if existente:
            _completar_existente(s, existente)
            print("SeedReferenciaPDF: cenário de referência já cadastrado.")
            return None
        if not componentes or not composicao:
            print("SeedReferenciaPDF: dados do PDF pendentes (COMPONENTES_PDF / COMPOSICAO_GLOBAL_PDF vazios); "
                  "nada foi criado.")
            return None
        erros, avisos = _validar(componentes, composicao)
        if erros:
            raise ValueError("Seed de referência inválido: " + "; ".join(erros))
        try:
            modelo = (s.query(ModeloVeiculo).filter_by(veiculo="Referência PDF", Modelo="Compacto Flex (hipotético)").first()
                      or ModeloVeiculo(veiculo="Referência PDF", Modelo="Compacto Flex (hipotético)",
                                       CategoriaVeiculo="Veículo compacto de passeio", MassaTotal=MASSA_TOTAL_KG,
                                       Estado="Fim de vida", VidaUtilAnos=15, Kilometragem=180000))
            v = Veiculo(modelo_base=modelo, veiculo=modelo.veiculo, Modelo=modelo.Modelo, Chassi=CHASSI_REF,
                        CategoriaVeiculo="Veículo compacto de passeio", MassaTotal=MASSA_TOTAL_KG,
                        Estado="Fim de vida", VidaUtilAnos=15, Kilometragem=180000,
                        motorizacao="Combustão interna", combustivel="Flex",
                        fonte_composicao="agregada", origem_dados="referencia_pdf")
            s.add(v)
            for categoria, kg in componentes:
                s.add(Pecas(veiculo=v, Categoria=categoria, Peso=kg, composicao=None, massa_origem="referencia"))
            for nome, kg in composicao:
                mat = ResolverMaterial(s, nome)          # desconhecido entra como 'nao classificado', nunca "Outros"
                if mat.status == "nao classificado":
                    avisos.append(f"material '{nome}' está sem classificação no catálogo: "
                                  f"não entrará no cálculo até receber grupo (pdf demo)")
                s.add(ComposicaoVeiculo(veiculo=v, material_id=mat.id, categoria_texto=nome, massa_kg=kg,
                                        origem="referencia", fonte=FONTE_PDF))
            # atividade gravada explicitamente (valores hipotéticos do PDF), para o cálculo não cair no padrão em silêncio
            s.add(AtividadeVeiculo(veiculo=v, **ATIVIDADE_PADRAO))
            for item, qtd, un, destino in ITENS_ESPECIAIS_PDF:
                s.add(ItemEspecial(veiculo=v, item=item, quantidade=qtd, unidade=un, destino=destino,
                                   origem="referencia"))
            s.commit()
            for a in avisos:
                print(f"SeedReferenciaPDF aviso: {a}")
            print(f"SeedReferenciaPDF: veículo #{v.id} criado ({len(componentes)} componentes, "
                  f"{len(composicao)} materiais, {len(ITENS_ESPECIAIS_PDF)} itens especiais).")
            return v.id
        except IntegrityError:          # dois processos do reloader podem semear ao mesmo tempo
            s.rollback()
            return None
if __name__ == "__main__":
    SeedReferenciaPDF()