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

from app.data.db import Session, Veiculo, Pecas, Materiais, QRFiles
from app.data.doc.GerarDados import QR

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

#endregion Interface
#region QR
@app.route("/QR", methods=["GET"])
@app.route("/qr", methods=["GET"])
@swag_from("app/data/doc/swagger/qr_lista.yml")
def QRLista():
    s = get_session()
    qrs = s.query(QRFiles).order_by(QRFiles.id).all()
    return render_template("QRGerado.html", qrs=qrs)

@app.route("/QR/<int:qr_id>", methods=["GET"])
def QRGeradoPagina(qr_id):
    s = get_session()
    registro = s.get(QRFiles, qr_id)
    if registro is None:
        abort(404)
    return render_template("QRGerado.html", qrs=[registro])

@app.route("/QR/<int:qr_id>/imagem", methods=["GET"])
def QRImagem(qr_id):
    s = get_session()
    registro = s.get(QRFiles, qr_id)
    if registro is None or not registro.path:
        abort(404)
    return send_file(registro.path, mimetype="image/png")

@app.route("/download/<int:qr_id>", methods=["GET"])  # rota que o QR aponta
def DownloadPDF(qr_id):
    pdf = QR.QrLido(qr_id)
    if pdf is None:
        abort(404)
    return send_file(pdf, mimetype="application/pdf",
                     download_name=f"relatorio_qr_{qr_id}.pdf",
                     as_attachment=True)
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
            "vida_util_anos": v.VidaUtilAnos,
            "estado": v.Estado,
        } for v in s.query(Veiculo).all()])
    finally:
        s.close()


@app.route("/Componentes", methods=["GET"])
@swag_from("docs/ComponentesGet.yml")
def listar_componentes():
    s = get_session()
    try:
        return jsonify([{
            "id": c.id,
            "veiculo_id": c.veiculo_id,
            "categoria": c.Categoria,
            "peso_kg": c.Peso,
        } for c in s.query(Pecas).all()])
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
            "peso_kg": m.Peso,
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
            Categoria=dados.get("categoria"),
            Motorizacao=dados.get("motorizacao"),
            Combustivel=dados.get("combustivel"),
            MassaTotal=dados.get("massa_total_kg"),
            VidaUtilAnos=dados.get("vida_util_anos"),
            Quilometragem=dados.get("quilometragem_km"),
            Estado=dados.get("estado") or "Fim de vida",
        )
        session.add(veiculo)
        session.commit()
        resultado = {
            "id": veiculo.id,
            "categoria": veiculo.Categoria,
            "motorizacao": veiculo.Motorizacao,
            "combustivel": veiculo.Combustivel,
            "massa_total_kg": veiculo.MassaTotal,
            "vida_util_anos": veiculo.VidaUtilAnos,
            "quilometragem_km": veiculo.Quilometragem,
            "estado": veiculo.Estado,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()


@app.route("/Componentes", methods=["POST"])
@swag_from("docs/ComponentesPost.yml")
def criar_componente():
    session = get_session()
    dados = request.get_json()
    try:
        componente = Componentes(
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
            veiculo_id=dados.get("veiculo_id"),
            Categoria=dados.get("categoria"),
            Peso=dados.get("peso_kg"),
        )
        session.add(material)
        session.commit()
        resultado = {
            "id": material.id,
            "veiculo_id": material.veiculo_id,
            "categoria": material.Categoria,
            "peso_kg": material.Peso,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()
#endregion post
#endregion dados
#region rodar
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
#endregion rodar