import copy
import uuid

from app.data.db import (CatalogoMaterial, ComposicaoVeiculo, Pecas, ResolverMaterial)

TOL_KG = 0.01                      # tolerância nas comparações de massa
STATUS_ITEM = ("identificado", "nao_identificado")
ORIGENS_MASSA = ("referencia", "medido", "estimado", "fornecedor", "nao informado")   # igual ao default do banco e aos <option> dos formulários
FONTES_COMPOSICAO = ("por_peca", "agregada")


def NovoUid():
    return uuid.uuid4().hex

def _num(v):
    #float ou None (vazio). ValueError se não for número.
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise ValueError("booleano não é número")
    return float(v)

def _r2(x):
    return None if x is None else round(x, 2)


#region validacao
def NormalizarComposicao(s, composicao, massa_peca=None, criar_catalogo=True):
    if composicao is None:
        return None, [], []
    if not isinstance(composicao, list):
        return None, ["composicao deve ser uma lista de itens"], []

    erros, alertas, itens, uids = [], [], [], set()
    for n, bruto in enumerate(composicao, 1):
        rot = f"Item {n}"
        if not isinstance(bruto, dict):
            erros.append(f"{rot}: deve ser um objeto")
            continue
        item = dict(bruto)

        try:
            massa = _num(item.get("massa_kg"))
        except (TypeError, ValueError):
            erros.append(f"{rot}: massa_kg inválida")
            continue
        if massa is None:
            erros.append(f"{rot}: informe massa_kg")
            continue
        if massa < 0:
            erros.append(f"{rot}: massa_kg negativa ({massa:g})")
            continue

        mat, texto = None, (item.get("categoria") or "").strip()
        if item.get("material_id") is not None:
            mat = s.get(CatalogoMaterial, item["material_id"])
            if mat is None:
                erros.append(f"{rot}: material_id {item['material_id']} não existe no catálogo")
                continue
        elif texto:
            mat = ResolverMaterial(s, texto, criar=False)
            if mat is None:
                if not criar_catalogo:
                    erros.append(f"{rot}: material '{texto}' não existe no catálogo")
                    continue
                mat = ResolverMaterial(s, texto)
                alertas.append(f"{rot}: '{texto}' não existia no catálogo; criado como não classificado")

        status = item.get("status") or ("identificado" if mat else "nao_identificado")
        if status not in STATUS_ITEM:
            erros.append(f"{rot}: status deve ser um de {', '.join(STATUS_ITEM)}")
            continue
        if status == "identificado" and mat is None:
            erros.append(f"{rot}: item identificado precisa de categoria ou material_id")
            continue
        if status == "nao_identificado" and mat is not None:
            erros.append(f"{rot}: item nao_identificado não pode ter material")
            continue

        uid = item.get("item_uid") or NovoUid()
        if uid in uids:
            erros.append(f"{rot}: item_uid repetido ({uid})")
            continue
        uids.add(uid)

        resto = {k: v for k, v in item.items()
                 if k not in ("item_uid", "material_id", "categoria", "massa_kg", "status")}
        if mat is not None and texto and texto != mat.nome and "categoria_original" not in resto:
            resto["categoria_original"] = texto
        resto.setdefault("origem", "nao_informado")
        itens.append({"item_uid": uid, "material_id": mat.id if mat else None,
                      "categoria": mat.nome if mat else None, "massa_kg": massa,
                      "status": status, **resto})
        if status == "nao_identificado":
            alertas.append(f"{rot}: {massa:g} kg sem identificação")
        elif mat.status == "nao_classificado":
            alertas.append(f"{rot}: material '{mat.nome}' ainda sem classificação")

    if massa_peca is None:
        alertas.append("Peça sem massa informada: não dá para conferir a composição")
    else:
        soma = sum(i["massa_kg"] for i in itens)
        for i in itens:
            if i["massa_kg"] > massa_peca + TOL_KG:
                erros.append(f"Material '{i['categoria'] or 'não identificado'}' ({i['massa_kg']:g} kg) "
                             f"é maior que a peça ({massa_peca:g} kg)")
        if soma > massa_peca + TOL_KG:
            erros.append(f"A soma dos materiais ({soma:g} kg) é maior que a peça ({massa_peca:g} kg)")
        elif soma < massa_peca - TOL_KG:
            alertas.append(f"Composição parcial: {massa_peca - soma:.2f} kg da peça sem composição cadastrada")
    return itens, erros, alertas
#endregion validacao


#region indicadores
def StatusCatalogo(s):
    #{material_id: (nome, status)} para consultar sem uma query por item.
    return {m.id: (m.nome, m.status) for m in s.query(CatalogoMaterial).all()}

def IndicadoresComposicao(composicao, massa_peca, catalogo=None):
    catalogo = catalogo or {}
    alertas, identificada, itens_nao_id, nao_classificados, negativa = [], 0.0, 0, set(), False
    lista = composicao if isinstance(composicao, list) else []
    for i in lista:
        try:
            massa = _num(i.get("massa_kg")) or 0.0
        except (AttributeError, TypeError, ValueError):
            alertas.append("Item de composição ilegível")
            continue
        if massa < 0:
            negativa = True
            alertas.append(f"Massa negativa na composição ({massa:g} kg)")
            continue
        if i.get("status") == "identificado" and i.get("material_id") is not None:
            identificada += massa
            nome, status = catalogo.get(i["material_id"], (i.get("categoria"), None))
            if status == "nao_classificado":
                nao_classificados.add(nome)
        elif i.get("status") == "identificado":
            identificada += massa
        else:
            itens_nao_id += 1
    for nome in sorted(n for n in nao_classificados if n):
        alertas.append(f"Material '{nome}' sem classificação")
    if itens_nao_id:
        alertas.append(f"{itens_nao_id} item(ns) declarado(s) como não identificado(s)")

    base = {"massa_kg": massa_peca, "itens": len(lista),
            "itens_nao_identificados": itens_nao_id,
            "materiais_nao_classificados": sorted(n for n in nao_classificados if n)}
    if massa_peca is None:
        return {**base, "estado": "sem_massa", "massa_identificada_kg": _r2(identificada),
                "massa_nao_identificada_kg": None, "cobertura_pct": None,
                "alertas": alertas + ["Peça sem massa informada"]}
    if composicao is None or not lista:
        return {**base, "estado": "sem_composicao", "massa_identificada_kg": 0.0,
                "massa_nao_identificada_kg": _r2(massa_peca), "cobertura_pct": 0.0,
                "alertas": alertas + ["Composição não informada"]}
    if negativa or identificada > massa_peca + TOL_KG:
        if identificada > massa_peca + TOL_KG:
            alertas.append(f"Materiais ({identificada:g} kg) maiores que a peça ({massa_peca:g} kg)")
        estado = "inconsistente"
    elif abs(massa_peca - identificada) <= TOL_KG and not itens_nao_id:
        estado = "completa"
    else:
        estado = "parcial"
    cobertura = _r2(identificada / massa_peca * 100) if massa_peca > 0 else None
    return {**base, "estado": estado, "massa_identificada_kg": _r2(identificada),
            "massa_nao_identificada_kg": _r2(max(0.0, massa_peca - identificada)),
            "cobertura_pct": cobertura, "alertas": alertas}

def IndicadoresPeca(p, catalogo=None):
    return IndicadoresComposicao(p.composicao, p.Peso, catalogo)

def IndicadoresVeiculo(s, v):
    #Cobertura do veículo. Usa UMA fonte de composição (v.fonte_composicao), nunca as duas.
    catalogo = StatusCatalogo(s)
    pecas = [p for p in v.pecas if p.removido_em is None]
    fonte = v.fonte_composicao or "por_peca"
    total = v.MassaTotal
    alertas, motivos = [], []

    por_peca = [{"peca_id": p.id, "categoria": p.Categoria, **IndicadoresPeca(p, catalogo)} for p in pecas]
    sem_massa = [p.id for p in pecas if p.Peso is None]
    soma_pecas = sum(p.Peso or 0.0 for p in pecas)

    if fonte == "por_peca":
        identificada = sum(x["massa_identificada_kg"] or 0.0 for x in por_peca)
        nao_class = sorted({n for x in por_peca for n in x["materiais_nao_classificados"]})
        for estado, texto in (("sem_composicao", "sem composição"), ("parcial", "com composição parcial"),
                              ("inconsistente", "com composição inconsistente"), ("sem_massa", "sem massa")):
            ids = [x["peca_id"] for x in por_peca if x["estado"] == estado]
            if ids:
                motivos.append(f"{len(ids)} peça(s) {texto}")
    else:
        itens = s.query(ComposicaoVeiculo).filter(ComposicaoVeiculo.veiculo_id == v.id).all()
        identificada = sum(i.massa_kg or 0.0 for i in itens if i.material_id or i.categoria_texto)
        nao_class = sorted({catalogo[i.material_id][0] for i in itens
                            if i.material_id in catalogo and catalogo[i.material_id][1] == "nao_classificado"})
        if not itens:
            motivos.append("Composição agregada não cadastrada")
        if any(p.composicao is not None for p in pecas):
            alertas.append("Existe composição por peça, mas a fonte do veículo é 'agregada': "
                           "a composição por peça foi ignorada para não contar a massa duas vezes")
    if nao_class:
        motivos.append(f"Materiais sem classificação: {', '.join(nao_class)}")

    nao_inventariada = None
    if total is None:
        motivos.append("Veículo sem massa total")
    else:
        if soma_pecas > total + TOL_KG:
            alertas.append(f"A soma das peças ({soma_pecas:g} kg) é maior que a massa total ({total:g} kg)")
            motivos.append("Soma das peças maior que a massa total")
        nao_inventariada = _r2(max(0.0, total - soma_pecas))
        if nao_inventariada and nao_inventariada > TOL_KG:
            motivos.append(f"{nao_inventariada:g} kg do veículo fora do inventário de peças")
    if sem_massa:
        alertas.append(f"Peça(s) sem massa: {', '.join('#' + str(i) for i in sem_massa)}")

    cobertura = _r2(identificada / total * 100) if total else None
    cobertura_inv = _r2(identificada / soma_pecas * 100) if fonte == "por_peca" and soma_pecas > 0 else None
    if cobertura is not None and cobertura < 100 - 1e-9 and total and (total - identificada) > TOL_KG:
        motivos.append(f"{max(0.0, total - identificada):.2f} kg do veículo sem identificação")
    integral = not motivos and cobertura is not None and abs(total - identificada) <= TOL_KG
    return {"veiculo_id": v.id, "fonte_composicao": fonte, "massa_total_kg": total,
            "soma_pecas_kg": _r2(soma_pecas), "massa_nao_inventariada_kg": nao_inventariada,
            "massa_identificada_kg": _r2(identificada),
            "massa_nao_identificada_kg": _r2(max(0.0, total - identificada)) if total is not None else None,
            "cobertura_pct": cobertura, "cobertura_inventariada_pct": cobertura_inv,
            "pecas_total": len(pecas),
            "pecas_sem_composicao": sum(1 for x in por_peca if x["estado"] == "sem_composicao"),
            "pecas_parciais": sum(1 for x in por_peca if x["estado"] == "parcial"),
            "materiais_nao_classificados": nao_class,
            "resultado_integral": bool(integral), "motivos_parcial": motivos,
            "alertas": alertas, "pecas": por_peca}
#endregion indicadores


#region sincronizacao
def SincronizarLote(s, material, remover=False, peca_anterior=None):
    uid = material.item_uid = material.item_uid or NovoUid()
    if peca_anterior is not None and peca_anterior is not material.pecas:
        resto = [i for i in (peca_anterior.composicao or []) if i.get("item_uid") != uid]
        peca_anterior.composicao = resto or None
    p = material.pecas
    atual = [dict(i) for i in (p.composicao or [])]
    existente = next((i for i in atual if i.get("item_uid") == uid), {})
    atual = [i for i in atual if i.get("item_uid") != uid]
    if not remover:
        mat = ResolverMaterial(s, material.Categoria)
        atual.append({**existente, "item_uid": uid, "material_id": mat.id if mat else None,
                      "categoria": mat.nome if mat else None, "massa_kg": material.Peso,
                      "status": "identificado" if mat else "nao_identificado",
                      "origem": existente.get("origem", "lote_cadastrado")})
    itens, erros, alertas = NormalizarComposicao(s, atual, p.Peso)
    if not erros:
        p.composicao = itens or None
    return erros, alertas

def ReconciliarLotes(s, peca, itens):
    por_uid = {i["item_uid"]: i for i in (itens or [])}
    erros = []
    for m in peca.materiais:
        if not m.item_uid:
            continue
        i = por_uid.get(m.item_uid)
        if i is None:
            erros.append(f"O lote #{m.id} ({m.Categoria}) não está mais na composição: mantenha o item "
                         f"{m.item_uid} ou remova o lote antes (DELETE /Materiais/{m.id})")
        else:
            m.Peso = i["massa_kg"]
            if i.get("categoria"):
                m.Categoria = i["categoria"]
    return erros

def CopiarInventarioModelo(s, modelo, veiculo):
    n = 0
    for c in modelo.componentes_ref:
        comp = None
        if c.composicao_ref is not None:
            comp = copy.deepcopy(c.composicao_ref)
            for i in comp:
                i["item_uid"] = NovoUid()
                i["origem"] = "referencia"
        s.add(Pecas(veiculo=veiculo, Categoria=c.categoria, Peso=c.massa_ref_kg, composicao=comp,
                    massa_origem="referencia", codigo_peca=c.codigo_peca, fornecedor=c.fornecedor,
                    modelo_componente_id=c.id))
        n += 1
    return n
#endregion sincronizacao