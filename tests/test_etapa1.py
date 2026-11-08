import json
from datetime import datetime, timedelta

import pytest

from app.data.db import Session, Veiculo, Pecas, Materiais, QRFiles, ModeloVeiculo, ModeloComponente, ComposicaoVeiculo
from app.data.doc import GerarDados, Seeds
from app.data.doc.GerarDados import QR, PDF

n = iter(range(1000))
def chassi(): return f"TST{next(n):05d}"

def novo_veiculo(c, massa=100.0, **extra):
    r = c.post("/Veiculo", json={"veiculo": "T", "modelo": "T", "chassi": chassi(), "massa_total_kg": massa, **extra})
    assert r.status_code == 201, r.json
    return r.json["id"]


# ---------- cálculo lê a composição JSON ----------
def test_calculo_usa_composicao_json(mundo):
    c = mundo
    vid = novo_veiculo(c, 100)
    r = c.post("/Componentes", json={"veiculo_id": vid, "categoria": "Carroceria", "peso_kg": 100,
                                     "composicao": [{"categoria": "Aço", "massa_kg": 80, "status": "identificado"},
                                                    {"categoria": "Alumínio", "massa_kg": 20, "status": "identificado"}]})
    assert r.status_code == 201, r.json
    calc = c.get(f"/Calculos/{vid}").json
    mats = {m["material"]: m["massa_kg"] for m in calc["reciclagem_por_material"]}
    assert mats["Aço"] == 80 and mats["Alumínio"] == 20
    assert calc["resultado_integral"] is True
    assert calc["qualidade"]["cobertura_pct"] == 100

def test_editar_json_muda_o_calculo(mundo):
    c = mundo
    vid = novo_veiculo(c, 100)
    pid = c.post("/Componentes", json={"veiculo_id": vid, "categoria": "X", "peso_kg": 100,
                                       "composicao": [{"categoria": "Aço", "massa_kg": 100}]}).json["id"]
    a = c.get(f"/Calculos/{vid}").json["total_kg_co2e"]
    assert c.put(f"/Componentes/{pid}", json={"composicao": [{"categoria": "Alumínio", "massa_kg": 100}]}).status_code == 200
    assert c.get(f"/Calculos/{vid}").json["total_kg_co2e"] != a

def test_material_desconhecido_nao_vira_outros_e_resultado_e_parcial(mundo):
    c = mundo
    leaf = next(v for v in c.get("/Veiculo").json if v["modelo"] == "Leaf")["id"]
    calc = c.get(f"/Calculos/{leaf}").json
    mats = {m["material"]: m["massa_kg"] for m in calc["reciclagem_por_material"]}
    assert mats["Outros"] == 0                       # Lítio/Cobalto/Níquel NÃO foram para "Outros"
    assert calc["resultado_integral"] is False
    assert calc["avisos"][0].startswith("RESULTADO PARCIAL")
    txt = " ".join(calc["avisos"])
    assert "Lítio" in txt and "NÃO entrou no cálculo" in txt
    assert calc["qualidade"]["massa_fora_do_calculo_kg"] >= 65
    assert calc["qualidade"]["origem_dados"] == "exemplo"

def test_peca_sem_composicao_nao_e_massa_zero_nem_completa(mundo):
    c = mundo
    vid = novo_veiculo(c, 100)
    c.post("/Componentes", json={"veiculo_id": vid, "categoria": "Motor", "peso_kg": 100})
    calc = c.get(f"/Calculos/{vid}").json
    assert calc["resultado_integral"] is False
    assert any("sem composição" in a for a in calc["avisos"])

def test_fonte_agregada_nao_conta_duas_vezes(mundo):
    c = mundo
    vid = novo_veiculo(c, 100, fonte_composicao="agregada")
    c.post("/Componentes", json={"veiculo_id": vid, "categoria": "P", "peso_kg": 100,
                                 "composicao": [{"categoria": "Aço", "massa_kg": 100}]})
    with Session() as s:
        from app.data.db import ResolverMaterial
        m = ResolverMaterial(s, "Aço")
        s.add(ComposicaoVeiculo(veiculo_id=vid, material_id=m.id, categoria_texto="Aço", massa_kg=60))
        s.commit()
    calc = c.get(f"/Calculos/{vid}").json
    mats = {m["material"]: m["massa_kg"] for m in calc["reciclagem_por_material"]}
    assert mats["Aço"] == 60                          # só a agregada
    assert any("ignorada" in a for a in calc["avisos"])


# ---------- QR permanente ----------
def test_qr_nao_e_apagado_ao_regerar(mundo):
    c = mundo
    with Session() as s:
        q = s.query(QRFiles).first()
        qid = q.id
        q.CriadoEm = datetime.now() - timedelta(days=30)
        q.ExpiraEm = datetime.now() - timedelta(days=29)      # valor "vencido" do esquema antigo
        s.commit()
    antes = Session().query(QRFiles).count()
    QR.RegerarTodos()
    with Session() as s:
        assert s.query(QRFiles).count() == antes
        assert s.get(QRFiles, qid) is not None

def test_qr_pagina_individual_e_pdf_por_codigo(mundo):
    c = mundo
    assert c.get("/QR/1").status_code == 200           # antes: erro por 'filtros' indefinido
    with Session() as s:
        vq = s.query(QRFiles).filter(QRFiles.veiculo_id.isnot(None)).first()
        pq = s.query(QRFiles).filter(QRFiles.peca_id.isnot(None)).first()
        mq = s.query(QRFiles).filter(QRFiles.material_id.isnot(None)).first()
        codigos = [vq.codigo, pq.codigo, mq.codigo]; ids = [vq.id, pq.id, mq.id]
    for cod in codigos:
        r = c.get(f"/q/{cod}")
        assert r.status_code == 200 and r.data[:4] == b"%PDF"
    assert c.get(f"/download/{ids[0]}").status_code == 200   # links antigos continuam
    assert c.get("/q/nao-existe").status_code == 404
    assert c.get(f"/QR/{ids[0]}/imagem").data[:4] == b"\x89PNG"

def test_url_base_configuravel(monkeypatch):
    monkeypatch.setenv("QR_BASE_URL", "https://pegada.exemplo.com.br/")
    assert QR.BaseUrl("127.0.0.1:5000") == "https://pegada.exemplo.com.br"
    assert QR.Link(QR.BaseUrl(), "abc") == "https://pegada.exemplo.com.br/q/abc"
    monkeypatch.delenv("QR_BASE_URL"); monkeypatch.setenv("QR_IP", "10.0.0.5"); monkeypatch.setenv("QR_PORT", "8000")
    assert QR.BaseUrl() == "http://10.0.0.5:8000"

def test_peca_nova_nasce_com_qr(mundo):
    c = mundo
    vid = novo_veiculo(c)
    pid = c.post("/Componentes", json={"veiculo_id": vid, "categoria": "Pneus", "peso_kg": 10}).json["id"]
    with Session() as s:
        assert s.query(QRFiles).filter_by(peca_id=pid).count() == 1
        assert s.query(QRFiles).filter_by(veiculo_id=vid).count() == 1


# ---------- remoção lógica ----------
def test_remocao_logica_preserva_historico(mundo):
    c = mundo
    vid = novo_veiculo(c)
    pid = c.post("/Componentes", json={"veiculo_id": vid, "categoria": "P", "peso_kg": 5}).json["id"]
    with Session() as s:
        cod = s.query(QRFiles).filter_by(veiculo_id=vid).first().codigo
    assert c.delete(f"/Veiculo/{vid}").status_code == 204
    assert vid not in [v["id"] for v in c.get("/Veiculo").json]
    assert pid not in [p["id"] for p in c.get("/Componentes").json]
    assert c.get(f"/Calculos/{vid}").status_code == 404
    assert c.delete(f"/Veiculo/{vid}").status_code == 404
    with Session() as s:                                   # nada foi apagado
        assert s.get(Veiculo, vid).removido_em is not None
        assert s.get(Pecas, pid).removido_em is not None
    assert c.get(f"/q/{cod}").status_code == 200           # o QR continua resolvendo

def test_remover_componente_e_logico(mundo):
    c = mundo
    vid = novo_veiculo(c)
    pid = c.post("/Componentes", json={"veiculo_id": vid, "categoria": "P", "peso_kg": 5}).json["id"]
    assert c.delete(f"/Componentes/{pid}").status_code == 200
    assert c.get(f"/Componentes/{pid}").status_code == 404
    with Session() as s:
        assert s.get(Pecas, pid) is not None

def test_remover_modelo_com_pecas_copiadas_nao_quebra_fk(mundo):
    c = mundo
    mid = c.post("/VeiculoModelo", json={"veiculo": "M", "modelo": "M", "massa_total_kg": 100}).json["id"]
    assert c.post(f"/VeiculoModelo/{mid}/componentes", json={"categoria": "Motor", "massa_ref_kg": 50}).status_code == 201
    r = c.post("/Veiculo", json={"veiculo": "M", "modelo": "M", "chassi": chassi(), "massa_total_kg": 100, "modelo_base_id": mid})
    assert r.json["pecas_copiadas"] == 1
    assert c.delete(f"/VeiculoModelo/{mid}").status_code == 204    # antes: IntegrityError com FK ligada
    with Session() as s:
        assert s.query(Pecas).filter(Pecas.veiculo_id == r.json["id"]).count() == 1


# ---------- lotes x JSON ----------
def test_editar_json_sem_perder_lote(mundo):
    c = mundo
    vid = novo_veiculo(c, 100)
    pid = c.post("/Componentes", json={"veiculo_id": vid, "categoria": "P", "peso_kg": 100}).json["id"]
    mid = c.post("/Materiais", json={"peca_id": pid, "categoria": "Aço", "peso_kg": 30}).json["id"]
    comp = c.get(f"/Componentes/{pid}").json["composicao"]
    assert len(comp) == 1
    # tirar o item que tem lote -> bloqueado, nada muda
    r = c.put(f"/Componentes/{pid}", json={"composicao": [{"categoria": "Cobre", "massa_kg": 10}]})
    assert r.status_code == 400 and "lote" in r.json["erro"]
    assert len(c.get(f"/Componentes/{pid}").json["composicao"]) == 1
    # manter o item_uid e mudar a massa -> o lote acompanha
    comp[0]["massa_kg"] = 45
    assert c.put(f"/Componentes/{pid}", json={"composicao": comp}).status_code == 200
    assert next(m for m in c.get("/Materiais").json if m["id"] == mid)["peso_kg"] == 45


# ---------- seed de referência ----------
def test_seed_sem_dados_nao_cria_nada(mundo):
    with Session() as s:
        antes = s.query(Veiculo).count()
    assert Seeds.SeedReferenciaPDF() is None
    with Session() as s:
        assert s.query(Veiculo).count() == antes

def test_seed_idempotente_e_calculo_integral(mundo):
    c = mundo
    # DADOS SINTÉTICOS só para testar a mecânica (NÃO são os do PDF)
    comps = [(f"Comp {i}", 50.0) for i in range(24)]                      # 1200 kg
    comp_global = [("Aço", 700.0), ("Plásticos", 300.0), ("Borracha", 200.0)]   # 1200 kg
    vid = Seeds.SeedReferenciaPDF(comps, comp_global)
    assert vid
    assert Seeds.SeedReferenciaPDF(comps, comp_global) is None             # idempotente
    with Session() as s:
        assert s.query(Veiculo).filter_by(Chassi=Seeds.CHASSI_REF).count() == 1
        assert s.query(Pecas).filter_by(veiculo_id=vid).count() == 24
        assert all(p.composicao is None for p in s.query(Pecas).filter_by(veiculo_id=vid))   # composição individual não inventada
        v = s.get(Veiculo, vid)
        assert (v.origem_dados, v.fonte_composicao, v.motorizacao, v.combustivel) == ("referencia_pdf", "agregada", "Combustão interna", "Flex")
        assert v.MassaTotal == 1200 and v.VidaUtilAnos == 15 and v.Kilometragem == 180000
        assert v.atividade is not None
    calc = c.get(f"/Calculos/{vid}").json
    assert calc["resultado_integral"] is True
    assert not any("Dados de atividade não cadastrados" in a for a in calc["avisos"])
    assert any("demonstrativos" in a for a in calc["avisos"])
    assert calc["massas"]["solidos_kg"] == 1200

def test_seed_rejeita_soma_maior_que_massa(mundo):
    with pytest.raises(ValueError):
        # chassi já existe -> precisa limpar para chegar na validação
        with Session() as s:
            s.query(Veiculo).filter_by(Chassi=Seeds.CHASSI_REF).update({Veiculo.Chassi: "REF-PDF-OLD"})
            s.commit()
        Seeds.SeedReferenciaPDF([("A", 1300.0)], [("Aço", 1200.0)])
