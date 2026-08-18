from sqlalchemy import or_, create_engine, Integer, Column, Float, String, JSON, Boolean, ForeignKey, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

engine = create_engine(f'sqlite:///dbtest.db')
Base = declarative_base()

Session = sessionmaker(bind=engine)
session = Session()


def refresh_session():
    global session
    session.close()
    session = Session()

class Materiais(Base):
    __tablename__ = 'Materiais'
    id = Column(Integer, primary_key=True)
    Tipo = Column(String(50))
    QuantidadeKg = Column(Float)

#region testes
Base.metadata.create_all(engine)

def fake_data():
    try:
        meterial = ["madeira","mdf"]
        for i in range(2):
            mat = meterial[i % len(meterial)]   
            print("feito")
            session.add(
            Materiais(
                Tipo = mat,
                QuantidadeKg = 100
            )
        )
        session.commit()
        print("Dados de teste criados com sucesso.")
    except Exception as e:
        session.rollback()
        print(f"Erro ao criar dados de debug: {e}")
if __name__ == '__main__':
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    fake_data()
#endregion