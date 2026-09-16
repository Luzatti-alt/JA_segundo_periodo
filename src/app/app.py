import sys,os
if getattr(sys, 'frozen', False):
    dir_base = os.path.dirname(sys.executable)
else:
    dir_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sobe 1 nível

sys.path.append(dir_base)

from flask import Flask, render_template, request, redirect, url_for
from data.db import Materiais, session
#region baseSistema
app = Flask(__name__)
app.debug = True #debug so qnd for fazer alterações e nn ter que rebuildar/rerodar o código
#integrar a um db ja existente
@app.route("/")#home page
def Home():
	return render_template("index.html")#retornar o arquivo html de home
#endregion baseSistema
#region test
@app.route("/test")#home page
def Test():
    print("fora do site")
    return render_template("a.html")
#endregion test

#region rodar
app.run(host="0.0.0.0",port=5000)