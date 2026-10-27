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
from sqlalchemy import func,create_engine

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
import qrcode

from app.data.db import session, Session, Veiculo, Pecas, Materiais, QRFiles
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

@app.route("/Veiculo", methods=["GET"])
@swag_from("docs/VeiculoGet.yml")
def listar_veiculos():
    s = get_session()
    try:
        return jsonify([{
            "id": v.id,
            "veiculo": v.veiculo,
            "modelo": v.Modelo,
            "chassi": v.Chassi,
            "ano": v.Ano,
            "categoria": v.CategoriaVeiculo,
            "massa_total_kg": v.MassaTotal,
            "vida util anos": v.VidaUtilAnos,
            "KMs":v.Kilometragem,
            "quantidade Pecas": v.QuantidadePecas,
            "quantidade por modelos": v.QuantidadePorModelos,
            "estado": v.Estado,
        } for v in s.query(Veiculo).all()])
    finally:
        s.close()

@app.route("/VeiculoModelo", methods=["GET"])
@swag_from("docs/VeiculoModeloGet.yml")
def listar_veiculo_modelo():
    s = get_session()
    try:
        modelos = s.query(Veiculo).filter(Veiculo.Chassi.is_(None)).all()
        return jsonify([{
            "id": v.id,
            "veiculo": v.veiculo,
            "modelo": v.Modelo,
            "ano": v.Ano,
            "categoria": v.CategoriaVeiculo,
            "massa_total_kg": v.MassaTotal,
            "vida_util_anos": v.VidaUtilAnos,
            "quilometragem_km": v.Kilometragem,
            "quantidade_pecas": v.QuantidadePecas,
            "quantidade_por_modelos": v.QuantidadePorModelos,
            "estado": v.Estado,
        } for v in modelos])
    finally:
        s.close()

@app.route("/VeiculoModelo", methods=["POST"])
@swag_from("data/doc/swagger/VeiculoModeloPost.yml")
def criar_veiculo_modelo():
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        modelo = Veiculo(
            veiculo=dados.get("veiculo"),
            Modelo=dados.get("modelo"),
            Chassi=dados.get("chassi"), 
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
        return jsonify({
            "id": modelo.id,
            "veiculo": modelo.veiculo,
            "modelo": modelo.Modelo,
            "ano": modelo.Ano,
            "categoria": modelo.CategoriaVeiculo,
            "massa_total_kg": modelo.MassaTotal,
            "vida_util_anos": modelo.VidaUtilAnos,
            "quilometragem_km": modelo.Kilometragem,
            "quantidade_por_modelos": modelo.QuantidadePorModelos,
            "estado": modelo.Estado,
        }), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
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

#endregion ler

#region post
@app.route("/Veiculo", methods=["POST"])
@swag_from("docs/veiculoCriar.yml")
def criar_veiculo():
    session = get_session()
    dados = request.get_json()
    try:
        veiculo = Veiculo(
            veiculo=dados.get("veiculo"),
            Modelo=dados.get("modelo"),
            Chassi=dados.get("chassi"),
            Ano=dados.get("ano"),
            CategoriaVeiculo=dados.get("categoria"),
            MassaTotal=dados.get("massa_total_kg"),
            VidaUtilAnos=dados.get("vida_util_anos"),
            Kilometragem=dados.get("quilometragem_km"),
            Estado=dados.get("estado") or "Fim de vida",
        )
        session.add(veiculo)
        session.commit()
        resultado = {
            "id": veiculo.id,
            "veiculo": veiculo.veiculo,
            "modelo": veiculo.Modelo,
            "chassi": veiculo.Chassi,
            "categoria": veiculo.CategoriaVeiculo,
            "massa_total_kg": veiculo.MassaTotal,
            "vida_util_anos": veiculo.VidaUtilAnos,
            "quilometragem_km": veiculo.Kilometragem,
            "estado": veiculo.Estado,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()

@app.route("/Veiculo/<int:veiculo_id>", methods=["PUT"])
def editar_veiculo(veiculo_id):
    s = get_session()
    dados = request.get_json(silent=True) or {}
    try:
        v = s.get(Veiculo, veiculo_id)
        if v is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        v.veiculo = dados.get("veiculo", v.veiculo)
        v.Modelo = dados.get("modelo", v.Modelo)
        v.Chassi = dados.get("chassi") or v.Chassi
        v.Ano = dados.get("ano") or v.Ano
        v.CategoriaVeiculo = dados.get("categoria", v.CategoriaVeiculo)
        v.MassaTotal = dados.get("massa_total_kg", v.MassaTotal)
        v.VidaUtilAnos = dados.get("vida_util_anos", v.VidaUtilAnos)
        v.Kilometragem = dados.get("quilometragem_km", v.Kilometragem)
        v.Estado = dados.get("estado", v.Estado)
        s.commit()
        return jsonify({"id": v.id}), 200
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

@app.route("/Componentes", methods=["POST"])
@swag_from("docs/ComponentesPost.yml")
def criar_componente():
    session = get_session()
    dados = request.get_json()
    try:
        componente = Pecas(
            veiculo_id=dados.get("veiculo_id"),
            Categoria=dados.get("categoria"),
            Peso=dados.get("peso_kg"),
        )
        session.add(componente)
        session.commit()
        resultado = {
            "id": componente.id,
            "veiculo_id": componente.veiculo_id,
            "categoria": componente.Categoria,
            "peso_kg": componente.Peso,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()


@app.route("/Materiais", methods=["POST"])
@swag_from("docs/MateriaisPost.yml")
def criar_material():
    session = get_session()
    dados = request.get_json()
    try:
        material = Materiais(
            peca_id=dados.get("veiculo_id"),
            Categoria=dados.get("categoria"),
            Peso=dados.get("peso_kg"),
        )
        session.add(material)
        session.commit()
        return jsonify({
            "id": material.id,
            "peca_id": material.peca_id,
            "categoria": material.Categoria,
            "peso_kg": material.Peso,
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()
#endregion post
#endregion dados
#region rodar
if __name__ == "__main__":
    # com debug, o reloader executa este bloco 2x; só o processo filho (WERKZEUG_RUN_MAIN) regera
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        QR.RegerarTodos()
    app.run(host="0.0.0.0", port=5000)
#endregion rodar