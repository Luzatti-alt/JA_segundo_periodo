#region baseSistema
import sys, os
from io import BytesIO
if getattr(sys, 'frozen', False):
    dir_base = os.path.dirname(sys.executable)
else:
    dir_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sobe 1 nível

sys.path.append(dir_base)

from flask import Flask, render_template, request, jsonify, send_file, abort, url_for
from flasgger import Swagger, swag_from  # swagger em /apidocs
from flask_cors import CORS
from sqlalchemy import func, create_engine, or_, cast, String

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
import qrcode

from app.data.db import session, Session, ModeloVeiculo, Veiculo, Pecas, Materiais, QRFiles, AtividadeVeiculo, DestinoMaterial, FatorEmissao 
from app.data.db import (CatalogoMaterial, CatalogoAlias, MaterialGrupo, ModeloComponente,
                         ComposicaoVeiculo, ResolverMaterial)
from datetime import datetime
from app.services import Inventario
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

def GetSession():
    return Session()

def LerNumero(valor, campo):
    #(float|None, erro|None). Vazio vira None; texto não numérico e valor negativo são erro
    if valor is None or valor == "":
        return None, None
    try:
        n = float(valor) if not isinstance(valor, bool) else None
    except (TypeError, ValueError):
        n = None
    if n is None:
        return None, f"{campo} deve ser um número"
    if n < 0:
        return None, f"{campo} não pode ser negativo"
    return n, None

def ErroComposicao(erros):
    resumo = "; ".join(erros[:3]) + (f" (+{len(erros) - 3})" if len(erros) > 3 else "")
    return jsonify({"erro": resumo, "erros": erros}), 400

ORIGENS_DADOS = ("real", "exemplo", "referencia_pdf", "nao_informado")

def GarantirQRs():
    #Todo veículo e toda peça ativa precisam ter QR. Idempotente
    with Session() as s:
        for v in s.query(Veiculo).filter(~Veiculo.qrs.any(), Veiculo.removido_em.is_(None)).all():
            QR.Gerar(data=f"{v.veiculo} {v.Modelo} | Chassi: {v.Chassi}", veiculo_id=v.id)
        for p in s.query(Pecas).filter(~Pecas.qrs.any(), Pecas.removido_em.is_(None)).all():
            QR.Gerar(data=f"Peça: {p.Categoria} | {p.Peso} kg", peca_id=p.id)
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
    with Session() as s:
        registro = s.get(QRFiles, qr_id)
        if registro is None:
            abort(404)
        return render_template("QRGerado.html", qrs=[registro], filtros=OpcoesFiltro(s))

@app.route("/Calculos", methods=['GET'])
def Calculos():
    return render_template("Calculos.html")

@app.route("/CatalogoMateriais", methods=['GET'])      # a API do catálogo é /Catalogo; esta é só a página
def CatalogoPagina():
    return render_template("Catalogo.html")

@app.route("/Inventario", methods=['GET'])             # nome InventarioPagina para não esconder o módulo services.Inventario
def InventarioPagina():
    return render_template("InventarioVeiculo.html")

#endregion Interface
#region QR
def FiltrarQRs(s):
    #Query de QRs filtrada por ?q= (várias palavras, todas precisam casar), ?estado=, ?ano=, ?categoria=.
    q = s.query(QRFiles).outerjoin(Veiculo, QRFiles.veiculo_id == Veiculo.id)
    q = q.filter(or_(QRFiles.veiculo_id.is_(None), Veiculo.removido_em.is_(None)))   # QR de veículo removido não lista
    for palavra in (request.args.get("q") or "").split():
        like = f"%{palavra.lstrip('#')}%"
        cond = [Veiculo.veiculo.ilike(like), Veiculo.Modelo.ilike(like), Veiculo.Chassi.ilike(like),
                Veiculo.CategoriaVeiculo.ilike(like), Veiculo.Estado.ilike(like),
                cast(Veiculo.Ano, String).ilike(like), QRFiles.data.ilike(like)]
        if palavra.lstrip("#").isdigit():
            n = int(palavra.lstrip("#"))
            cond += [QRFiles.id == n, Veiculo.id == n]
        q = q.filter(or_(*cond))
    if request.args.get("estado"):
        q = q.filter(Veiculo.Estado == request.args["estado"])
    if request.args.get("ano"):
        q = q.filter(cast(Veiculo.Ano, String) == request.args["ano"])
    if request.args.get("categoria"):
        q = q.filter(Veiculo.CategoriaVeiculo == request.args["categoria"])
    return q.order_by(QRFiles.id)
 
def OpcoesFiltro(s):
    col = lambda c: sorted({x[0] for x in s.query(c).distinct() if x[0] not in (None, "")}, key=str)
    return {"estados": col(Veiculo.Estado), "anos": col(Veiculo.Ano), "categorias": col(Veiculo.CategoriaVeiculo)}
 
@app.route("/QR", methods=["GET"])
@app.route("/qr", methods=["GET"])
def QRLista():
    with Session() as s:
        qrs = FiltrarQRs(s).all()
        return render_template("QRGerado.html", qrs=qrs, filtros=OpcoesFiltro(s))
 
@app.route("/QR/buscar", methods=["GET"])          # JSON para campos de busca/autocomplete
@swag_from("data/doc/swagger/QRBuscar.yml")
def QRBuscar():
    limite = min(request.args.get("limite", 30, type=int), 100)
    with Session() as s:
        itens = []
        for r in FiltrarQRs(s).limit(limite).all():
            v = r.veiculo
            itens.append({"id": r.id, "veiculo_id": r.veiculo_id,
                          "titulo": f"{v.veiculo} {v.Modelo}" if v else (r.data or f"QR #{r.id}"),
                          "chassi": v.Chassi if v else None, "ano": v.Ano if v else None,
                          "estado": v.Estado if v else None,
                          "imagem": url_for("QRImagem", qr_id=r.id),
                          "pdf": url_for("DownloadPDF", qr_id=r.id)})
        return jsonify(itens)
 
 
@app.route("/QR/<int:qr_id>/imagem", methods=["GET"])
@swag_from("data/doc/swagger/QRImagem.yml")
def QRImagem(qr_id):
    with Session() as s:
        registro = s.get(QRFiles, qr_id)
        if registro is None:
            abort(404)
        codigo = registro.codigo
    baixar = request.args.get("baixar") in ("1", "true", "sim")
    resp = send_file(QR.Png(QR.BaseUrl(request.host), codigo), mimetype="image/png",
                     as_attachment=baixar, download_name=f"qr_{qr_id}.png")
    resp.headers["Cache-Control"] = "no-store"     # o conteúdo muda se o IP da máquina mudar
    return resp
 
@app.route("/q/<codigo>", methods=["GET"])  # rota que o QR aponta (codigo permanente, não sequencial)
def QRPorCodigo(codigo):
    pdf = QR.QrLido(codigo=codigo)
    if pdf is None:
        abort(404)
    return send_file(pdf, mimetype="application/pdf",
                     download_name=f"relatorio_{codigo[:8]}.pdf", as_attachment=False)

@app.route("/download/<int:qr_id>", methods=["GET"])  # legado: QRs já impressos apontam para cá
@swag_from("data/doc/swagger/DownloadPDF.yml")
def DownloadPDF(qr_id):
    pdf = QR.QrLido(qr_id=qr_id)
    if pdf is None:
        abort(404)
    return send_file(pdf, mimetype="application/pdf",
                     download_name=f"relatorio_qr_{qr_id}.pdf", as_attachment=True)

#endregion QR

#region dados
#region ler
@app.route("/VeiculoModelo", methods=["GET"])
@swag_from("data/doc/swagger/VeiculoModeloGet.yml")
def ListarVeiculoModelo():
    s = GetSession()
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
            # snake_case (as chaves com espaço acima ficam até o JS ser adaptado)
            "massa_total_kg": m.MassaTotal,
            "vida_util_anos": m.VidaUtilAnos,
            "quilometragem_km": m.Kilometragem,
            "quantidade_por_modelos": m.QuantidadePorModelos,
        } for m in s.query(ModeloVeiculo).all()])
    finally:
        s.close()

@app.route("/Veiculo", methods=["GET"])
@swag_from("data/doc/swagger/VeiculoGet.yml")
def ListarVeiculos():
    s = GetSession()
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
            "quantidade Pecas": len([p for p in v.pecas if p.removido_em is None]),
            "estado": v.Estado,
            "massa_total_kg": v.MassaTotal,
            "vida_util_anos": v.VidaUtilAnos,
            "quantidade_pecas": len([p for p in v.pecas if p.removido_em is None]),
            "fonte_composicao": v.fonte_composicao,
            "origem_dados": v.origem_dados,
            "motorizacao": v.motorizacao,
            "combustivel": v.combustivel,
        } for v in s.query(Veiculo).filter(Veiculo.removido_em.is_(None)).all()])
    finally:
        s.close()

@app.route("/Materiais", methods=["GET"])
@swag_from("data/doc/swagger/MateriaisGet.yml")
def ListarMateriais():
    s = GetSession()
    try:
        return jsonify([{
            "id": m.id,
            "peca_id": m.peca_id,
            "categoria": m.Categoria,
            "peso kg": m.Peso,
            "peso_kg": m.Peso,
            "item_uid": m.item_uid,
        } for m in s.query(Materiais).join(Pecas, Materiais.peca_id == Pecas.id)
                                    .filter(Pecas.removido_em.is_(None)).all()])
    finally:
        s.close()

def ComponenteJSON(p, v, catalogo):
    return {
        "id": p.id,
        "id do veiculo": v.id,
        "veiculo_id": p.veiculo_id,
        "modelo veiculo da peca": v.Modelo,
        "categoria": p.Categoria,
        "peso kg": p.Peso,
        "peso_kg": p.Peso,
        "modelo_veiculo": v.Modelo,
        "massa_origem": p.massa_origem,
        "codigo_peca": p.codigo_peca,
        "fornecedor": p.fornecedor,
        "composicao": p.composicao,           # None = composição não informada
        "indicadores": Inventario.IndicadoresPeca(p, catalogo),
    }

@app.route("/Componentes", methods=["GET"])
@swag_from("data/doc/swagger/ComponentesGet.yml")
def ListarComponentes():
    s = GetSession()
    try:
        catalogo = Inventario.StatusCatalogo(s)
        tipos = (s.query(Pecas, Veiculo)
                .join(Veiculo, Pecas.veiculo_id == Veiculo.id)
                .filter(Pecas.removido_em.is_(None))
                .all())
        return jsonify([ComponenteJSON(p, v, catalogo) for p, v in tipos])
    finally:
        s.close()

@app.route("/Componentes/<int:peca_id>", methods=["GET"])
@swag_from("data/doc/swagger/ComponenteGetUm.yml")
def LerComponente(peca_id):
    s = GetSession()
    try:
        p = s.get(Pecas, peca_id)
        if p is None or p.removido_em is not None:
            return jsonify({"erro": "Componente não encontrado"}), 404
        return jsonify(ComponenteJSON(p, p.veiculo, Inventario.StatusCatalogo(s)))
    finally:
        s.close()

#endregion ler

#region post
@app.route("/VeiculoModelo", methods=["POST"])
@swag_from("data/doc/swagger/VeiculoModeloPost.yml")
def CriarVeiculoModelo():
    s = GetSession()
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
@swag_from("data/doc/swagger/veiculoCriar.yml")
def CriarVeiculo():
    s = GetSession()
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
            motorizacao=dados.get("motorizacao") or None,
            combustivel=dados.get("combustivel") or None,
        )
        origem = dados.get("origem_dados") or "real" or "real"
        if origem not in ORIGENS_DADOS:
            return jsonify({"erro": f"origem_dados deve ser um de {', '.join(ORIGENS_DADOS)}"}), 400
        veiculo.origem_dados = origem
        fonte = dados.get("fonte_composicao")
        if fonte:
            if fonte not in Inventario.FONTES_COMPOSICAO:
                return jsonify({"erro": "fonte_composicao deve ser por_peca ou agregada"}), 400
            veiculo.fonte_composicao = fonte
        s.add(veiculo)
        s.flush()
        copiadas = 0
        if modelo_id and dados.get("copiar_inventario", True):
            # valores de REFERÊNCIA do modelo (massa_origem='referencia'), a confirmar na inspeção
            copiadas = Inventario.CopiarInventarioModelo(s, s.get(ModeloVeiculo, modelo_id), veiculo)
        s.commit()
        novo_id = veiculo.id
        s.close()
        GarantirQRs()      # QR do veículo e das peças copiadas
        return jsonify({"id": novo_id, "pecas_copiadas": copiadas}), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Componentes", methods=["POST"])
@swag_from("data/doc/swagger/ComponentesPost.yml")
def CriarComponente():
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        alvo = s.get(Veiculo, dados["veiculo_id"]) if dados.get("veiculo_id") else None
        if alvo is None or alvo.removido_em is not None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        peso, erro = LerNumero(dados.get("peso_kg"), "peso_kg")
        if erro:
            return jsonify({"erro": erro}), 400
        origem = dados.get("massa_origem") or "nao_informado"
        if origem not in Inventario.ORIGENS_MASSA:
            return jsonify({"erro": f"massa_origem deve ser um de {', '.join(Inventario.ORIGENS_MASSA)}"}), 400
        itens, erros, alertas = Inventario.NormalizarComposicao(s, dados.get("composicao"), peso)
        if erros:
            return ErroComposicao(erros)
        componente = Pecas(
            veiculo_id=dados.get("veiculo_id"),
            Categoria=dados.get("categoria"),
            Peso=peso,
            composicao=itens,
            massa_origem=origem,
            codigo_peca=dados.get("codigo_peca"),
            fornecedor=dados.get("fornecedor"),
        )
        s.add(componente)
        s.commit()
        resposta = {"id": componente.id, "alertas": alertas,
                    "indicadores": Inventario.IndicadoresPeca(componente, Inventario.StatusCatalogo(s))}
        s.close()
        GarantirQRs()      # a peça nasce com QR
        return jsonify(resposta), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Materiais", methods=["POST"])
@swag_from("data/doc/swagger/MateriaisPost.yml")
def CriarMaterial():
    # Material = lote físico de uma peça; o item correspondente em Pecas.composicao é mantido junto
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        if not dados.get("peca_id") or s.get(Pecas, dados["peca_id"]) is None:
            return jsonify({"erro": "Peça não encontrada"}), 404
        peso, erro = LerNumero(dados.get("peso_kg"), "peso_kg")
        if erro or peso is None:
            return jsonify({"erro": erro or "Informe peso_kg"}), 400
        material = Materiais(
            peca_id=dados.get("peca_id"),   # estava dados.get("veiculo_id")
            Categoria=dados.get("categoria"),
            Peso=peso,
            item_uid=Inventario.NovoUid(),
        )
        s.add(material)
        s.flush()
        erros, alertas = Inventario.SincronizarLote(s, material)
        if erros:
            s.rollback()
            return ErroComposicao(erros)
        s.commit()
        return jsonify({"id": material.id, "alertas": alertas}), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion post

#region put
@app.route("/VeiculoModelo/<int:modelo_id>", methods=["PUT"])
@swag_from("data/doc/swagger/VeiculoModeloPut.yml") 
def EditarVeiculoModelo(modelo_id):
    s = GetSession()
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
@swag_from("data/doc/swagger/VeiculoPut.yml") 
def EditarVeiculo(veiculo_id):
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        v = s.get(Veiculo, veiculo_id)
        if v is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        if v.removido_em is not None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        if "fonte_composicao" in dados and dados["fonte_composicao"] not in Inventario.FONTES_COMPOSICAO:
            return jsonify({"erro": "fonte_composicao deve ser por_peca ou agregada"}), 400
        if "origem_dados" in dados and dados["origem_dados"] not in ORIGENS_DADOS:
            return jsonify({"erro": f"origem_dados deve ser um de {', '.join(ORIGENS_DADOS)}"}), 400
        campos = {
            "veiculo": "veiculo", "modelo": "Modelo", "chassi": "Chassi", "ano": "Ano",
            "categoria": "CategoriaVeiculo", "massa_total_kg": "MassaTotal",
            "vida_util_anos": "VidaUtilAnos", "quilometragem_km": "Kilometragem",
            "estado": "Estado", "fonte_composicao": "fonte_composicao",
            "origem_dados": "origem_dados", "motorizacao": "motorizacao", "combustivel": "combustivel",
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
@swag_from("data/doc/swagger/ComponentesPut.yml")
def EditarComponente(peca_id):
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        p = s.get(Pecas, peca_id)
        if p is None or p.removido_em is not None:
            return jsonify({"erro": "Componente não encontrado"}), 404
        if "veiculo_id" in dados and s.get(Veiculo, dados["veiculo_id"]) is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        peso = p.Peso
        if "peso_kg" in dados:
            peso, erro = LerNumero(dados["peso_kg"], "peso_kg")
            if erro:
                return jsonify({"erro": erro}), 400
        if "massa_origem" in dados and dados["massa_origem"] not in Inventario.ORIGENS_MASSA:
            return jsonify({"erro": f"massa_origem deve ser um de {', '.join(Inventario.ORIGENS_MASSA)}"}), 400
        alertas = []
        if "composicao" in dados or "peso_kg" in dados:   # revalida só quando algo disso mudou
            bruta = dados["composicao"] if "composicao" in dados else p.composicao
            itens, erros, alertas = Inventario.NormalizarComposicao(s, bruta, peso)
            if erros:
                return ErroComposicao(erros)
            erros = Inventario.ReconciliarLotes(s, p, itens)    # lotes (Materiais) acompanham o JSON
            if erros:
                s.rollback()
                return ErroComposicao(erros)
            p.composicao = itens
        p.veiculo_id = dados.get("veiculo_id", p.veiculo_id)
        p.Categoria = dados.get("categoria", p.Categoria)
        p.Peso = peso
        for campo, atributo in (("massa_origem", "massa_origem"), ("codigo_peca", "codigo_peca"),
                                ("fornecedor", "fornecedor")):
            if campo in dados:
                setattr(p, atributo, dados[campo])
        s.commit()
        return jsonify({"id": p.id, "alertas": alertas,
                        "indicadores": Inventario.IndicadoresPeca(p, Inventario.StatusCatalogo(s))}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Materiais/<int:material_id>", methods=["PUT"])
@swag_from("data/doc/swagger/MateriaisPut.yml")
def EditarMaterial(material_id):
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        m = s.get(Materiais, material_id)
        if m is None:
            return jsonify({"erro": "Material não encontrado"}), 404
        anterior = m.pecas
        if "peca_id" in dados and s.get(Pecas, dados["peca_id"]) is None:
            return jsonify({"erro": "Peça não encontrada"}), 404
        if "peso_kg" in dados:
            peso, erro = LerNumero(dados["peso_kg"], "peso_kg")
            if erro or peso is None:
                return jsonify({"erro": erro or "Informe peso_kg"}), 400
            m.Peso = peso
        m.peca_id = dados.get("peca_id", m.peca_id)
        m.Categoria = dados.get("categoria", m.Categoria)
        s.flush()
        s.refresh(m)                      # recarrega m.pecas caso a peça tenha mudado
        erros, alertas = Inventario.SincronizarLote(s, m, peca_anterior=anterior)
        if erros:
            s.rollback()
            return ErroComposicao(erros)
        s.commit()
        return jsonify({"id": m.id, "alertas": alertas}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion put

#region delete
@app.route("/VeiculoModelo/<int:modelo_id>", methods=["DELETE"])
@swag_from("data/doc/swagger/VeiculoModeloDelete.yml")
def RemoverVeiculoModelo(modelo_id):
    s = GetSession()
    try:
        m = s.get(ModeloVeiculo, modelo_id)
        if m is None:
            return jsonify({"erro": "Modelo não encontrado"}), 404
        ids = [c.id for c in m.componentes_ref]
        if ids:   # com FK ativa, as peças copiadas precisam soltar a referência antes
            s.query(Pecas).filter(Pecas.modelo_componente_id.in_(ids)).update(
                {Pecas.modelo_componente_id: None}, synchronize_session=False)
        s.delete(m)   # os veículos ligados ficam, só perdem o modelo_id
        s.commit()
        return "", 204
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Veiculo/<int:veiculo_id>", methods=["DELETE"])
@swag_from("data/doc/swagger/VeiculoDelete.yml")
def RemoverVeiculo(veiculo_id):
    s = GetSession()
    try:
        v = s.get(Veiculo, veiculo_id)
        if v is None or v.removido_em is not None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        # remoção LÓGICA: histórico, QR e peças ficam preservados (o QR continua resolvendo, marcado como removido)
        v.removido_em = datetime.now()
        for p in v.pecas:
            if p.removido_em is None:
                p.removido_em = v.removido_em
        s.commit()
        return "", 204
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Materiais/<int:material_id>", methods=["DELETE"])
@swag_from("data/doc/swagger/MateriaisDelete.yml")
def RemoverMeterial(material_id):
    s = GetSession()
    try:
        m = s.get(Materiais, material_id)
        if m is None:
            return jsonify({"erro": "Material não encontrado"}), 404
        Inventario.SincronizarLote(s, m, remover=True)   # tira o item da composição da peça
        s.delete(m)
        s.commit()
        return jsonify({"ok": True}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Componentes/<int:peca_id>", methods=["DELETE"])
@swag_from("data/doc/swagger/ComponentesDelete.yml")
def RemoverComponente(peca_id):
    s = GetSession()
    try:
        p = s.get(Pecas, peca_id)
        if p is None or p.removido_em is not None:
            return jsonify({"erro": "Componente não encontrado"}), 404
        p.removido_em = datetime.now()      # remoção lógica (composição e lotes ficam preservados)
        s.commit()
        return jsonify({"ok": True}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion delete

#region inventario
@app.route("/Veiculo/<int:veiculo_id>/inventario", methods=["GET"])
@swag_from("data/doc/swagger/VeiculoInventario.yml")
def InventarioVeiculo(veiculo_id):
    # cobertura da composição; resultado_integral=false indica que qualquer cálculo será PARCIAL
    s = GetSession()
    try:
        v = s.get(Veiculo, veiculo_id)
        if v is None:
            return jsonify({"erro": "Veículo não encontrado"}), 404
        return jsonify(Inventario.IndicadoresVeiculo(s, v))
    finally:
        s.close()

def ComponenteModeloJSON(c):
    return {"id": c.id, "modelo_id": c.modelo_id, "categoria": c.categoria, "massa_ref_kg": c.massa_ref_kg,
            "composicao_ref": c.composicao_ref, "codigo_peca": c.codigo_peca,
            "fornecedor": c.fornecedor, "origem": c.origem}

def AplicarComponenteModelo(s, c, dados):
    #Valida e aplica os campos de um ModeloComponente. Devolve (resposta_de_erro|None, alertas).#
    if "categoria" in dados:
        c.categoria = (dados["categoria"] or "").strip() or None
    if not c.categoria:
        return (jsonify({"erro": "Informe a categoria do componente"}), 400), []
    if "massa_ref_kg" in dados:
        c.massa_ref_kg, erro = LerNumero(dados["massa_ref_kg"], "massa_ref_kg")
        if erro:
            return (jsonify({"erro": erro}), 400), []
    alertas = []
    if "composicao_ref" in dados or "massa_ref_kg" in dados:
        bruta = dados["composicao_ref"] if "composicao_ref" in dados else c.composicao_ref
        itens, erros, alertas = Inventario.NormalizarComposicao(s, bruta, c.massa_ref_kg)
        if erros:
            return ErroComposicao(erros), []
        c.composicao_ref = itens
    for campo in ("codigo_peca", "fornecedor"):
        if campo in dados:
            setattr(c, campo, dados[campo])
    return None, alertas

@app.route("/VeiculoModelo/<int:modelo_id>/componentes", methods=["GET"])
@swag_from("data/doc/swagger/ModeloComponentesGet.yml")
def ListarComponentesModelo(modelo_id):
    s = GetSession()
    try:
        m = s.get(ModeloVeiculo, modelo_id)
        if m is None:
            return jsonify({"erro": "Modelo não encontrado"}), 404
        return jsonify([ComponenteModeloJSON(c) for c in m.componentes_ref])
    finally:
        s.close()

@app.route("/VeiculoModelo/<int:modelo_id>/componentes", methods=["POST"])
@swag_from("data/doc/swagger/ModeloComponentesPost.yml")
def CriarComponenteModelo(modelo_id):
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        if s.get(ModeloVeiculo, modelo_id) is None:
            return jsonify({"erro": "Modelo não encontrado"}), 404
        c = ModeloComponente(modelo_id=modelo_id)
        resposta, alertas = AplicarComponenteModelo(s, c, dados)
        if resposta:
            s.rollback()
            return resposta
        s.add(c)
        s.commit()
        return jsonify({"id": c.id, "alertas": alertas}), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/ModeloComponentes/<int:comp_id>", methods=["PUT"])
@swag_from("data/doc/swagger/ModeloComponentesPut.yml")
def EditarComponenteModelo(comp_id):
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        c = s.get(ModeloComponente, comp_id)
        if c is None:
            return jsonify({"erro": "Componente do modelo não encontrado"}), 404
        resposta, alertas = AplicarComponenteModelo(s, c, dados)
        if resposta:
            s.rollback()
            return resposta
        s.commit()
        return jsonify({"id": c.id, "alertas": alertas}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/ModeloComponentes/<int:comp_id>", methods=["DELETE"])
@swag_from("data/doc/swagger/ModeloComponentesDelete.yml")
def RemoverComponenteModelo(comp_id):
    s = GetSession()
    try:
        c = s.get(ModeloComponente, comp_id)
        if c is None:
            return jsonify({"erro": "Componente do modelo não encontrado"}), 404
        s.query(Pecas).filter(Pecas.modelo_componente_id == comp_id).update({Pecas.modelo_componente_id: None})
        s.delete(c)   # as peças já copiadas ficam; só perdem a ligação com a referência
        s.commit()
        return "", 204
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion inventario

#region catalogo
STATUS_CATALOGO = ("classificado", "nao_classificado", "outros_declarado")

def MaterialCatalogoJSON(m):
    return {"id": m.id, "nome": m.nome, "unidade_ref": m.unidade_ref, "descricao": m.descricao,
            "status": m.status, "processos": m.processos or [], "ativo": bool(m.ativo),
            "aliases": sorted(a.alias for a in m.aliases),
            "grupos": {g.esquema: g.grupo for g in m.grupos}}

def AplicarCatalogo(s, m, dados):
    nome = (dados.get("nome", m.nome) or "").strip()
    if not nome:
        return jsonify({"erro": "Informe o nome do material"}), 400
    outro = s.query(CatalogoMaterial).filter(CatalogoMaterial.nome == nome, CatalogoMaterial.id != (m.id or 0)).first()
    if outro:
        return jsonify({"erro": f"Já existe o material '{nome}'"}), 409

    # aliases desejados = nome + (aliases enviados | os atuais), sem repetir pela forma normalizada
    atuais = [a.alias for a in m.aliases]
    pedidos = dados["aliases"] if "aliases" in dados else atuais
    if not isinstance(pedidos, list) or not all(isinstance(a, str) for a in pedidos):
        return jsonify({"erro": "aliases deve ser uma lista de textos"}), 400
    desejados = {}
    for a in [nome, *pedidos]:
        if a.strip():
            desejados.setdefault(NormalizarNome(a), a.strip())
    for norm, alias in desejados.items():
        dono = s.query(CatalogoAlias).filter_by(alias_norm=norm).first()
        if dono and dono.material_id != m.id:
            return jsonify({"erro": f"'{alias}' já é nome/alias de '{dono.material.nome}'"}), 409

    grupos = m.grupos
    novos_grupos = {g.esquema: g.grupo for g in grupos}
    if "grupos" in dados:
        g = dados["grupos"]
        if not isinstance(g, dict) or not all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in g.items()):
            return jsonify({"erro": "grupos deve ser {esquema: grupo}"}), 400
        novos_grupos = dict(g)

    status = dados.get("status")
    if status is None:      # sem status explícito: acompanha os grupos (exceto "Outros" declarado)
        status = m.status or "nao_classificado"
        if "grupos" in dados and status != "outros_declarado":
            status = "classificado" if novos_grupos else "nao_classificado"
    if status not in STATUS_CATALOGO:
        return jsonify({"erro": f"status deve ser um de {', '.join(STATUS_CATALOGO)}"}), 400
    if status == "classificado" and not novos_grupos:
        return jsonify({"erro": "Material 'classificado' precisa de ao menos um grupo"}), 400
    processos = dados.get("processos", m.processos)
    if processos is not None and not (isinstance(processos, list) and all(isinstance(x, str) for x in processos)):
        return jsonify({"erro": "processos deve ser uma lista de textos"}), 400

    m.nome, m.status, m.processos = nome, status, processos
    for campo in ("unidade_ref", "descricao"):
        if campo in dados:
            setattr(m, campo, dados[campo])
    if "ativo" in dados:
        m.ativo = bool(dados["ativo"])
    # aliases e grupos por diferença (evita violar UNIQUE ao trocar linhas na mesma gravação)
    for a in list(m.aliases):
        if a.alias_norm not in desejados:
            m.aliases.remove(a)
    existentes = {a.alias_norm for a in m.aliases}
    for norm, alias in desejados.items():
        if norm not in existentes:
            m.aliases.append(CatalogoAlias(alias=alias, alias_norm=norm))
    for g in list(m.grupos):
        if g.esquema not in novos_grupos:
            m.grupos.remove(g)
        else:
            g.grupo = novos_grupos[g.esquema]
    ja = {g.esquema for g in m.grupos}
    for esquema, grupo in novos_grupos.items():
        if esquema not in ja:
            m.grupos.append(MaterialGrupo(esquema=esquema, grupo=grupo))
    return None

def NormalizarNome(txt):
    from app.data.db import _norm
    return _norm(txt)

def UsoMaterial(s, material_id):
    #Onde o material aparece (composições JSON, composição agregada, modelos).
    conta = lambda lista: sum(1 for c in lista if any(i.get("material_id") == material_id for i in (c or [])))
    return {"pecas": conta([p.composicao for p in s.query(Pecas).filter(Pecas.composicao.isnot(None))]),
            "modelos": conta([c.composicao_ref for c in s.query(ModeloComponente).filter(ModeloComponente.composicao_ref.isnot(None))]),
            "composicao_veiculo": s.query(ComposicaoVeiculo).filter_by(material_id=material_id).count()}

@app.route("/Catalogo", methods=["GET"])
@swag_from("data/doc/swagger/CatalogoGet.yml")
def ListarCatalogo():
    s = GetSession()
    try:
        q = s.query(CatalogoMaterial)
        if request.args.get("status"):
            q = q.filter(CatalogoMaterial.status == request.args["status"])
        if request.args.get("ativo") in ("0", "1"):
            q = q.filter(CatalogoMaterial.ativo == (request.args["ativo"] == "1"))
        itens = [MaterialCatalogoJSON(m) for m in q.order_by(CatalogoMaterial.nome).all()]
        busca = NormalizarNome(request.args.get("q") or "")
        if busca:
            itens = [i for i in itens if busca in NormalizarNome(i["nome"]) or any(busca in NormalizarNome(a) for a in i["aliases"])]
        return jsonify(itens)
    finally:
        s.close()

@app.route("/Catalogo/resolver", methods=["GET"])
@swag_from("data/doc/swagger/CatalogoResolver.yml")
def ResolverCatalogo():
    # só consulta: NÃO cria nada. Útil para o formulário avisar "material novo" antes de salvar.
    s = GetSession()
    try:
        m = ResolverMaterial(s, request.args.get("nome"), criar=False)
        return jsonify({"encontrado": m is not None, "material": MaterialCatalogoJSON(m) if m else None})
    finally:
        s.close()

@app.route("/Catalogo/<int:material_id>", methods=["GET"])
@swag_from("data/doc/swagger/CatalogoGetUm.yml")
def LerCatalogo(material_id):
    s = GetSession()
    try:
        m = s.get(CatalogoMaterial, material_id)
        if m is None:
            return jsonify({"erro": "Material não encontrado"}), 404
        return jsonify({**MaterialCatalogoJSON(m), "uso": UsoMaterial(s, material_id)})
    finally:
        s.close()

@app.route("/Catalogo", methods=["POST"])
@swag_from("data/doc/swagger/CatalogoPost.yml")
def CriarCatalogo():
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        m = CatalogoMaterial(nome="", status="nao_classificado")
        resposta = AplicarCatalogo(s, m, dados)
        if resposta:
            s.rollback()
            return resposta
        s.add(m)
        s.commit()
        return jsonify(MaterialCatalogoJSON(m)), 201
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Catalogo/<int:material_id>", methods=["PUT"])
@swag_from("data/doc/swagger/CatalogoPut.yml")
def EditarCatalogo(material_id):
    s = GetSession()
    dados = request.get_json(silent=True) or {}
    try:
        m = s.get(CatalogoMaterial, material_id)
        if m is None:
            return jsonify({"erro": "Material não encontrado"}), 404
        resposta = AplicarCatalogo(s, m, dados)
        if resposta:
            s.rollback()
            return resposta
        s.commit()
        return jsonify(MaterialCatalogoJSON(m))
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()

@app.route("/Catalogo/<int:material_id>", methods=["DELETE"])
@swag_from("data/doc/swagger/CatalogoDelete.yml")
def RemoverCatalogo(material_id):
    s = GetSession()
    try:
        m = s.get(CatalogoMaterial, material_id)
        if m is None:
            return jsonify({"erro": "Material não encontrado"}), 404
        uso = UsoMaterial(s, material_id)
        if any(uso.values()):
            return jsonify({"erro": "Material em uso; desative-o (ativo=false) em vez de apagar", "uso": uso}), 409
        s.delete(m)
        s.commit()
        return "", 204
    except Exception as e:
        s.rollback()
        return jsonify({"erro": str(e)}), 400
    finally:
        s.close()
#endregion catalogo
#region calculos
def Calc(veiculo_id, parte="resumo"):
    s = GetSession()
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
@swag_from("data/doc/swagger/CalculoResumo.yml")
def calculo_resumo(veiculo_id):
    return Calc(veiculo_id)
 
@app.route("/Calculos/<int:veiculo_id>/cenarios", methods=["GET"])
@swag_from("data/doc/swagger/CalculoCenarios.yml")       
def calculo_cenarios(veiculo_id):
    return Calc(veiculo_id, "cenarios")
 
@app.route("/Calculos/<int:veiculo_id>/sensibilidade", methods=["GET"])
@swag_from("data/doc/swagger/CalculoSensibilidade.yml")
def calculo_sensibilidade(veiculo_id):
    return Calc(veiculo_id, "sensibilidade")
 

@app.route("/Atividade/<int:veiculo_id>", methods=["GET"])
@swag_from("data/doc/swagger/AtividadeGet.yml")
def LerAtividade(veiculo_id):
    s = GetSession()
    try:
        atividade, _ = Calculo.Atividade(s, veiculo_id)
        return jsonify(atividade)
    finally:
        s.close()
 
@app.route("/Atividade/<int:veiculo_id>", methods=["PUT"])
@swag_from("data/doc/swagger/AtividadePut.yml")
def SalvarAtividade(veiculo_id):
    s = GetSession()
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
 
#destinos dos materiais (banco + padrão do PDF para o que faltar)
@app.route("/Destinos", methods=["GET"])
@swag_from("data/doc/swagger/DestinosGet.yml") 
def ListarDestinos():
    s = GetSession()
    try:
        _, destinos = Calculo.Parametros(s)
        return jsonify([{"material": g, "reciclagem": destinos[g][0], "reuso": destinos[g][1],
                         "valorizacao": destinos[g][2], "disposicao": destinos[g][3]}
                        for g in GRUPOS])
    finally:
        s.close()
 
@app.route("/Destinos/<material>", methods=["PUT"])
@swag_from("data/doc/swagger/DestinoPut.yml")
def SalvarDestino(material):
    if material not in GRUPOS:
        return jsonify({"erro": "Material desconhecido"}), 404
    s = GetSession()
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
@swag_from("data/doc/swagger/FatoresGet.yml")
def ListarFatores():
    s = GetSession()
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
@swag_from("data/doc/swagger/FatorPut.yml")
def SalvarFator(chave):
    padrao = {c: (v, u, o) for c, v, u, o in FATORES_PADRAO}
    if chave not in padrao:
        return jsonify({"erro": "Fator desconhecido"}), 404
    s = GetSession()
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
    from app.data.doc.Seeds import SeedReferenciaPDF
    SeedReferenciaPDF()   # cenário hipotético do PDF;
    GarantirQRs()#testes/ter alguns
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        QR.RegerarTodos()
    app.run(host="0.0.0.0", port=5000)
#endregion rodar