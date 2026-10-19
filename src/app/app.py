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

from data.db import (sessao, criar_banco, Cenario, TipoMaterial, Veiculo, Componentes, Materiais,
                     Destinacao, ResiduoEspecial, DadoAtividade, FatorEmissao, ResultadoCalculo)
from data.doc.QrGenDownloads import QR
from data.calculo import calcular, ErroCalculo

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

criar_banco()  # cria as tabelas e os catálogos (cenários, tipos de material, fatores) se faltarem
#endregion baseSistema


#region Erros
class ErroApi(Exception):
    def __init__(self, mensagem, status=400):
        super().__init__(mensagem)
        self.status = status


@app.errorhandler(ErroApi)
@app.errorhandler(ErroCalculo)
def _erro_com_status(e):
    return jsonify({"erro": str(e)}), e.status


@app.errorhandler(IntegrityError)
def _erro_integridade(e):
    # referência inexistente, registro duplicado ou registro em uso por outro
    return jsonify({"erro": f"Violação de integridade: {e.orig}"}), 409
#endregion Erros


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

#region Auxiliares
def obter_json():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ErroApi("Envie um objeto JSON no corpo da requisição")
    return dados

def converter(modelo, atributo, valor):
    """Converte o valor do JSON para o tipo da coluna (float, int, str)."""
    if valor is None:
        return None
    tipo = modelo.__table__.columns[atributo].type.python_type
    try:
        return tipo(valor)
    except (TypeError, ValueError):
        raise ErroApi(f"Valor inválido para '{atributo}': {valor!r}")

def buscar_cenario(s, nome):
    achado = s.query(Cenario).filter(func.lower(Cenario.Nome) == str(nome).strip().lower()).one_or_none()
    if achado is None:
        raise ErroApi(f"Cenário '{nome}' não existe")
    return achado

def buscar_tipo_material(s, nome):
    achado = s.query(TipoMaterial).filter(func.lower(TipoMaterial.Nome) == str(nome).strip().lower()).one_or_none()
    if achado is None:
        raise ErroApi(f"Tipo de material '{nome}' não existe (veja /TipoMaterial)")
    return achado

def numero_inteiro(valor, nome):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErroApi(f"Valor inválido para '{nome}': {valor!r}")
#endregion Auxiliares

#region Ganchos por recurso
# entrada(s, dados, criando) -> atributos extras a gravar (ex.: nome do cenário -> cenario_id)
# saida(obj)                 -> campos extras no JSON de resposta
# validar(obj)               -> levanta ErroApi se o registro for inválido

def entrada_cenario(s, dados, criando):
    if criando or "cenario" in dados:
        return {"cenario_id": buscar_cenario(s, dados.get("cenario") or "base").id}
    return {}

def saida_cenario(obj):
    return {"cenario": obj.cenario.Nome}

def entrada_material(s, dados, criando):
    if criando or "categoria" in dados:
        if not dados.get("categoria"):
            raise ErroApi("Campo obrigatório: categoria")
        return {"tipo_material_id": buscar_tipo_material(s, dados["categoria"]).id}
    return {}

def saida_material(obj):
    return {"categoria": obj.Categoria, "tipo_material_id": obj.tipo_material_id}

def saida_destinacao(obj):
    return {"veiculo_id": obj.veiculo_id, **saida_cenario(obj)}

def validar_destinacao(obj):
    pcts = [obj.PctReciclagem or 0, obj.PctReuso or 0, obj.PctValorizacao or 0, obj.PctDisposicao or 0]
    if any(p < 0 or p > 100 for p in pcts):
        raise ErroApi("Cada percentual deve estar entre 0 e 100")
    if abs(sum(pcts) - 100) > 0.01:
        raise ErroApi(f"Os quatro percentuais devem somar 100 (soma atual: {sum(pcts):g})")
#endregion Ganchos por recurso

#region CRUD
TIPOS_SWAGGER = {int: "integer", float: "number", str: "string"}

def especificacao(tag, resumo, campos=None, path_id=False, filtros=()):
    """Monta o dicionário de documentação do Swagger."""
    spec = {"tags": [tag], "summary": resumo,
            "responses": {"200": {"description": "OK"}, "400": {"description": "Dados inválidos"}}}
    parametros = []
    if path_id:
        parametros.append({"name": "id", "in": "path", "type": "integer", "required": True})
    for filtro in filtros:
        parametros.append({"name": filtro, "in": "query", "type": "string", "required": False})
    if campos is not None:
        parametros.append({"name": "body", "in": "body", "required": True, "schema": {
            "type": "object", "properties": {k: {"type": t} for k, t in campos.items()}}})
    if parametros:
        spec["parameters"] = parametros
    return spec

def registrar_crud(nome, modelo, campos, obrigatorios=(), extras=None,
                   entrada=None, saida=None, validar=None):
    """Cria GET (lista e um), POST, PUT e DELETE para um modelo.

    campos: chave do JSON -> atributo do modelo
    extras: campos do JSON tratados pelos ganchos (só para documentar no Swagger)
    """
    caminho = f"/{nome}"
    propriedades = {k: TIPOS_SWAGGER.get(modelo.__table__.columns[a].type.python_type, "string")
                    for k, a in campos.items()}
    propriedades.update(extras or {})
    filtros = [k for k in campos if k.endswith("_id")] + (["cenario"] if hasattr(modelo, "cenario_id") else [])

    def serializar(obj):
        d = {"id": obj.id}
        d.update({k: getattr(obj, a) for k, a in campos.items()})
        if saida:
            d.update(saida(obj))
        return d

    def buscar(s, id):
        obj = s.get(modelo, id)
        if obj is None:
            raise ErroApi(f"{nome} {id} não encontrado", 404)
        return obj

    @swag_from(especificacao(nome, f"Lista {nome} (aceita filtros na query)", filtros=filtros))
    def listar():
        with sessao() as s:
            q = s.query(modelo)
            for chave, valor in request.args.items():
                if chave in campos and chave.endswith("_id"):
                    atributo = campos[chave]
                    q = q.filter(getattr(modelo, atributo) == converter(modelo, atributo, valor))
                elif chave == "cenario" and hasattr(modelo, "cenario_id"):
                    q = q.filter(modelo.cenario_id == buscar_cenario(s, valor).id)
            return jsonify([serializar(o) for o in q.order_by(modelo.id).all()])

    @swag_from(especificacao(nome, f"Busca um registro de {nome}", path_id=True))
    def obter(id):
        with sessao() as s:
            return jsonify(serializar(buscar(s, id)))

    @swag_from(especificacao(nome, f"Cria um registro em {nome}", campos=propriedades))
    def criar():
        dados = obter_json()
        faltando = [k for k in obrigatorios if dados.get(k) is None]
        if faltando:
            raise ErroApi("Campos obrigatórios: " + ", ".join(faltando))
        with sessao() as s:
            valores = {a: converter(modelo, a, dados[k]) for k, a in campos.items() if k in dados}
            if entrada:
                valores.update(entrada(s, dados, True))
            obj = modelo(**valores)
            if validar:
                validar(obj)
            s.add(obj)
            s.flush()  # gera o id e dispara erros de integridade antes de responder
            resposta = serializar(obj)
        return jsonify(resposta), 201

    @swag_from(especificacao(nome, f"Atualiza só os campos enviados em {nome}", campos=propriedades, path_id=True))
    def editar(id):
        dados = obter_json()
        with sessao() as s:
            obj = buscar(s, id)
            for k, a in campos.items():
                if k in dados:
                    setattr(obj, a, converter(modelo, a, dados[k]))
            if entrada:
                for a, v in entrada(s, dados, False).items():
                    setattr(obj, a, v)
            if validar:
                validar(obj)
            s.flush()
            resposta = serializar(obj)
        return jsonify(resposta)

    @swag_from(especificacao(nome, f"Remove um registro de {nome} (e os filhos dele)", path_id=True))
    def remover(id):
        with sessao() as s:
            s.delete(buscar(s, id))
            s.flush()
        return jsonify({"removido": id})

    app.add_url_rule(caminho, f"listar_{nome}", listar, methods=["GET"])
    app.add_url_rule(caminho, f"criar_{nome}", criar, methods=["POST"])
    app.add_url_rule(f"{caminho}/<int:id>", f"obter_{nome}", obter, methods=["GET"])
    app.add_url_rule(f"{caminho}/<int:id>", f"editar_{nome}", editar, methods=["PUT"])
    app.add_url_rule(f"{caminho}/<int:id>", f"remover_{nome}", remover, methods=["DELETE"])

# catálogos
registrar_crud("Cenario", Cenario, {"nome": "Nome"}, obrigatorios=["nome"])

registrar_crud("TipoMaterial", TipoMaterial,
               {"nome": "Nome", "fe_reciclagem": "FEReciclagem", "fe_virgem": "FEVirgem",
                "fd": "FD", "origem": "Origem"},
               obrigatorios=["nome", "fe_reciclagem", "fe_virgem", "fd"])

registrar_crud("FatorEmissao", FatorEmissao,
               {"processo": "Processo", "valor": "Valor", "unidade": "Unidade", "origem": "Origem"},
               obrigatorios=["processo", "valor"])

# veículo e filhos
registrar_crud("Veiculo", Veiculo,
               {"categoria": "Categoria", "motorizacao": "Motorizacao", "combustivel": "Combustivel",
                "massa_total_kg": "MassaTotal", "vida_util_anos": "VidaUtilAnos",
                "quilometragem_km": "Quilometragem", "estado": "Estado"},
               obrigatorios=["massa_total_kg"])

registrar_crud("Componentes", Componentes,
               {"veiculo_id": "veiculo_id", "categoria": "Categoria", "peso_kg": "Peso"},
               obrigatorios=["veiculo_id", "categoria", "peso_kg"])

registrar_crud("Materiais", Materiais,
               {"veiculo_id": "veiculo_id", "peso_kg": "Peso"},
               obrigatorios=["veiculo_id", "peso_kg"],
               extras={"categoria": "string"}, entrada=entrada_material, saida=saida_material)

registrar_crud("Destinacao", Destinacao,
               {"material_id": "material_id", "pct_reciclagem": "PctReciclagem", "pct_reuso": "PctReuso",
                "pct_valorizacao": "PctValorizacao", "pct_disposicao": "PctDisposicao"},
               obrigatorios=["material_id"],
               extras={"cenario": "string"}, entrada=entrada_cenario, saida=saida_destinacao,
               validar=validar_destinacao)

registrar_crud("ResiduoEspecial", ResiduoEspecial,
               {"veiculo_id": "veiculo_id", "nome": "Nome", "quantidade": "Quantidade",
                "unidade": "Unidade", "destino": "Destino"},
               obrigatorios=["veiculo_id", "nome", "quantidade"])

registrar_crud("DadoAtividade", DadoAtividade,
               {"veiculo_id": "veiculo_id", "processo": "Processo", "valor": "Valor", "unidade": "Unidade"},
               obrigatorios=["veiculo_id", "processo", "valor"],
               extras={"cenario": "string"}, entrada=entrada_cenario, saida=saida_cenario)
#endregion CRUD

#region Resultados
def serializar_resultado(r, detalhe=False):
    d = {
        "id": r.id,
        "veiculo_id": r.veiculo_id,
        "cenario": r.cenario.Nome,
        "emissao_bruta_kgco2e": round(r.EmissaoBruta, 2),
        "beneficio_potencial_kgco2e": round(r.BeneficioPotencial, 2),
        "saldo_comparativo_kgco2e": round(r.Saldo, 2),
        "taxa_reciclagem_pct": round(r.TaxaReciclagem, 2),
        "criado_em": r.CriadoEm.isoformat() if r.CriadoEm else None,
    }
    if detalhe:
        d["etapas"] = [{"etapa": e.Etapa, "kgco2e": round(e.KgCO2e, 2),
                        "participacao_pct": round(e.KgCO2e / r.EmissaoBruta * 100, 2) if r.EmissaoBruta else 0.0}
                       for e in sorted(r.etapas, key=lambda e: -e.KgCO2e)]
    return d


@app.route("/Resultado/calcular", methods=["POST"])
@swag_from(especificacao("Resultado", "Calcula (e grava) o resultado de um veículo em um cenário",
                         campos={"veiculo_id": "integer", "cenario": "string", "salvar": "boolean"}))
def calcular_resultado():
    dados = obter_json()
    if dados.get("veiculo_id") is None:
        raise ErroApi("Campo obrigatório: veiculo_id")
    salvar = bool(dados.get("salvar", True))
    with sessao() as s:
        resultado = calcular(s, numero_inteiro(dados["veiculo_id"], "veiculo_id"),
                             dados.get("cenario") or "base", salvar=salvar)
    return jsonify(resultado), (201 if salvar else 200)


@app.route("/Resultado", methods=["GET"])
@swag_from(especificacao("Resultado", "Lista resultados gravados", filtros=["veiculo_id", "cenario"]))
def listar_resultados():
    with sessao() as s:
        q = s.query(ResultadoCalculo)
        if request.args.get("veiculo_id"):
            q = q.filter(ResultadoCalculo.veiculo_id == numero_inteiro(request.args["veiculo_id"], "veiculo_id"))
        if request.args.get("cenario"):
            q = q.filter(ResultadoCalculo.cenario_id == buscar_cenario(s, request.args["cenario"]).id)
        return jsonify([serializar_resultado(r) for r in q.order_by(ResultadoCalculo.id).all()])


@app.route("/Resultado/<int:id>", methods=["GET"])
@swag_from(especificacao("Resultado", "Busca um resultado com a quebra por etapa", path_id=True))
def obter_resultado(id):
    with sessao() as s:
        r = s.get(ResultadoCalculo, id)
        if r is None:
            raise ErroApi(f"Resultado {id} não encontrado", 404)
        return jsonify(serializar_resultado(r, detalhe=True))

@app.route("/Resultado/<int:id>", methods=["DELETE"])
@swag_from(especificacao("Resultado", "Remove um resultado gravado", path_id=True))
def remover_resultado(id):
    with sessao() as s:
        r = s.get(ResultadoCalculo, id)
        if r is None:
            raise ErroApi(f"Resultado {id} não encontrado", 404)
        s.delete(r)
    return jsonify({"removido": id})
#endregion Resultados

#region rodar
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
#endregion rodar