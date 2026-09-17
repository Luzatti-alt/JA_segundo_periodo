#region baseSistema
import sys,os
if getattr(sys, 'frozen', False):
    dir_base = os.path.dirname(sys.executable)
else:
    dir_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sobe 1 nível

sys.path.append(dir_base)

from flask import Flask, render_template, request, redirect, url_for,jsonify
from flasgger import Swagger, swag_from #swagger
from flask_cors import CORS
from flask_bcrypt import Bcrypt  # criptografia
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from data.db import Veiculo,Componentes,Materiais,Destinacao,ResiduoEspecial,DadoAtividade,FatorEmissao,FatorMaterialVirgem,ResultadoCalculo, session
app = Flask(__name__)
app.debug = True #debug so qnd for fazer alterações e nn ter que rebuildar/rerodar o código

bcrypt = Bcrypt(app)
#flask CORS permite aplicar a extensão CORS, permitindo acesso de todas as origens resolve o problema 'from origin 'null' has been blocked'(android)
CORS(app, origins=["*"])

app.config['SWAGGER'] = {
    'title': 'API Pegada de Carbono',
    'termsOfService': '',
    'description': 'Documentação da API de pegada de carbono',
    'version': '0.0.1',
}
Swagger(app)  # fica em /apidocs

engine = create_engine('sqlite:///dbtest.db', echo=True)
Session = sessionmaker(bind=engine)
def get_session():
    return Session()
#endregion baseSistema

#region Interface
#interface farei dps
@app.route("/", methods=["GET"])#home page
def Home():
	return render_template("index.html")#retornar o arquivo html de home
#endregion Interface

#region DadosJsonPost

#region AddDados

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
            Estado=dados.get("estado", "Fim de vida"),
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


@app.route("/Destinacao", methods=["POST"])
@swag_from("docs/DestinacaoPost.yml")
def criar_destinacao():
    session = get_session()
    dados = request.get_json()
    try:
        destinacao = Destinacao(
            veiculo_id=dados.get("veiculo_id"),
            material_id=dados.get("material_id"),
            Cenario=dados.get("cenario", "base"),
            PctReciclagem=dados.get("pct_reciclagem", 0.0),
            PctReuso=dados.get("pct_reuso", 0.0),
            PctValorizacao=dados.get("pct_valorizacao", 0.0),
            PctDisposicao=dados.get("pct_disposicao", 0.0),
        )
        session.add(destinacao)
        session.commit()
        resultado = {
            "id": destinacao.id,
            "veiculo_id": destinacao.veiculo_id,
            "material_id": destinacao.material_id,
            "cenario": destinacao.Cenario,
            "pct_reciclagem": destinacao.PctReciclagem,
            "pct_reuso": destinacao.PctReuso,
            "pct_valorizacao": destinacao.PctValorizacao,
            "pct_disposicao": destinacao.PctDisposicao,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()


@app.route("/ResiduoEspecial", methods=["POST"])
@swag_from("docs/ResiduoEspecialPost.yml")
def criar_residuo_especial():
    session = get_session()
    dados = request.get_json()
    try:
        residuo = ResiduoEspecial(
            veiculo_id=dados.get("veiculo_id"),
            Nome=dados.get("nome"),
            Quantidade=dados.get("quantidade"),
            Unidade=dados.get("unidade"),
            Destino=dados.get("destino"),
        )
        session.add(residuo)
        session.commit()
        resultado = {
            "id": residuo.id,
            "veiculo_id": residuo.veiculo_id,
            "nome": residuo.Nome,
            "quantidade": residuo.Quantidade,
            "unidade": residuo.Unidade,
            "destino": residuo.Destino,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()


@app.route("/DadoAtividade", methods=["POST"])
@swag_from("docs/DadoAtividadePost.yml")
def criar_dado_atividade():
    session = get_session()
    dados = request.get_json()
    try:
        atividade = DadoAtividade(
            veiculo_id=dados.get("veiculo_id"),
            Cenario=dados.get("cenario", "base"),
            Processo=dados.get("processo"),
            Valor=dados.get("valor"),
            Unidade=dados.get("unidade"),
        )
        session.add(atividade)
        session.commit()
        resultado = {
            "id": atividade.id,
            "veiculo_id": atividade.veiculo_id,
            "cenario": atividade.Cenario,
            "processo": atividade.Processo,
            "valor": atividade.Valor,
            "unidade": atividade.Unidade,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()


@app.route("/FatorEmissao", methods=["POST"])
@swag_from("docs/FatorEmissaoPost.yml")
def criar_fator_emissao():
    session = get_session()
    dados = request.get_json()
    try:
        fator = FatorEmissao(
            material_id=dados.get("material_id"),  # pode vir None p/ fatores genéricos
            Processo=dados.get("processo"),
            Valor=dados.get("valor"),
            Unidade=dados.get("unidade"),
            Origem=dados.get("origem"),
        )
        session.add(fator)
        session.commit()
        resultado = {
            "id": fator.id,
            "material_id": fator.material_id,
            "processo": fator.Processo,
            "valor": fator.Valor,
            "unidade": fator.Unidade,
            "origem": fator.Origem,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()


@app.route("/FatorMaterialVirgem", methods=["POST"])
@swag_from("docs/FatorMaterialVirgemPost.yml")
def criar_fator_material_virgem():
    session = get_session()
    dados = request.get_json()
    try:
        fator = FatorMaterialVirgem(
            material_id=dados.get("material_id"),
            FEVirgem=dados.get("fe_virgem"),
            FD=dados.get("fd"),
        )
        session.add(fator)
        session.commit()
        resultado = {
            "id": fator.id,
            "material_id": fator.material_id,
            "fe_virgem": fator.FEVirgem,
            "fd": fator.FD,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()


@app.route("/ResultadoCalculo", methods=["POST"])
@swag_from("docs/ResultadoCalculoPost.yml")
def criar_resultado_calculo():
    session = get_session()
    dados = request.get_json()
    try:
        resultado_calculo = ResultadoCalculo(
            veiculo_id=dados.get("veiculo_id"),
            Cenario=dados.get("cenario", "base"),
            Etapa=dados.get("etapa"),
            EmissaoKgCO2e=dados.get("emissao_kgco2e"),
            ParticipacaoPct=dados.get("participacao_pct"),
            EvitadoKgCO2e=dados.get("evitado_kgco2e"),
        )
        session.add(resultado_calculo)
        session.commit()
        resultado = {
            "id": resultado_calculo.id,
            "veiculo_id": resultado_calculo.veiculo_id,
            "cenario": resultado_calculo.Cenario,
            "etapa": resultado_calculo.Etapa,
            "emissao_kgco2e": resultado_calculo.EmissaoKgCO2e,
            "participacao_pct": resultado_calculo.ParticipacaoPct,
            "evitado_kgco2e": resultado_calculo.EvitadoKgCO2e,
        }
        return jsonify(resultado), 201
    except Exception as e:
        session.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        session.close()

#endRegion AddDados

#endregion DadosJsonPost

#region DadosJsonGET

@app.route("/Veiculo", methods=["GET"])
@swag_from("docs/VeiculoGet.yml")
def listar_veiculos():
    session = get_session()
    veiculos = session.query(Veiculo).all()

    ListaVeiculos = [
        {
            "id": v.id,
            "categoria": v.Categoria,
            "motorizacao": v.Motorizacao,
            "combustivel": v.Combustivel,
            "massa_total_kg": v.MassaTotal,
            "vida_util_anos": v.VidaUtilAnos,
            "quilometragem_km": v.Quilometragem,
            "estado": v.Estado,
        }
        for v in veiculos
    ]

    session.close()
    return jsonify(ListaVeiculos)


@app.route("/Componentes", methods=["GET"])
@swag_from("docs/ComponentesGet.yml")
def listar_componentes():
    session = get_session()
    componentes = session.query(Componentes).all()
    ListaComponentes = [
        {
            "id": c.id,
            "veiculo_id": c.veiculo_id,
            "categoria": c.Categoria,
            "peso_kg": c.Peso,
        }
        for c in componentes
    ]

    session.close()
    return jsonify(ListaComponentes)


@app.route("/Materiais", methods=["GET"])

@swag_from("docs/MateriaisGet.yml")
def listar_materiais():
    session = get_session()
    materiais = session.query(Materiais).all()

    ListaMateriais = [
        {
            "id": m.id,
            "veiculo_id": m.veiculo_id,
            "categoria": m.Categoria,
            "peso_kg": m.Peso,
        }
        for m in materiais
    ]

    session.close()
    return jsonify(ListaMateriais)


@app.route("/Destinacao", methods=["GET"])
@swag_from("docs/DestinacaoGet.yml")
def listar_destinacoes():
    session = get_session()
    destinacoes = session.query(Destinacao).all()

    ListaDestinacoes = [
        {
            "id": d.id,
            "veiculo_id": d.veiculo_id,
            "material_id": d.material_id,
            "cenario": d.Cenario,
            "pct_reciclagem": d.PctReciclagem,
            "pct_reuso": d.PctReuso,
            "pct_valorizacao": d.PctValorizacao,
            "pct_disposicao": d.PctDisposicao,
        }
        for d in destinacoes
    ]

    session.close()
    return jsonify(ListaDestinacoes)


@app.route("/ResiduoEspecial", methods=["GET"])
@swag_from("docs/ResiduoEspecialGet.yml")
def listar_residuos_especiais():
    session = get_session()
    residuos = session.query(ResiduoEspecial).all()

    ListaResiduos = [
        {
            "id": r.id,
            "veiculo_id": r.veiculo_id,
            "nome": r.Nome,
            "quantidade": r.Quantidade,
            "unidade": r.Unidade,
            "destino": r.Destino,
        }
        for r in residuos
    ]

    session.close()
    return jsonify(ListaResiduos)


@app.route("/DadoAtividade", methods=["GET"])
@swag_from("docs/DadoAtividadeGet.yml")
def listar_dados_atividade():
    session = get_session()
    atividades = session.query(DadoAtividade).all()

    ListaAtividades = [
        {
            "id": a.id,
            "veiculo_id": a.veiculo_id,
            "cenario": a.Cenario,
            "processo": a.Processo,
            "valor": a.Valor,
            "unidade": a.Unidade,
        }
        for a in atividades
    ]

    session.close()
    return jsonify(ListaAtividades)


@app.route("/FatorEmissao", methods=["GET"])
@swag_from("docs/FatorEmissaoGet.yml")
def listar_fatores_emissao():
    session = get_session()
    fatores = session.query(FatorEmissao).all()

    ListaFatores = [
        {
            "id": f.id,
            "material_id": f.material_id,
            "processo": f.Processo,
            "valor": f.Valor,
            "unidade": f.Unidade,
            "origem": f.Origem,
        }
        for f in fatores
    ]

    session.close()
    return jsonify(ListaFatores)


@app.route("/FatorMaterialVirgem", methods=["GET"])
@swag_from("docs/FatorMaterialVirgemGet.yml")
def listar_fatores_material_virgem():
    session = get_session()
    fatores = session.query(FatorMaterialVirgem).all()

    ListaFatoresVirgem = [
        {
            "id": f.id,
            "material_id": f.material_id,
            "fe_virgem": f.FEVirgem,
            "fd": f.FD,
        }
        for f in fatores
    ]

    session.close()
    return jsonify(ListaFatoresVirgem)


@app.route("/ResultadoCalculo", methods=["GET"])
@swag_from("docs/ResultadoCalculoGet.yml")
def listar_resultados_calculo():
    session = get_session()
    resultados = session.query(ResultadoCalculo).all()

    ListaResultados = [
        {
            "id": r.id,
            "veiculo_id": r.veiculo_id,
            "cenario": r.Cenario,
            "etapa": r.Etapa,
            "emissao_kgco2e": r.EmissaoKgCO2e,
            "participacao_pct": r.ParticipacaoPct,
            "evitado_kgco2e": r.EvitadoKgCO2e,
        }
        for r in resultados
    ]

    session.close()
    return jsonify(ListaResultados)

#endregion DadosJsonGET

#region rodar
app.run(host="0.0.0.0",port=5000)