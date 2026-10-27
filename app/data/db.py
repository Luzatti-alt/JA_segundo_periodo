import os
from datetime import datetime, timedelta
from sqlalchemy import (create_engine, Integer, Column, Float, String,DateTime, ForeignKey)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship


os.makedirs("app/data", exist_ok=True)  # cria a pasta se não existir
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, 'dbtest.db')
engine = create_engine(f'sqlite:///{DB_PATH}')


Base = declarative_base()

Session = sessionmaker(bind=engine)
session = Session()


def refresh_session():
    global session
    session.close()
    session = Session()


class Veiculo(Base):
    __tablename__ = 'ModelosCarro'
    id = Column(Integer, primary_key=True)
    veiculo = Column(String(100))
    Modelo = Column(String(100))
    Chassi = Column(String(30),nullable=True)
    Ano = Column(Integer)
    CategoriaVeiculo = Column(String(50))
    QuantidadePecas = Column(Integer, default=1)
    MassaTotal = Column(Float)  # kg
    Estado = Column(String(30), default="Fim de vida")
    VidaUtilAnos = Column(Integer, default=10)
    Kilometragem = Column(Integer, default=0)
    QuantidadePorModelos = Column(Integer, default= 1)

    pecas = relationship('Pecas', back_populates='veiculo')
    qrs = relationship('QRFiles', back_populates='veiculo')


class Pecas(Base):
    __tablename__ = 'Pecas'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('ModelosCarro.id'))
    Categoria = Column(String(50))
    Peso = Column(Float)

    materiais = relationship('Materiais', back_populates='pecas')
    veiculo = relationship('Veiculo', back_populates='pecas')
    qrs = relationship('QRFiles', back_populates='pecas')


class Materiais(Base):
    __tablename__ = 'Materiais'
    id = Column(Integer, primary_key=True)
    peca_id = Column(Integer, ForeignKey('Pecas.id'))
    Categoria = Column(String(50))
    Peso = Column(Float)

    pecas = relationship('Pecas', back_populates='materiais')
    qrs = relationship('QRFiles', back_populates='materiais')


class QRFiles(Base):
    __tablename__ = 'QRs'
    id = Column(Integer, primary_key=True)
    path = Column(String)
    data = Column(String)
    veiculo_id = Column(Integer, ForeignKey('ModelosCarro.id'), nullable=True)
    peca_id = Column(Integer, ForeignKey('Pecas.id'), nullable=True)
    material_id = Column(Integer, ForeignKey('Materiais.id'), nullable=True)

    CriadoEm = Column(DateTime, default=datetime.now)
    ExpiraEm = Column(DateTime, default=lambda: datetime.now() + timedelta(hours=2))

    materiais = relationship('Materiais', back_populates='qrs')
    veiculo = relationship('Veiculo', back_populates='qrs')
    pecas = relationship('Pecas', back_populates='qrs')


#region testes
Base.metadata.create_all(engine)


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

    veiculos, pecas_lista, materiais_lista = [], [], []

    for (nome, modelo, chassi, ano, cat, massa, estado, vida, pecas) in dados:
        v = Veiculo(veiculo=nome, Modelo=modelo, Chassi=chassi, Ano=ano,
                    CategoriaVeiculo=cat, MassaTotal=massa, Estado=estado,
                    VidaUtilAnos=vida)
        veiculos.append(v)
        for (pcat, ppeso, materiais) in pecas:
            p = Pecas(Categoria=pcat, Peso=ppeso, veiculo=v)
            pecas_lista.append(p)
            for (mcat, mpeso) in materiais:
                materiais_lista.append(Materiais(Categoria=mcat, Peso=mpeso, pecas=p))

    session.add_all(veiculos + pecas_lista + materiais_lista)
    session.commit()  # grava e gera os IDs

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

    # QR já expirado, para testar a limpeza
    id_exp = QR.Gerar(base_url, data="QR expirado (teste)", veiculo_id=veiculos[0].id)
    exp = session.get(QRFiles, id_exp)
    exp.CriadoEm = datetime.now() - timedelta(hours=5)
    exp.ExpiraEm = datetime.now() - timedelta(hours=3)
    session.commit()
    ids.append(id_exp)

    print(f"Inseridos: {len(veiculos)} veículos, {len(pecas_lista)} peças, "
          f"{len(materiais_lista)} materiais, {len(ids)} QRs.")
    print(f"Base URL dos QRs: {base_url}")
    print(f"PNGs em: {os.path.join(DATA_DIR, 'doc', 'temp')}")

if __name__ == '__main__':
    Base.metadata.create_all(engine)
    ExData()
#endregion