#region baseSistema
import sys, os
from io import BytesIO
if getattr(sys, 'frozen', False):
    dir_base = os.path.dirname(sys.executable)
else:
    dir_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sobe 1 nível

sys.path.append(dir_base)

from flask import Flask, render_template, request, jsonify
from flasgger import Swagger, swag_from  # swagger em /apidocs
from flask_cors import CORS
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.data.db import (session, Veiculo, Pecas, Materiais,)
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
}
Swagger(app)  # fica em /apidocs

#endregion baseSistema

#region Interface
@app.route("/", methods=["GET"])  # home page
def Home():
    return render_template("index.html")

@app.route("/Dados", methods=['GET'])
def Dados():
    return render_template("DadosDB.html")

#endregion Interface

from flask import Flask, render_template, request, jsonify, send_file, abort
from app.data.db import session, Veiculo, Pecas, Materiais, QRFiles
from app.data.doc.GerarDados import QR

#region QR
@app.route("/QR", methods=["GET"])
def QRLista():
    """Lista os QRs gerados, para escanear da tela do PC no teste."""
    qrs = session.query(QRFiles).order_by(QRFiles.id).all()
    return render_template("QRGerado.html", qrs=qrs)

@app.route("/QR/<int:qr_id>", methods=["GET"])
def QRGeradoPagina(qr_id):
    registro = session.get(QRFiles, qr_id)
    if registro is None:
        abort(404)
    return render_template("QRGerado.html", qrs=[registro])

@app.route("/QR/<int:qr_id>/imagem", methods=["GET"])
def QRImagem(qr_id):
    registro = session.get(QRFiles, qr_id)
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

#region rodar
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
#endregion rodar