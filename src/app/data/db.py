from sqlalchemy import or_, create_engine, Integer, Column, Float, String, JSON, Boolean, ForeignKey, func, FLOAT
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
 
engine = create_engine(f'sqlite:///dbtest.db')
Base = declarative_base()
 
Session = sessionmaker(bind=engine)
session = Session()

 
def refresh_session():
    global session
    session.close()
    session = Session()
 
#dados base de carros da fabricante para facilitar os calculos
class Veiculo(Base):
    __tablename__ = 'ModelosCarro'
    id = Column(Integer, primary_key=True)
    Categoria = Column(String(50))          # ex: "Veículo compacto de passeio"
    Motorizacao = Column(String(50))        # ex: "Combustão interna"
    Combustivel = Column(String(30))        # ex: "Flex"
    MassaTotal = Column(Float)              # kg
    VidaUtilAnos = Column(Integer)
    Quilometragem = Column(Float)           # km acumulados
    Estado = Column(String(30), default="Fim de vida")
 
    componentes = relationship('Componentes', back_populates='veiculo')
    materiais = relationship('Materiais', back_populates='veiculo')
    destinacoes = relationship('Destinacao', back_populates='veiculo')
    residuosEspeciais = relationship('ResiduoEspecial', back_populates='veiculo')
    atividades = relationship('DadoAtividade', back_populates='veiculo')
 
 
class Componentes(Base):
    __tablename__ = 'Componentes'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('ModelosCarro.id'))
    Categoria = Column(String(50)) #bateria,fluidos, pneus etc
    Peso = Column(Float)
 
    veiculo = relationship('Veiculo', back_populates='componentes')
 
class Materiais(Base):
    __tablename__ = 'Materiais'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('ModelosCarro.id'))
    Categoria = Column(String(50)) # metal,plastico etc so que sendo mais especifico
    Peso = Column(Float)                    # kg desse material no veículo
 
    veiculo = relationship('Veiculo', back_populates='materiais')
    destinacoes = relationship('Destinacao', back_populates='material')
    fatoresEmissao = relationship('FatorEmissao', back_populates='material')
    fatorVirgem = relationship('FatorMaterialVirgem', back_populates='material', uselist=False)
 

class QRFiles(Base):
    __tablename__ = 'QRs'
    id = Column(Integer, primary_key=True)
    path = Column(String)

#region testes
Base.metadata.create_all(engine)


def ExData():
    #refatorando para a nova versão
    pass

if __name__ == '__main__':
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ExData()
#endregion