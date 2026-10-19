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

from src.app.data.db import (session, Veiculo, Componentes, Materiais,
                     Destinacao, ResiduoEspecial, DadoAtividade, FatorEmissao)
from src.app.data.doc.GerarDados import QR

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

#region QR
@app.route("/QR/<doc>", methods=["GET"])
def QRGeradoPagina():
    return render_template("QRGerado.html")

def DownloadPDF(QRDoc):
    upload = Upload.query.filter_by(id=QRDoc).first()
    return send_file(BytesIO(upload.data), download_name=upload.filename, as_attachment=True )
#endregion QR

#region rodar
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
#endregion rodar