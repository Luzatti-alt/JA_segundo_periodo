import os
import shutil
import uuid
from datetime import datetime, timedelta
from sqlalchemy import (create_engine, event, Integer, Column, Float, String, DateTime, ForeignKey,
                        Boolean, JSON, Text, UniqueConstraint)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)   # era "app/data", relativo a quem roda
DB_PATH = os.environ.get("DB_PATH") or os.path.join(DATA_DIR, 'dbtest.db')   # DB_PATH só para testes
engine = create_engine(f'sqlite:///{DB_PATH}')

@event.listens_for(engine, "connect")
def _ativar_fk(conexao, _):
    # SQLite ignora FOREIGN KEY por padrão; sem isso a integridade dependia só do ORM
    cur = conexao.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()

def _uuid():
    return uuid.uuid4().hex

Base = declarative_base()

Session = sessionmaker(bind=engine)
session = Session()

def refresh_session():
    global session
    session.close()
    session = Session()

class ModeloVeiculo(Base):
    __tablename__ = 'ModelosCarro'
    id = Column(Integer, primary_key=True)
    veiculo = Column(String(100))
    Modelo = Column(String(100))
    Ano = Column(Integer)
    CategoriaVeiculo = Column(String(50))
    MassaTotal = Column(Float)
    Estado = Column(String(30), default="Fim de vida")
    VidaUtilAnos = Column(Integer, default=10)
    Kilometragem = Column(Integer, default=0)
    QuantidadePorModelos = Column(Integer, default=1)

    veiculos = relationship('Veiculo', back_populates='modelo_base')
    componentes_ref = relationship('ModeloComponente', back_populates='modelo', cascade='all, delete-orphan')


class Veiculo(Base):
    __tablename__ = 'Veiculo'
    id = Column(Integer, primary_key=True)
    modelo_id = Column(Integer, ForeignKey('ModelosCarro.id'), nullable=True)
    veiculo = Column(String(100))
    Modelo = Column(String(100))
    Chassi = Column(String(30), unique=True, nullable=False)
    Ano = Column(Integer)
    CategoriaVeiculo = Column(String(50))
    MassaTotal = Column(Float)
    Estado = Column(String(30), default="Fim de vida")
    VidaUtilAnos = Column(Integer, default=10)
    Kilometragem = Column(Integer, default=0)
    # qual inventário o cálculo usa: "por_peca" (Pecas.composicao) ou "agregada" (ComposicaoVeiculo).
    # Nunca os dois ao mesmo tempo, senão a mesma massa seria contada duas vezes.
    fonte_composicao = Column(String(20), default="por_peca")
    # separa o que é real do que é demonstrativo: real | exemplo (ExData) | referencia_pdf | nao_informado
    origem_dados = Column(String(20), default="real")
    motorizacao = Column(String(30), nullable=True)    # Combustão interna | Híbrido | Elétrico (sugestões no index.html)
    combustivel = Column(String(30), nullable=True)    # Flex | Gasolina | Etanol | Diesel...
    removido_em = Column(DateTime, nullable=True)   # remoção lógica (preserva histórico)

    modelo_base = relationship('ModeloVeiculo', back_populates='veiculos')
    composicao_agregada = relationship('ComposicaoVeiculo', back_populates='veiculo',
                                       cascade='all, delete-orphan')
    pecas = relationship('Pecas', back_populates='veiculo', cascade='all, delete-orphan')
    qrs = relationship('QRFiles', back_populates='veiculo', cascade='all, delete-orphan')
    atividade = relationship('AtividadeVeiculo', back_populates='veiculo', uselist=False,
                             cascade='all, delete-orphan')


class Pecas(Base):
    __tablename__ = 'Pecas'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('Veiculo.id'))     
    Categoria = Column(String(50))
    Peso = Column(Float)
    # Composição declarada da peça. NULL = composição NÃO informada (não é "zero material").
    # Itens: {"item_uid", "material_id", "categoria", "massa_kg", "status", "origem", ...}
    # status: "identificado" | "nao_identificado". Atribua sempre uma lista nova (o JSON não rastreia mutação).
    composicao = Column(JSON, nullable=True)
    massa_origem = Column(String(20), default="nao_informado")   # referencia|medido|estimado|fornecedor|nao_informado
    codigo_peca = Column(String(60), nullable=True)
    fornecedor = Column(String(100), nullable=True)
    modelo_componente_id = Column(Integer, ForeignKey('ModeloComponente.id'), nullable=True)
    removido_em = Column(DateTime, nullable=True)

    materiais = relationship('Materiais', back_populates='pecas', cascade='all, delete-orphan')#talvez trocar por json/dicionario para ter um controle melhor sobre informações da peça para auditoria ex: materialA:50(kg)materialB:20(kg)
    veiculo = relationship('Veiculo', back_populates='pecas')
    qrs = relationship('QRFiles', back_populates='pecas', cascade='all, delete-orphan')
class Materiais(Base):
    __tablename__ = 'Materiais'
    id = Column(Integer, primary_key=True)
    peca_id = Column(Integer, ForeignKey('Pecas.id'))
    Categoria = Column(String(50))
    Peso = Column(Float)
    # A partir daqui um Material é um LOTE FÍSICO rastreável. item_uid aponta para o item
    # de Pecas.composicao de onde ele veio; a massa é contada uma vez só (na composição).
    item_uid = Column(String(36), nullable=True)

    pecas = relationship('Pecas', back_populates='materiais')
    qrs = relationship('QRFiles', back_populates='materiais', cascade='all, delete-orphan')

class QRFiles(Base):
    __tablename__ = 'QRs'
    id = Column(Integer, primary_key=True)
    path = Column(String)
    data = Column(String)
    veiculo_id = Column(Integer, ForeignKey('Veiculo.id'), nullable=True)   
    peca_id = Column(Integer, ForeignKey('Pecas.id'), nullable=True)
    material_id = Column(Integer, ForeignKey('Materiais.id'), nullable=True)

    codigo = Column(String(36), default=_uuid)    # identificador permanente e não sequencial (índice único em Migrar)
    ativo = Column(Boolean, default=True)

    CriadoEm = Column(DateTime, default=datetime.now)
    # DEPRECADO: o QR é permanente. Expiração agora é do LinkTemporario. Mantido para não quebrar GerarDados.
    ExpiraEm = Column(DateTime, default=lambda: datetime.now() + timedelta(hours=2))

    materiais = relationship('Materiais', back_populates='qrs')
    veiculo = relationship('Veiculo', back_populates='qrs')
    pecas = relationship('Pecas', back_populates='qrs')
    links = relationship('LinkTemporario', back_populates='qr', cascade='all, delete-orphan')


class LinkTemporario(Base):
    #Link com validade (ex.: download do PDF). Expirar aqui NUNCA apaga o QR.#
    __tablename__ = 'LinksTemporarios'
    id = Column(Integer, primary_key=True)
    qr_id = Column(Integer, ForeignKey('QRs.id'), nullable=False)
    token = Column(String(40), unique=True, default=_uuid)
    finalidade = Column(String(30), default="pdf")
    CriadoEm = Column(DateTime, default=datetime.now)
    ExpiraEm = Column(DateTime, default=lambda: datetime.now() + timedelta(hours=2))

    qr = relationship('QRFiles', back_populates='links')


#region catalogo
# Catálogo dinâmico: novas categorias entram pela aplicação, sem mexer em código ou estrutura.
class CatalogoMaterial(Base):
    __tablename__ = 'CatalogoMateriais'
    id = Column(Integer, primary_key=True)
    nome = Column(String(80), unique=True, nullable=False)
    unidade_ref = Column(String(20), default="kg")
    descricao = Column(Text)
    # classificado: tem grupo em algum esquema | nao_classificado: conhecido, sem grupo
    # outros_declarado: alguém declarou "Outros" de propósito
    # "sem fator de emissão" NÃO é gravado: depende da metodologia, é calculado na consulta.
    status = Column(String(30), default="nao_classificado")
    processos = Column(JSON, nullable=True)        # ex.: ["reciclagem", "reuso"]
    ativo = Column(Boolean, default=True)
    CriadoEm = Column(DateTime, default=datetime.now)

    aliases = relationship('CatalogoAlias', back_populates='material', cascade='all, delete-orphan')
    grupos = relationship('MaterialGrupo', back_populates='material', cascade='all, delete-orphan')


class CatalogoAlias(Base):
    __tablename__ = 'CatalogoAliases'
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('CatalogoMateriais.id'), nullable=False)
    alias = Column(String(80), nullable=False)
    alias_norm = Column(String(80), unique=True, nullable=False)   # minúsculo, sem acento

    material = relationship('CatalogoMaterial', back_populates='aliases')


class MaterialGrupo(Base):
    #Grupo de cálculo do material em cada esquema (pdf_demo, vda, ...).#
    __tablename__ = 'MaterialGrupos'
    __table_args__ = (UniqueConstraint('material_id', 'esquema'),)
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('CatalogoMateriais.id'), nullable=False)
    esquema = Column(String(30), nullable=False)
    grupo = Column(String(60), nullable=False)

    material = relationship('CatalogoMaterial', back_populates='grupos')
#endregion catalogo


#region inventario
class ModeloComponente(Base):
    #Inventário-base de um modelo. Valores DE REFERÊNCIA, não medidos em veículo nenhum.#
    __tablename__ = 'ModeloComponente'
    id = Column(Integer, primary_key=True)
    modelo_id = Column(Integer, ForeignKey('ModelosCarro.id'), nullable=False)
    categoria = Column(String(50))
    massa_ref_kg = Column(Float)
    composicao_ref = Column(JSON, nullable=True)     # mesmo formato de Pecas.composicao; NULL = desconhecida
    codigo_peca = Column(String(60), nullable=True)
    fornecedor = Column(String(100), nullable=True)
    origem = Column(String(20), default="referencia")

    modelo = relationship('ModeloVeiculo', back_populates='componentes_ref')


class ComposicaoVeiculo(Base):
    #Composição GLOBAL do veículo (como o PDF fornece). Só vale com Veiculo.fonte_composicao='agregada'.#
    __tablename__ = 'ComposicaoVeiculo'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('Veiculo.id'), nullable=False)
    material_id = Column(Integer, ForeignKey('CatalogoMateriais.id'), nullable=True)
    categoria_texto = Column(String(80))             # texto original, preservado mesmo sem catálogo
    massa_kg = Column(Float)
    origem = Column(String(20), default="referencia")
    fonte = Column(String(100))

    veiculo = relationship('Veiculo', back_populates='composicao_agregada')
    material = relationship('CatalogoMaterial')
#endregion inventario


#region calculo
# Tabelas do modelo de cálculo (PDF "Parte 1"). Valores iniciais em app/data/doc/Calculos.py
class FatorEmissao(Base):
    __tablename__ = 'FatoresEmissao'
    chave = Column(String(60), primary_key=True)   # ex.: "diesel", "reciclagem:Aço", "virgem:Cobre"
    valor = Column(Float, nullable=False)
    unidade = Column(String(30))
    origem = Column(String(100), default="Hipotético")


class DestinoMaterial(Base):
    __tablename__ = 'DestinosMaterial'
    material = Column(String(50), primary_key=True)   # grupo do PDF: Aço, Alumínio, Plásticos...
    reciclagem = Column(Float, default=0)             # percentuais; cada linha deve fechar 100
    reuso = Column(Float, default=0)
    valorizacao = Column(Float, default=0)
    disposicao = Column(Float, default=0)


class AtividadeVeiculo(Base):
    __tablename__ = 'AtividadeVeiculo'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('Veiculo.id'), unique=True, nullable=False)
    transporte_inicial_km = Column(Float)
    energia_kwh = Column(Float)
    diesel_l = Column(Float)
    dist_reciclagem_km = Column(Float)
    dist_reuso_km = Column(Float)
    dist_valorizacao_km = Column(Float)
    dist_disposicao_km = Column(Float)
    dist_fluidos_km = Column(Float)

    veiculo = relationship('Veiculo', back_populates='atividade')
#endregion calculo

#region migracao
class SchemaVersao(Base):
    __tablename__ = 'SchemaVersao'
    versao = Column(Integer, primary_key=True)
    descricao = Column(String(200))
    aplicada_em = Column(DateTime, default=datetime.now)


def _colunas(conn, tabela):
    return {r[1] for r in conn.exec_driver_sql(f'PRAGMA table_info("{tabela}")')}

# (tabela, coluna, DDL). ALTER TABLE ADD COLUMN do SQLite não aceita UNIQUE nem NOT NULL sem default;
# a unicidade vai em índice separado.
COLUNAS_V1 = [
    ("Pecas", "composicao", "JSON"),
    ("Pecas", "massa_origem", "VARCHAR(20) DEFAULT 'nao_informado'"),
    ("Pecas", "codigo_peca", "VARCHAR(60)"),
    ("Pecas", "fornecedor", "VARCHAR(100)"),
    ("Pecas", "modelo_componente_id", "INTEGER REFERENCES ModeloComponente(id)"),
    ("Pecas", "removido_em", "DATETIME"),
    ("Veiculo", "fonte_composicao", "VARCHAR(20) DEFAULT 'por_peca'"),
    ("Veiculo", "removido_em", "DATETIME"),
    ("Materiais", "item_uid", "VARCHAR(36)"),
    ("QRs", "codigo", "VARCHAR(36)"),
    ("QRs", "ativo", "BOOLEAN DEFAULT 1"),
]

def _mig_1(conn):
    for tabela, coluna, ddl in COLUNAS_V1:
        if coluna not in _colunas(conn, tabela):
            conn.exec_driver_sql(f'ALTER TABLE "{tabela}" ADD COLUMN {coluna} {ddl}')
    for (qid,) in conn.exec_driver_sql('SELECT id FROM "QRs" WHERE codigo IS NULL').fetchall():
        conn.exec_driver_sql('UPDATE "QRs" SET codigo=? WHERE id=?', (_uuid(), qid))
    conn.exec_driver_sql('UPDATE "QRs" SET ativo=1 WHERE ativo IS NULL')
    conn.exec_driver_sql("UPDATE Veiculo SET fonte_composicao='por_peca' WHERE fonte_composicao IS NULL")
    conn.exec_driver_sql('CREATE UNIQUE INDEX IF NOT EXISTS ux_qrs_codigo ON "QRs"(codigo)')

def _mig_2(conn):
    # bancos anteriores: não dá para saber se o veículo é real ou exemplo -> 'nao_informado' (nunca chuta 'real')
    if "origem_dados" not in _colunas(conn, "Veiculo"):
        conn.exec_driver_sql("ALTER TABLE \"Veiculo\" ADD COLUMN origem_dados VARCHAR(20) DEFAULT 'nao_informado'")
    for col in ("motorizacao", "combustivel"):
        if col not in _colunas(conn, "Veiculo"):
            conn.exec_driver_sql(f'ALTER TABLE "Veiculo" ADD COLUMN {col} VARCHAR(30)')
    conn.exec_driver_sql("UPDATE Veiculo SET origem_dados='nao_informado' WHERE origem_dados IS NULL")

MIGRACOES = [
    (1, "Composicao JSON, catalogo, QR permanente, remocao logica", _mig_1),
    (2, "Veiculo.origem_dados, motorizacao, combustivel", _mig_2),
]

def Migrar():
    #create_all + migrações pendentes. Faz cópia do .db antes de alterar um banco existente.#
    from sqlalchemy import inspect
    tabelas = set(inspect(engine).get_table_names())
    atual = 0
    if 'SchemaVersao' in tabelas:
        with engine.connect() as c:
            atual = c.exec_driver_sql('SELECT COALESCE(MAX(versao), 0) FROM SchemaVersao').scalar()
    pendentes = [m for m in MIGRACOES if m[0] > atual]
    if pendentes and 'Veiculo' in tabelas:          # banco antigo com dados
        copia = f"{DB_PATH}.bak-v{atual}-{datetime.now():%Y%m%d%H%M%S}"
        shutil.copy2(DB_PATH, copia)
        print(f"Backup do banco antes da migração: {copia}")
    Base.metadata.create_all(engine)
    for versao, descricao, funcao in pendentes:
        try:
            with engine.begin() as conn:
                funcao(conn)
                conn.exec_driver_sql('INSERT INTO SchemaVersao (versao, descricao, aplicada_em) VALUES (?, ?, ?)',
                                     (versao, descricao, datetime.now().isoformat(sep=' ')))
            print(f"Migração {versao} aplicada: {descricao}")
        except Exception as e:      # dois processos do reloader podem migrar ao mesmo tempo
            print(f"Migração {versao} não aplicada agora ({e}); será reconferida na próxima inicialização")
#endregion migracao


#region catalogo funcoes
def _norm(txt):
    from app.data.doc.Calculos import _norm as n    # import local evita circular
    return n(txt)

def NovoMaterial(s, nome, status="nao_classificado", grupos=None, aliases=(), descricao=None):
    #Cria material + alias com o próprio nome. grupos: {esquema: grupo}. Não faz commit.#
    m = CatalogoMaterial(nome=nome.strip(), status=status, descricao=descricao)
    vistos = set()
    for al in (nome, *aliases):                     # "Aço" e "aco" têm a mesma forma normalizada
        if _norm(al) not in vistos:
            vistos.add(_norm(al))
            m.aliases.append(CatalogoAlias(alias=al, alias_norm=_norm(al)))
    for esquema, grupo in (grupos or {}).items():
        m.grupos.append(MaterialGrupo(esquema=esquema, grupo=grupo))
    s.add(m)
    s.flush()
    return m

def ResolverMaterial(s, nome, criar=True):
    if not (nome or "").strip():
        return None
    a = s.query(CatalogoAlias).filter_by(alias_norm=_norm(nome)).first()
    if a is not None:
        return a.material
    return NovoMaterial(s, nome) if criar else None

# materiais extras: "Fluidos" (grupo do PDF, seção 4) e os dos exemplos que o PDF não agrupa.
# Sem grupo = "não classificado" de propósito.
MATERIAIS_EXTRA = [("Fluidos", "Fluidos"), ("Lítio", None), ("Cobalto", None), ("Níquel", None), ("Tecido", None),
                   ("Líquido de arrefecimento", "Fluidos"), ("Fluido de freio", "Fluidos")]

def SeedCatalogo():
    #Cria o catálogo inicial a partir dos grupos do PDF. Não sobrescreve nada que já exista.#
    from app.data.doc.Calculos import GRUPOS, FLUIDOS, _ALIAS
    with Session() as s:
        try:
            for g in GRUPOS:
                if ResolverMaterial(s, g, criar=False) is None:
                    extras = [k for k, v in _ALIAS.items() if v == g]
                    NovoMaterial(s, g, "outros_declarado" if g == "Outros" else "classificado",
                                 {"pdf_demo": g}, extras)
            for nome, grupo in MATERIAIS_EXTRA:
                if ResolverMaterial(s, nome, criar=False) is None:
                    NovoMaterial(s, nome, "classificado" if grupo else "nao_classificado",
                                 {"pdf_demo": grupo} if grupo else None)
            s.commit()
        except Exception as e:
            s.rollback()
            print(f"SeedCatalogo não concluído: {e}")


def MigrarComposicao():
    with Session() as s:
        try:
            n = 0
            for p in s.query(Pecas).filter(Pecas.composicao.is_(None)).all():
                if not p.materiais:
                    continue                      # sem materiais: composição continua "não informada"
                itens = []
                for m in p.materiais:
                    mat = ResolverMaterial(s, m.Categoria)
                    m.item_uid = m.item_uid or _uuid()
                    item = {"item_uid": m.item_uid, "material_id": mat.id if mat else None,
                            "categoria": mat.nome if mat else None, "massa_kg": m.Peso,
                            "status": "identificado" if mat else "nao_identificado",
                            "origem": "migrado"}
                    if mat and (m.Categoria or "").strip() != mat.nome:
                        item["categoria_original"] = m.Categoria
                    itens.append(item)
                p.composicao = itens
                n += 1
            s.commit()
            if n:
                print(f"Composição JSON gerada para {n} peça(s).")
        except Exception as e:
            s.rollback()
            print(f"MigrarComposicao não concluída: {e}")
#endregion catalogo funcoes


#region testes
Migrar()


def SeedCalculo():
    #Cria os fatores e destinos do PDF que ainda não existem (não sobrescreve edições)
    from app.data.doc.Calculos import FATORES_PADRAO, DESTINOS_PADRAO   # import local evita circular
    with Session() as s:
        try:
            existentes = {f.chave for f in s.query(FatorEmissao).all()}
            for chave, valor, unidade, origem in FATORES_PADRAO:
                if chave not in existentes:
                    s.add(FatorEmissao(chave=chave, valor=valor, unidade=unidade, origem=origem))
            existentes = {d.material for d in s.query(DestinoMaterial).all()}
            for material, (r, u, v, d) in DESTINOS_PADRAO.items():
                if material not in existentes:
                    s.add(DestinoMaterial(material=material, reciclagem=r, reuso=u,
                                          valorizacao=v, disposicao=d))
            s.commit()
        except Exception:
            s.rollback()   # dois processos do reloader podem semear ao mesmo tempo


SeedCalculo()
SeedCatalogo()
MigrarComposicao()


def ExData(base_url=None):
    from app.data.doc.GerarDados import QR, IpLocal  # import local evita circular
    base_url = base_url or f"http://{IpLocal()}:5000"

    if session.query(Veiculo).count() > 0:
        print("Banco já possui dados, ExData ignorada.")
        return

    dados = [
        ("Nissan", "Leaf", "9BNLEAF0001234567", 2014, "Veículo elétrico",
         1500.0, "Fim de vida", 12, [
             ("Bateria", 300.0, [("Lítio", 12.0), ("Cobalto", 18.0),
                                 ("Níquel", 35.0), ("Alumínio", 90.0)]),
             ("Pneus", 40.0, [("Borracha", 32.0), ("Aço", 8.0)]),
             ("Carroceria", 450.0, [("Aço", 380.0), ("Alumínio", 70.0)]),
             ("Fluidos", 25.0, [("Líquido de arrefecimento", 10.0),
                                ("Fluido de freio", 1.0)]),
         ]),
        ("Renault", "Zoe", "VF1ZOE00002345678", 2016, "Veículo elétrico",
         1480.0, "Fim de vida", 10, [
             ("Bateria", 290.0, [("Lítio", 11.0), ("Cobalto", 16.0),
                                 ("Níquel", 30.0), ("Cobre", 45.0)]),
             ("Pneus", 38.0, [("Borracha", 30.0), ("Aço", 8.0)]),
             ("Interior", 120.0, [("Plástico", 70.0), ("Tecido", 30.0)]),
         ]),
        ("Toyota", "Prius", "JTDKN3DU3A0345678", 2010, "Veículo híbrido",
         1380.0, "Em uso", 15, [
             ("Bateria", 45.0, [("Níquel", 20.0), ("Aço", 15.0)]),
             ("Motor", 150.0, [("Ferro fundido", 100.0), ("Alumínio", 50.0)]),
             ("Pneus", 36.0, [("Borracha", 28.0), ("Aço", 8.0)]),
         ]),
    ]

    modelos, veiculos, pecas_lista, materiais_lista = [], [], [], []

    for (nome, modelo, chassi, ano, cat, massa, estado, vida, pecas) in dados:
        m = ModeloVeiculo(veiculo=nome, Modelo=modelo, Ano=ano, CategoriaVeiculo=cat,
                          MassaTotal=massa, Estado=estado, VidaUtilAnos=vida)
        v = Veiculo(modelo_base=m, veiculo=nome, Modelo=modelo, Chassi=chassi, Ano=ano,
                    CategoriaVeiculo=cat, MassaTotal=massa, Estado=estado,
                    VidaUtilAnos=vida, origem_dados="exemplo")
        modelos.append(m)
        veiculos.append(v)
        for (pcat, ppeso, materiais) in pecas:
            p = Pecas(Categoria=pcat, Peso=ppeso, veiculo=v)
            pecas_lista.append(p)
            for (mcat, mpeso) in materiais:
                materiais_lista.append(Materiais(Categoria=mcat, Peso=mpeso, pecas=p))

    session.add_all(modelos + veiculos + pecas_lista + materiais_lista)
    session.commit()

    ids = []
    for v in veiculos:
        ids.append(QR.Gerar(base_url, data=f"{v.veiculo} {v.Modelo} | Chassi: {v.Chassi}",
                            veiculo_id=v.id))
    for p in pecas_lista:
        ids.append(QR.Gerar(base_url, data=f"Peça: {p.Categoria} | {p.Peso} kg",
                            peca_id=p.id))
    for m in materiais_lista[:5]:
        ids.append(QR.Gerar(base_url, data=f"Material: {m.Categoria} | {m.Peso} kg",
                            material_id=m.id))

    MigrarComposicao()   # os exemplos nascem com Pecas.composicao preenchida

    print(f"Inseridos: {len(veiculos)} veículos, {len(pecas_lista)} peças, "
          f"{len(materiais_lista)} materiais, {len(ids)} QRs.")
    print(f"Base URL dos QRs: {base_url}")

if __name__ == '__main__':
    ExData()
#endregion