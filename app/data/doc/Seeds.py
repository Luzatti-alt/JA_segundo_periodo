from sqlalchemy.exc import IntegrityError

from app.data.db import (Session, ModeloVeiculo, Veiculo, Pecas, ComposicaoVeiculo,
                         AtividadeVeiculo, ResolverMaterial)
from app.data.doc.Calculos import ATIVIDADE_PADRAO

CHASSI_REF = "REF-PDF-0001"
FONTE_PDF = 'PDF "Parte 1 - Modelo hipotético de cálculo da pegada de carbono"'

MASSA_TOTAL_KG = 1200.0
# PREENCHER com os dados do PDF:
COMPONENTES_PDF = []          # [("Categoria do componente", massa_kg), ...]  -> 24 itens
COMPOSICAO_GLOBAL_PDF = []    # [("Material", massa_kg), ...]                 -> composição global do veículo


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


def SeedReferenciaPDF(componentes=None, composicao=None):
    componentes = COMPONENTES_PDF if componentes is None else componentes
    composicao = COMPOSICAO_GLOBAL_PDF if composicao is None else composicao
    with Session() as s:
        if s.query(Veiculo).filter_by(Chassi=CHASSI_REF).first():
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
                mat = ResolverMaterial(s, nome)          # desconhecido entra como 'nao_classificado', nunca "Outros"
                s.add(ComposicaoVeiculo(veiculo=v, material_id=mat.id, categoria_texto=nome, massa_kg=kg,
                                        origem="referencia", fonte=FONTE_PDF))
            # atividade gravada explicitamente (valores hipotéticos do PDF), para o cálculo não cair no padrão em silêncio
            s.add(AtividadeVeiculo(veiculo=v, **ATIVIDADE_PADRAO))
            s.commit()
            for a in avisos:
                print(f"SeedReferenciaPDF aviso: {a}")
            print(f"SeedReferenciaPDF: veículo #{v.id} criado ({len(componentes)} componentes, "
                  f"{len(composicao)} materiais).")
            return v.id
        except IntegrityError:          # dois processos do reloader podem semear ao mesmo tempo
            s.rollback()
            return None
if __name__ == "__main__":
    SeedReferenciaPDF()