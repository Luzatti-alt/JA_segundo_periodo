#region constantes
# Fonte: "Parte 1 - Modelo hipotético de cálculo da pegada de carbono".
# TODOS os valores abaixo são HIPOTÉTICOS (exceto eletricidade e diesel, que o PDF
# cita como referência pública). Servem para demonstrar e testar o modelo.
import unicodedata

GRUPOS = ["Aço", "Ferro fundido", "Alumínio", "Cobre", "Plásticos",
          "Vidro", "Borracha", "Chumbo", "Outros"]   # seção 4 do PDF
FLUIDOS = "Fluidos"                                    # tratado à parte (seção 11.4)

# seção 5: (reciclagem, reuso, valorização, disposição) em % — cada linha fecha 100
DESTINOS_PADRAO = {
    "Aço":           (95, 2, 0, 3),
    "Ferro fundido": (95, 0, 0, 5),
    "Alumínio":      (92, 5, 0, 3),
    "Cobre":         (98, 1, 0, 1),
    "Plásticos":     (65, 10, 10, 15),
    "Vidro":         (90, 2, 0, 8),
    "Borracha":      (50, 10, 30, 10),
    "Chumbo":        (95, 0, 0, 5),
    "Outros":        (30, 5, 25, 40),
}

# seção 8: dados de atividade (por veículo). A massa transportada inicialmente
# é a massa total do veículo.
ATIVIDADE_PADRAO = {
    "transporte_inicial_km": 100.0,
    "energia_kwh": 35.0,
    "diesel_l": 8.0,
    "dist_reciclagem_km": 50.0,
    "dist_reuso_km": 40.0,
    "dist_valorizacao_km": 60.0,
    "dist_disposicao_km": 30.0,
    "dist_fluidos_km": 80.0,
}

_REC = {"Aço": 0.55, "Ferro fundido": 0.60, "Alumínio": 1.20, "Cobre": 1.10,
        "Plásticos": 0.80, "Vidro": 0.45, "Borracha": 0.70, "Chumbo": 0.50, "Outros": 0.50}
# seção 13: (FE material virgem, fator de deslocamento)
_VIRGEM = {"Aço": (2.00, 0.95), "Ferro fundido": (1.80, 0.95), "Alumínio": (8.00, 0.95),
           "Cobre": (4.00, 0.98), "Plásticos": (2.50, 0.80), "Vidro": (1.00, 0.90),
           "Borracha": (1.50, 0.70), "Chumbo": (2.00, 0.95), "Outros": (1.50, 0.50)}

# (chave, valor, unidade, origem) — seção 9
FATORES_PADRAO = (
    [("eletricidade", 0.0457, "kgCO2e/kWh", "Referência pública MCTI/SIN"),
     ("diesel", 2.6702, "kgCO2e/L", "Referência PBGHG"),
     ("transporte", 0.10, "kgCO2e/t.km", "Hipotético"),
     ("disposicao", 0.15, "kgCO2e/kg", "Hipotético"),
     ("tratamento_fluidos", 0.30, "kgCO2e/kg", "Hipotético"),
     # o PDF não define emissão de processo para reuso/valorização (só o transporte);
     # ficam em 0 e podem ser editadas quando houver dado real
     ("reuso", 0.0, "kgCO2e/kg", "Não definido no PDF"),
     ("valorizacao", 0.0, "kgCO2e/kg", "Não definido no PDF")]
    + [("reciclagem:" + g, _REC[g], "kgCO2e/kg", "Hipotético") for g in GRUPOS]
    + [("virgem:" + g, _VIRGEM[g][0], "kgCO2e/kg", "Hipotético") for g in GRUPOS]
    + [("deslocamento:" + g, _VIRGEM[g][1], "fração (0 a 1)", "Hipotético") for g in GRUPOS]
)

# seção 11 / 12 do PDF — resultado esperado do cenário-base (usado nos testes)
RESULTADO_PDF = {"total": 723.69, "reciclagem": 666.41, "diesel": 21.36, "transporte": 17.86,
                 "disposicao": 13.16, "tratamento_fluidos": 3.30, "eletricidade": 1.60,
                 "beneficio": 2418.01}

# cenários (seção 15). O PDF só informa os totais, não as taxas por material, então os
# cenários movem uma fração da reciclagem <-> disposição, calibrada para reproduzir
# a massa reciclada do PDF (854,85 kg e 1.091,92 kg). Ajuste se tiver as taxas reais.
CENARIOS = {
    "baixa": {"nome": "Baixa recuperação", "reciclagem_para_disposicao_pct": 15.16},
    "base":  {"nome": "Base"},
    "alta":  {"nome": "Alta recuperação", "disposicao_para_reciclagem_pct": 96.13},
}

# seção 6: itens que não são sucata convencional ("lista de atenção")
ITENS_ATENCAO = [
    (("bateria",), "Reciclagem específica"),
    (("pneu",), "Rotas específicas"),
    (("catalisador",), "Recuperação de materiais"),
    (("eletron", "modulo", "chicote"), "Reciclagem especializada"),
    (("oleo", "arrefecimento", "freio", "combustivel", "fluido", "liquido"), "Coleta e tratamento"),
]
#endregion constantes


#region classificacao
def _norm(txt):
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return t.lower().strip()

_ALIAS = {
    "aco": "Aço", "ferro fundido": "Ferro fundido", "ferro": "Ferro fundido",
    "aluminio": "Alumínio", "cobre": "Cobre", "plastico": "Plásticos", "plasticos": "Plásticos",
    "vidro": "Vidro", "borracha": "Borracha", "chumbo": "Chumbo", "outros": "Outros",
}

def GrupoMaterial(categoria):
    """Converte o texto livre de Materiais.Categoria em um dos grupos do PDF."""
    n = _norm(categoria)
    if n in _ALIAS:
        return _ALIAS[n]
    if any(p in n for p in ("fluido", "liquido", "oleo", "combustivel")):
        return FLUIDOS
    return "Outros"

def ItemAtencao(categoria):
    n = _norm(categoria)
    for palavras, destino in ITENS_ATENCAO:
        if any(p in n for p in palavras):
            return destino
    return None
#endregion classificacao


#region motor
def calcular(massa_total_kg, materiais_kg, fluidos_kg, atividade, destinos, fatores):
    """Equação fundamental do PDF: E = AD x FE. Função pura (não toca no banco).

    materiais_kg: {grupo: kg}      destinos: {grupo: (rec, reuso, valor, disp)} em %
    atividade: dict como ATIVIDADE_PADRAO      fatores: {chave: valor}
    """
    fe = lambda k: float(fatores.get(k) or 0.0)
    avisos = []
    f_tr = fe("transporte")
    massa_total_kg = float(massa_total_kg or 0.0)

    massa_dest = {"reciclagem": 0.0, "reuso": 0.0, "valorizacao": 0.0, "disposicao": 0.0}
    reciclagem, beneficio = [], []
    for g in GRUPOS:
        kg = float(materiais_kg.get(g, 0.0))
        r, u, v, d = destinos.get(g, DESTINOS_PADRAO[g])
        if abs(r + u + v + d - 100) > 0.01:
            avisos.append(f"Destinos de {g} somam {r + u + v + d:g}% (deveria fechar 100%)")
        kr, ku, kv, kd = kg * r / 100, kg * u / 100, kg * v / 100, kg * d / 100
        massa_dest["reciclagem"] += kr
        massa_dest["reuso"] += ku
        massa_dest["valorizacao"] += kv
        massa_dest["disposicao"] += kd
        reciclagem.append({"material": g, "massa_kg": kg, "massa_reciclada_kg": kr,
                           "fe": fe("reciclagem:" + g), "kg_co2e": kr * fe("reciclagem:" + g)})
        beneficio.append({"material": g, "massa_reciclada_kg": kr, "fe_virgem": fe("virgem:" + g),
                          "fd": fe("deslocamento:" + g),
                          "kg_co2e": kr * fe("virgem:" + g) * fe("deslocamento:" + g)})

    massa_solidos = sum(float(materiais_kg.get(g, 0.0)) for g in GRUPOS)
    fluidos_kg = float(fluidos_kg or 0.0)

    # 11.1 transporte: massa (t) x distância (km) x fator
    t = lambda kg: kg / 1000.0
    transporte_itens = [
        ("Transporte inicial", t(massa_total_kg) * atividade["transporte_inicial_km"] * f_tr),
        ("Até recicladores", t(massa_dest["reciclagem"]) * atividade["dist_reciclagem_km"] * f_tr),
        ("Para reuso", t(massa_dest["reuso"]) * atividade["dist_reuso_km"] * f_tr),
        ("Para valorização", t(massa_dest["valorizacao"]) * atividade["dist_valorizacao_km"] * f_tr),
        ("Para disposição", t(massa_dest["disposicao"]) * atividade["dist_disposicao_km"] * f_tr),
        ("Tratamento dos fluidos", t(fluidos_kg) * atividade["dist_fluidos_km"] * f_tr),
    ]
    e_transporte = sum(v for _, v in transporte_itens)
    e_eletricidade = atividade["energia_kwh"] * fe("eletricidade")      # 11.2
    e_diesel = atividade["diesel_l"] * fe("diesel")                      # 11.3
    e_fluidos = fluidos_kg * fe("tratamento_fluidos")                    # 11.4
    e_disposicao = massa_dest["disposicao"] * fe("disposicao")           # 11.5
    e_reciclagem = sum(x["kg_co2e"] for x in reciclagem)                 # 11.6
    e_reuso = massa_dest["reuso"] * fe("reuso")
    e_valorizacao = massa_dest["valorizacao"] * fe("valorizacao")

    etapas = [("Reciclagem", e_reciclagem), ("Diesel", e_diesel), ("Transporte", e_transporte),
              ("Disposição", e_disposicao), ("Tratamento de fluidos", e_fluidos),
              ("Eletricidade", e_eletricidade)]
    if e_reuso:
        etapas.append(("Reuso", e_reuso))
    if e_valorizacao:
        etapas.append(("Valorização", e_valorizacao))
    total = sum(v for _, v in etapas)
    evitada = sum(x["kg_co2e"] for x in beneficio)

    if massa_total_kg and abs(massa_solidos + fluidos_kg - massa_total_kg) > 0.5:
        avisos.append(f"Conferência de massa: materiais ({massa_solidos:.2f} kg) + fluidos "
                      f"({fluidos_kg:.2f} kg) ≠ massa total ({massa_total_kg:.2f} kg)")
    r2 = lambda x: round(x, 2)
    pct = lambda x, base: r2(x / base * 100) if base else 0.0
    return {
        "massas": {"total_kg": r2(massa_total_kg), "solidos_kg": r2(massa_solidos),
                   "fluidos_kg": r2(fluidos_kg),
                   "nao_catalogada_kg": r2(max(massa_total_kg - massa_solidos - fluidos_kg, 0.0))},
        "destinos": {k: {"massa_kg": r2(v), "participacao_pct": pct(v, massa_solidos)}
                     for k, v in massa_dest.items()},
        "etapas": [{"etapa": n, "kg_co2e": r2(v), "participacao_pct": pct(v, total)} for n, v in etapas],
        "transporte_detalhe": [{"trecho": n, "kg_co2e": r2(v)} for n, v in transporte_itens],
        "reciclagem_por_material": [{**x, "massa_kg": r2(x["massa_kg"]),
                                     "massa_reciclada_kg": r2(x["massa_reciclada_kg"]),
                                     "kg_co2e": r2(x["kg_co2e"])} for x in reciclagem],
        "beneficio_por_material": [{**x, "massa_reciclada_kg": r2(x["massa_reciclada_kg"]),
                                    "kg_co2e": r2(x["kg_co2e"])} for x in beneficio],
        "total_kg_co2e": r2(total),
        # seção 13/14: indicador comparativo, NÃO é carbono removido nem "pegada negativa"
        "beneficio_potencial_kg_co2e": r2(evitada),
        "saldo_comparativo_kg_co2e": r2(total - evitada),
        "avisos": avisos,
    }


def variar_destinos(destinos, reciclagem_para_disposicao_pct=0.0, disposicao_para_reciclagem_pct=0.0):
    """Move uma fração (relativa) entre reciclagem e disposição, em todos os materiais."""
    novo = {}
    for g, (r, u, v, d) in destinos.items():
        a = r * reciclagem_para_disposicao_pct / 100
        b = d * disposicao_para_reciclagem_pct / 100
        novo[g] = (r - a + b, u, v, d + a - b)
    return novo


def cenarios(massa_total_kg, materiais_kg, fluidos_kg, atividade, destinos, fatores):
    """Seção 15: compara baixa / base / alta recuperação."""
    saida = []
    for chave, cfg in CENARIOS.items():
        dest = variar_destinos(destinos, cfg.get("reciclagem_para_disposicao_pct", 0.0),
                               cfg.get("disposicao_para_reciclagem_pct", 0.0))
        r = calcular(massa_total_kg, materiais_kg, fluidos_kg, atividade, dest, fatores)
        saida.append({
            "cenario": chave, "nome": cfg["nome"],
            "massa_reciclada_kg": r["destinos"]["reciclagem"]["massa_kg"],
            "taxa_reciclagem_pct": r["destinos"]["reciclagem"]["participacao_pct"],
            "massa_disposta_kg": r["destinos"]["disposicao"]["massa_kg"],
            "emissao_bruta_kg_co2e": r["total_kg_co2e"],
            "beneficio_potencial_kg_co2e": r["beneficio_potencial_kg_co2e"],
            "saldo_comparativo_kg_co2e": r["saldo_comparativo_kg_co2e"],
        })
    return saida


# seção 16: variável -> (variação inferior, variação superior). Valores calibrados para
# reproduzir a tabela do PDF (FE ±20%, distâncias ±50%, eletricidade ±50%).
SENSIBILIDADE = [
    ("Taxa de reciclagem",       {"rec_disp": 11.9}, {"disp_rec": 95.9}),
    ("FE reciclagem do aço",     {"fe": ("reciclagem:Aço", 0.8)}, {"fe": ("reciclagem:Aço", 1.2)}),
    ("FE reciclagem do alumínio", {"fe": ("reciclagem:Alumínio", 0.8)}, {"fe": ("reciclagem:Alumínio", 1.2)}),
    ("Distâncias",               {"dist": 0.5}, {"dist": 1.5}),
    ("Consumo de eletricidade",  {"energia": 0.5}, {"energia": 1.5}),
]

def _aplicar(var, atividade, destinos, fatores):
    atv, dst, fat = dict(atividade), destinos, dict(fatores)
    if "rec_disp" in var:
        dst = variar_destinos(destinos, reciclagem_para_disposicao_pct=var["rec_disp"])
    if "disp_rec" in var:
        dst = variar_destinos(destinos, disposicao_para_reciclagem_pct=var["disp_rec"])
    if "fe" in var:
        chave, mult = var["fe"]
        fat[chave] = fat.get(chave, 0.0) * mult
    if "dist" in var:
        for k in atv:
            if k.endswith("_km"):
                atv[k] *= var["dist"]
    if "energia" in var:
        atv["energia_kwh"] *= var["energia"]
    return atv, dst, fat


def sensibilidade(massa_total_kg, materiais_kg, fluidos_kg, atividade, destinos, fatores):
    base = calcular(massa_total_kg, materiais_kg, fluidos_kg, atividade, destinos, fatores)["total_kg_co2e"]
    saida = []
    for nome, inf, sup in SENSIBILIDADE:
        vals = []
        for var in (inf, sup):
            a, d, f = _aplicar(var, atividade, destinos, fatores)
            vals.append(calcular(massa_total_kg, materiais_kg, fluidos_kg, a, d, f)["total_kg_co2e"])
        saida.append({"variavel": nome, "inferior": vals[0], "base": base, "superior": vals[1],
                      "amplitude": round(abs(vals[1] - vals[0]), 2)})
    return sorted(saida, key=lambda x: -x["amplitude"])
#endregion motor


#region banco
class Calculo:
    """Cola entre o banco e o motor, no mesmo estilo de classe estática do GerarDados.py."""

    @staticmethod
    def Parametros(s):
        from app.data.db import FatorEmissao, DestinoMaterial
        fatores = {f.chave: f.valor for f in s.query(FatorEmissao).all()}
        destinos = {d.material: (d.reciclagem, d.reuso, d.valorizacao, d.disposicao)
                    for d in s.query(DestinoMaterial).all()}
        for g in GRUPOS:                       # banco incompleto: cai no padrão do PDF
            destinos.setdefault(g, DESTINOS_PADRAO[g])
        for chave, valor, _, _ in FATORES_PADRAO:
            fatores.setdefault(chave, valor)
        return fatores, destinos

    @staticmethod
    def Atividade(s, veiculo_id):
        from app.data.db import AtividadeVeiculo
        a = s.query(AtividadeVeiculo).filter(AtividadeVeiculo.veiculo_id == veiculo_id).first()
        if a is None:
            return dict(ATIVIDADE_PADRAO), True
        return {k: (getattr(a, k) if getattr(a, k) is not None else v)
                for k, v in ATIVIDADE_PADRAO.items()}, False

    @staticmethod
    def Entradas(s, v):
        """Soma Materiais.Peso do veículo por grupo do PDF."""
        materiais, fluidos, avisos, atencao, em_outros = {}, 0.0, [], [], set()
        for p in v.pecas:
            destino = ItemAtencao(p.Categoria)
            if destino:
                atencao.append({"peca_id": p.id, "categoria": p.Categoria,
                                "peso_kg": p.Peso, "destino": destino})
            if not p.materiais:
                avisos.append(f"Peça #{p.id} ({p.Categoria}) não tem materiais cadastrados")
            soma = sum((m.Peso or 0.0) for m in p.materiais)
            if p.Peso and soma > p.Peso + 0.01:
                avisos.append(f"Peça #{p.id} ({p.Categoria}): materiais ({soma:g} kg) "
                              f"maiores que a peça ({p.Peso:g} kg)")
            for m in p.materiais:
                g = GrupoMaterial(m.Categoria)
                if g == FLUIDOS:
                    fluidos += m.Peso or 0.0
                else:
                    materiais[g] = materiais.get(g, 0.0) + (m.Peso or 0.0)
                    if g == "Outros" and _norm(m.Categoria) != "outros":
                        em_outros.add(m.Categoria)
        if em_outros:
            avisos.append("Materiais tratados como 'Outros' (sem grupo próprio no PDF): "
                          + ", ".join(sorted(em_outros)))
        return materiais, fluidos, avisos, atencao

    @staticmethod
    def Veiculo(s, veiculo_id, parte="resumo"):
        from app.data.db import Veiculo
        v = s.get(Veiculo, veiculo_id)
        if v is None:
            return None
        fatores, destinos = Calculo.Parametros(s)
        atividade, padrao = Calculo.Atividade(s, veiculo_id)
        materiais, fluidos, avisos, atencao = Calculo.Entradas(s, v)
        args = (v.MassaTotal or 0.0, materiais, fluidos, atividade, destinos, fatores)
        if parte == "cenarios":
            return cenarios(*args)
        if parte == "sensibilidade":
            return sensibilidade(*args)
        r = calcular(*args)
        r["avisos"] = avisos + r["avisos"]
        if padrao:
            r["avisos"].append("Dados de atividade não cadastrados para este veículo: "
                               "usando os valores hipotéticos do PDF")
        if not materiais and not fluidos:
            r["avisos"].append("Veículo sem materiais cadastrados: o resultado só reflete "
                               "transporte inicial, diesel e eletricidade")
        r["veiculo"] = {"id": v.id, "veiculo": v.veiculo, "modelo": v.Modelo,
                        "chassi": v.Chassi, "massa_total_kg": v.MassaTotal}
        r["atividade"] = atividade
        r["lista_de_atencao"] = atencao
        r["unidade_funcional"] = "kgCO2e por veículo"
        return r
#endregion banco