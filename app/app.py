#region baseSistema
import sys, os
from io import BytesIO
if getattr(sys, 'frozen', False):
    dir_base = os.path.dirname(sys.executable)
else:
    dir_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sobe 1 nível

sys.path.append(dir_base)

from flask import Flask, render_template, request, jsonify, send_file, abort
from flasgger import Swagger, swag_from  # swagger em /apidocs
from flask_cors import CORS
from sqlalchemy import func,create_engine, or_

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
import qrcode

from app.data.db import session, Session, ModeloVeiculo, Veiculo, Pecas, Materiais, QRFiles
from app.data.doc.Calculos import *
from app.data.doc.GerarDados import QR, IpLocal

app = Flask(__name__)
app.debug = True  # debug só enquanto desenvolve, para não precisar reiniciar a cada alteração

# permite acesso de todas as origens (resolve "from origin 'null' has been blocked" no android)
CORS(app, origins=["*"])

app.config['SWAGGER'] = {
    'title': 'API Pegada de Carbono',
    'termsOfService': '',
    'description': 'Documentação da API de pegada de carbono',
    'version': '0.1.0',
    'specs_route': '/api/docs',
}
Swagger(app)  # fica em /apidocs

def get_session():
    return Session()
#endregion baseSistema

#region Interface
@app.route("/", methods=["GET"])  # home page
def Home():
    return render_template("index.html")

@app.route("/Dados", methods=['GET'])
def Dados():
    return render_template("DadosDB.html")

@app.route("/QR/<int:qr_id>", methods=["GET"])
def QRGeradoPagina(qr_id):
    s = get_session()
    registro = s.get(QRFiles, qr_id)
    if registro is None:
        abort(404)
    return render_template("QRGerado.html", qrs=[registro])

@app.route("/Calculos", methods=['GET'])
def Calculos():
    return render_template("Calculos.html")

#endregion Interface
#region QR
@app.route("/QR", methods=["GET"])
@app.route("/qr", methods=["GET"])
@swag_from("app/data/doc/swagger/qr_lista.yml")
def QRLista():
    with Session() as s:
        qrs = s.query(QRFiles).order_by(QRFiles.id).all()
        return render_template("QRGerado.html", qrs=qrs)


@app.route("/QR/<int:qr_id>/imagem", methods=["GET"])
def QRImagem(qr_id):
    with Session() as s:
        if s.get(QRFiles, qr_id) is None:
            abort(404)

    host = request.host
    if host.startswith(("127.0.0.1", "localhost")):
        host = f"{IpLocal()}:5000"      # celular não alcança localhost

    img = qrcode.make(f"http://{host}/download/{qr_id}", box_size=10, border=4)
    buf = BytesIO()                      # BytesIO já está importado no seu app.py
    img.save(buf, format="PNG")
    buf.seek(0)
    resp = send_file(buf, mimetype="image/png", max_age=0)
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route("/download/<int:qr_id>", methods=["GET"])  # rota que o QR aponta
def DownloadPDF(qr_id):
    pdf = QR.QrLido(qr_id)
    if pdf is None:
        abort(404)
    return send_file(pdf, mimetype="application/pdf",
                     download_name=f"relatorio_qr_{qr_id}.pdf",
                     as_attachment=True)
#pesquisar qr (a fazer)
#endregion QR

#region dados
#region ler
@app.route("/VeiculoModelo", methods=["GET"])
@swag_from("docs/VeiculoModeloGet.yml")
def listar_veiculo_modelo():
    s = get_session()
    try:
        return jsonify([{
            "id": m.id,
            "veiculo": m.veiculo,
            "modelo": m.Modelo,
            "ano": m.Ano,
            "categoria": m.CategoriaVeiculo,
            "massa total kg": m.MassaTotal,
            "vida util anos": m.VidaUtilAnos,
            "quilometragem km": m.Kilometragem,
            "quantidade por modelos": m.QuantidadePorModelos,
            "estado": m.Estado,
        } for m in s.query(ModeloVeiculo).all()])
    finally:
        s.close()

@app.route("/Veiculo", methods=["GET"])
@swag_from("docs/VeiculoGet.yml")
def listar_veiculos():
    s = get_session()
    try:
        return jsonify([{
            "id": v.id,
            "modelo_id": v.modelo_id,
            "veiculo": v.veiculo,
            "modelo": v.Modelo,
            "chassi": v.Chassi,
            "ano": v.Ano,
            "categoria": v.CategoriaVeiculo,
            "massa total kg": v.MassaTotal,
            "vida util anos": v.VidaUtilAnos,  # manter assim para aparecer corretamente
            "KMs": v.Kilometragem,
            "quilometragem km": v.Kilometragem,  # o formulário de editar lê esta chave
            "quantidade Pecas": len(v.pecas),
            "estado": v.Estado,
        } for v in s.query(Veiculo).all()])
    finally:
        s.close()

@app.route("/Materiais", methods=["GET"])
@swag_from("docs/MateriaisGet.yml")
def listar_materiais():
    s = get_session()
    try:
        return jsonify([{
            "id": m.id,
            "peca_id": m.peca_id,
            "categoria": m.Categoria,
            "peso kg": m.Peso,
        } for m in s.query(Materiais).all()])
    finally:
        s.close()

@app.route("/Componentes", methods=["GET"])
@swag_from("docs/ComponentesGet.yml")
def listar_componentes():
    s = get_session()
    try:   
        tipos = (s.query(Pecas, Veiculo)
                .join(Veiculo, Pecas.veiculo_id == Veiculo.id)
                .all())
        return jsonify([{
            "id": p.id,
            "id do veiculo":v.id,
            "veiculo_id": p.veiculo_id,
            "modelo veiculo da peca": v.Modelo,
            "categoria": p.Categoria,
            "peso kg": p.Peso,
        } for p, v in tipos])
    finally:
        s.close()

#endregion ler

#region post
@app.route("/VeiculoModelo", methods=["POST"])
@swag_from("data/doc/swagger/VeiculoModeloPost.yml")
def criar_veiculo_modelo():
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        modelo = ModeloVeiculo(
            veiculo=dados.get("veiculo"),
            Modelo=dados.get("modelo"),
            Ano=dados.get("ano") or None,
            CategoriaVeiculo=dados.get("categoria"),
            MassaTotal=dados.get("massa_total_kg"),
            VidaUtilAnos=dados.get("vida_util_anos") or None,
            Kilometragem=dados.get("quilometragem_km") or None,
            QuantidadePorModelos=dados.get("quantidade_por_modelos") or 1,
            Estado=dados.get("estado") or "Fim de vida",
        )
        s.add(modelo)
        s.commit()
        return jsonify({"id": modelo.id}), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Veiculo", methods=["POST"])
@swag_from("docs/veiculoCriar.yml")
def criar_veiculo():
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        chassi = (dados.get("chassi") or "").strip()
        if not chassi:
            return jsonify({"erro": "Informe o chassi do veículo"}), 400
        if s.query(Veiculo).filter(Veiculo.Chassi == chassi).first():
            return jsonify({"erro": "Já existe um veículo com este chassi"}), 409

        modelo_id = dados.get("modelo_base_id")
        if modelo_id and s.get(ModeloVeiculo, modelo_id) is None:
            return jsonify({"erro": "Modelo base não encontrado"}), 404

        veiculo = Veiculo(
            modelo_id=modelo_id or None,
            veiculo=dados.get("veiculo"),
            Modelo=dados.get("modelo"),
            Chassi=chassi,
            Ano=dados.get("ano") or None,
            CategoriaVeiculo=dados.get("categoria"),
            MassaTotal=dados.get("massa_total_kg"),
            VidaUtilAnos=dados.get("vida_util_anos") or None,
            Kilometragem=dados.get("quilometragem_km") or None,
            Estado=dados.get("estado") or "Fim de vida",
        )
        s.add(veiculo)
        s.commit()
        return jsonify({"id": veiculo.id}), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Componentes", methods=["POST"])
@swag_from("docs/ComponentesPost.yml")
def criar_componente():
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        if not dados.get("veiculo_id") or s.get(Veiculo, dados["veiculo_id"]) is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        componente = Pecas(
            veiculo_id=dados.get("veiculo_id"),
            Categoria=dados.get("categoria"),
            Peso=dados.get("peso_kg"),
        )
        s.add(componente)
        s.commit()
        return jsonify({"id": componente.id}), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Materiais", methods=["POST"])
@swag_from("docs/MateriaisPost.yml")
def criar_material():
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        if not dados.get("peca_id") or s.get(Pecas, dados["peca_id"]) is None:
            return jsonify({"erro": "Peça não encontrada"}), 404
        material = Materiais(
            peca_id=dados.get("peca_id"),   # estava dados.get("veiculo_id")
            Categoria=dados.get("categoria"),
            Peso=dados.get("peso_kg"),
        )
        s.add(material)
        s.commit()
        return jsonify({"id": material.id}), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion post

#region put
@app.route("/VeiculoModelo/<int:modelo_id>", methods=["PUT"])
def editar_veiculo_modelo(modelo_id):
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        m = s.get(ModeloVeiculo, modelo_id)
        if m is None:
            return jsonify({"erro": "Modelo não encontrado"}), 404
        campos = {
            "veiculo": "veiculo", "modelo": "Modelo", "ano": "Ano",
            "categoria": "CategoriaVeiculo", "massa_total_kg": "MassaTotal",
            "vida_util_anos": "VidaUtilAnos", "quilometragem_km": "Kilometragem",
            "quantidade_por_modelos": "QuantidadePorModelos", "estado": "Estado",
        }
        for chave, atributo in campos.items():
            if chave in dados:
                setattr(m, atributo, dados[chave])
        s.commit()
        return jsonify({"id": m.id}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Veiculo/<int:veiculo_id>", methods=["PUT"])
def editar_veiculo(veiculo_id):
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        v = s.get(Veiculo, veiculo_id)
        if v is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        campos = {
            "veiculo": "veiculo", "modelo": "Modelo", "chassi": "Chassi", "ano": "Ano",
            "categoria": "CategoriaVeiculo", "massa_total_kg": "MassaTotal",
            "vida_util_anos": "VidaUtilAnos", "quilometragem_km": "Kilometragem",
            "estado": "Estado",
        }
        for chave, atributo in campos.items():
            if chave == "chassi" and not dados.get("chassi"):
                continue  # chassi não pode ficar vazio
            if chave in dados:
                setattr(v, atributo, dados[chave])
        s.commit()
        return jsonify({"id": v.id}), 200
    except Exception as e:
        s.rollback()  # chassi repetido cai aqui (UNIQUE)
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Componentes/<int:peca_id>", methods=["PUT"])
def editar_componente(peca_id):
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        p = s.get(Pecas, peca_id)
        if p is None:
            return jsonify({"erro": "Componente não encontrado"}), 404
        p.veiculo_id = dados.get("veiculo_id", p.veiculo_id)
        p.Categoria = dados.get("categoria", p.Categoria)
        p.Peso = dados.get("peso_kg", p.Peso)
        s.commit()
        return jsonify({"id": p.id}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Materiais/<int:material_id>", methods=["PUT"])
def editar_material(material_id):
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        m = s.get(Materiais, material_id)
        if m is None:
            return jsonify({"erro": "Material não encontrado"}), 404
        m.peca_id = dados.get("peca_id", m.peca_id)
        m.Categoria = dados.get("categoria", m.Categoria)
        m.Peso = dados.get("peso_kg", m.Peso)
        s.commit()
        return jsonify({"id": m.id}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion put

#region delete
@app.route("/VeiculoModelo/<int:modelo_id>", methods=["DELETE"])
def remover_veiculo_modelo(modelo_id):
    s = get_session()
    try:
        m = s.get(ModeloVeiculo, modelo_id)
        if m is None:
            return jsonify({"erro": "Modelo não encontrado"}), 404
        s.delete(m)   # os veículos ligados ficam, só perdem o modelo_id
        s.commit()
        return "", 204
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Veiculo/<int:veiculo_id>", methods=["DELETE"])
def remover_veiculo(veiculo_id):
    s = get_session()
    try:
        v = s.get(Veiculo, veiculo_id)
        if v is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        s.delete(v)
        s.commit()
        return "", 204
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Materiais/<int:material_id>", methods=["DELETE"])
def remover_material(material_id):
    s = get_session()
    try:
        m = s.get(Materiais, material_id)
        if m is None:
            return jsonify({"erro": "Material não encontrado"}), 404
        s.delete(m)
        s.commit()
        return jsonify({"ok": True}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Componentes/<int:peca_id>", methods=["DELETE"])
def remover_componente(peca_id):
    s = get_session()
    try:
        p = s.get(Pecas, peca_id)
        if p is None:
            return jsonify({"erro": "Componente não encontrado"}), 404
        s.delete(p)
        s.commit()
        return jsonify({"ok": True}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion delete
#region calculos
def _calc(veiculo_id, parte="resumo"):
    s = get_session()
    try:
        r = Calculo.Veiculo(s, veiculo_id, parte)
        if r is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        return jsonify(r)
    except Exception as e:
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
 
@app.route("/Calculos/<int:veiculo_id>", methods=["GET"])
def calculo_resumo(veiculo_id):
    return _calc(veiculo_id)
 
@app.route("/Calculos/<int:veiculo_id>/cenarios", methods=["GET"])
def calculo_cenarios(veiculo_id):
    return _calc(veiculo_id, "cenarios")
 
@app.route("/Calculos/<int:veiculo_id>/sensibilidade", methods=["GET"])
def calculo_sensibilidade(veiculo_id):
    return _calc(veiculo_id, "sensibilidade")
 
# ---- atividade do veículo
@app.route("/Atividade/<int:veiculo_id>", methods=["GET"])
def ler_atividade(veiculo_id):
    s = get_session()
    try:
        atividade, _ = Calculo.Atividade(s, veiculo_id)
        return jsonify(atividade)
    finally:
        s.close()
 
@app.route("/Atividade/<int:veiculo_id>", methods=["PUT"])
def salvar_atividade(veiculo_id):
    s = get_session()
    try:
        if s.get(Veiculo, veiculo_id) is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        dados = request.get_json(silent=True) or {}
        a = s.query(AtividadeVeiculo).filter_by(veiculo_id=veiculo_id).first()
        if a is None:
            a = AtividadeVeiculo(veiculo_id=veiculo_id)
            s.add(a)
        for campo in ATIVIDADE_PADRAO:
            if campo in dados:
                v = float(dados[campo])
                if v < 0:
                    return jsonify({"erro": f"{campo} não pode ser negativo"}), 400
                setattr(a, campo, v)
        s.commit()
        return jsonify({"ok": True})
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
 
# ---- destinos dos materiais (banco + padrão do PDF para o que faltar)
@app.route("/Destinos", methods=["GET"])
def listar_destinos():
    s = get_session()
    try:
        _, destinos = Calculo.Parametros(s)
        return jsonify([{"material": g, "reciclagem": destinos[g][0], "reuso": destinos[g][1],
                         "valorizacao": destinos[g][2], "disposicao": destinos[g][3]}
                        for g in GRUPOS])
    finally:
        s.close()
 
@app.route("/Destinos/<material>", methods=["PUT"])
def salvar_destino(material):
    if material not in GRUPOS:
        return jsonify({"erro": "Material desconhecido"}), 404
    s = get_session()
    try:
        d = request.get_json(silent=True) or {}
        cols = ("reciclagem", "reuso", "valorizacao", "disposicao")
        vals = [float(d.get(c, 0)) for c in cols]
        if any(v < 0 for v in vals) or abs(sum(vals) - 100) > 0.01:
            return jsonify({"erro": f"Os quatro destinos devem somar 100% (soma atual: {sum(vals):g})"}), 400
        reg = s.get(DestinoMaterial, material) or DestinoMaterial(material=material)
        for c, v in zip(cols, vals):
            setattr(reg, c, v)
        s.add(reg)
        s.commit()
        return jsonify({"ok": True})
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
 

@app.route("/Fatores", methods=["GET"])
def listar_fatores():
    s = get_session()
    try:
        banco = {f.chave: f for f in s.query(FatorEmissao).all()}
        saida = []
        for chave, valor, unidade, origem in FATORES_PADRAO:
            f = banco.get(chave)
            saida.append({"chave": chave, "valor": f.valor if f else valor,
                          "unidade": unidade, "origem": (f.origem if f else origem)})
        return jsonify(saida)
    finally:
        s.close()
 
@app.route("/Fatores/<path:chave>", methods=["PUT"])
def salvar_fator(chave):
    padrao = {c: (v, u, o) for c, v, u, o in FATORES_PADRAO}
    if chave not in padrao:
        return jsonify({"erro": "Fator desconhecido"}), 404
    s = get_session()
    try:
        d = request.get_json(silent=True) or {}
        valor = float(d.get("valor"))
        if valor < 0:
            return jsonify({"erro": "O valor não pode ser negativo"}), 400
        reg = s.get(FatorEmissao, chave) or FatorEmissao(chave=chave, unidade=padrao[chave][1])
        reg.valor = valor
        reg.origem = d.get("origem") or padrao[chave][2]
        s.add(reg)
        s.commit()
        return jsonify({"ok": True})
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion calculos
#endregion dados
#region rodar
if __name__ == "__main__":
    # com debug, o reloader executa este bloco 2x; só o processo filho (WERKZEUG_RUN_MAIN) regera
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        QR.RegerarTodos()
    app.run(host="0.0.0.0", port=5000)
#endregion rodar