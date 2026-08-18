import sys,os
if getattr(sys, 'frozen', False):
    dir_base = os.path.dirname(sys.executable)
else:
    dir_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sobe 1 nível

sys.path.append(dir_base)

from flask import Flask, render_template, request, redirect, url_for
from src.db import Materiais, session
#region baseSistema
app = Flask(__name__)
app.debug = True #debug so qnd for fazer alterações e nn ter que rebuildar/rerodar o código
#integrar a um db ja existente
@app.route("/")#home page
def Home():
	return render_template("index.html")#retornar o arquivo html de home
#endregion baseSistema

#region cliente
#region test
@app.route("/test")#home page
def Test():
    print("fora do site")
    return render_template("Orcamento.html")
#endregion test

#endregion cliente
@app.route("/Orcamento")#home page
def Orcamento():
    return render_template("Orcamento.html")

@app.route("/ControleOrcamento")#home page
def ControleOrcamento():
    materiais = session.query(Materiais).all()
    return render_template("ControleOrcamento.html", Materiais=materiais)

@app.route("/FimProduto")
def FimProduto():
    return render_template("FimProduto.html")
#region rodar
app.run(host="0.0.0.0",port=5000)