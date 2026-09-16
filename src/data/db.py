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
    resultados = relationship('ResultadoCalculo', back_populates='veiculo')
 
 
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
 
class Destinacao(Base):
    __tablename__ = 'Destinacao'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('ModelosCarro.id'))
    material_id = Column(Integer, ForeignKey('Materiais.id'))
    Cenario = Column(String(20), default="base")   # base | baixa | alta
    PctReciclagem = Column(Float, default=0.0)
    PctReuso = Column(Float, default=0.0)
    PctValorizacao = Column(Float, default=0.0)
    PctDisposicao = Column(Float, default=0.0)
 
    veiculo = relationship('Veiculo', back_populates='destinacoes')
    material = relationship('Materiais', back_populates='destinacoes')
 
class ResiduoEspecial(Base):
    __tablename__ = 'ResiduoEspecial'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('ModelosCarro.id'))
    Nome = Column(String(80))               # óleo lubrificante, fluido de freio etc.
    Quantidade = Column(Float)
    Unidade = Column(String(10))            # L ou kg
    Destino = Column(String(80))            # ex: "Tratamento especializado"
 
    veiculo = relationship('Veiculo', back_populates='residuosEspeciais')
 
class DadoAtividade(Base):
    __tablename__ = 'DadoAtividade'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('ModelosCarro.id'))
    Cenario = Column(String(20), default="base")
    Processo = Column(String(50))           # ex: "transporte_inicial", "energia_desmontagem"
    Valor = Column(Float)
    Unidade = Column(String(10))            # km, kWh, L, kg
 
    veiculo = relationship('Veiculo', back_populates='atividades')
 
class FatorEmissao(Base):
    __tablename__ = 'FatorEmissao'
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('Materiais.id'), nullable=True)  # nulo p/ fatores genéricos
    Processo = Column(String(50))           # eletricidade, diesel, transporte, reciclagem, disposicao...
    Valor = Column(Float)                   # kgCO2e/kg, /kWh, /L ou /t.km
    Unidade = Column(String(20))
    Origem = Column(String(80))             # ex: "Hipotético", "Referência PBGHG"
 
    material = relationship('Materiais', back_populates='fatoresEmissao')
 
class FatorMaterialVirgem(Base):
    __tablename__ = 'FatorMaterialVirgem'
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('Materiais.id'))
    FEVirgem = Column(Float)                # fator de emissão do material virgem
    FD = Column(Float)                      # fator de deslocamento (0-1)
 
    material = relationship('Materiais', back_populates='fatorVirgem')
 
class ResultadoCalculo(Base):
    __tablename__ = 'ResultadoCalculo'
    id = Column(Integer, primary_key=True)
    veiculo_id = Column(Integer, ForeignKey('ModelosCarro.id'))
    Cenario = Column(String(20), default="base")
    Etapa = Column(String(30))              # transporte, eletricidade, diesel, disposicao, fluidos, reciclagem
    EmissaoKgCO2e = Column(Float)
    ParticipacaoPct = Column(Float)
    EvitadoKgCO2e = Column(Float, nullable=True)  # só preenchido na linha "reciclagem" (seção 13)
 
    veiculo = relationship('Veiculo', back_populates='resultados')
 
#region testes
Base.metadata.create_all(engine)


def ExData():
    try:
        #Veículo de referência
        veiculo = Veiculo(
            Categoria="Veículo compacto de passeio",
            Motorizacao="Combustão interna",
            Combustivel="Flex",
            MassaTotal=1200,
            VidaUtilAnos=15,
            Quilometragem=180000,
            Estado="Fim de vida",
        )
        session.add(veiculo)
        session.flush()  # garante veiculo.id disponível sem precisar commitar ainda
 
        #Seção 3 - Inventário dos componentes
        componentes_pdf = [
            ("Carroceria e painéis estruturais", 390),
            ("Chassi e subestruturas", 110),
            ("Motor", 130),
            ("Transmissão", 65),
            ("Suspensão e direção", 50),
            ("Sistema de freios", 28),
            ("Rodas", 28),
            ("Pneus", 40),
            ("Vidros", 32),
            ("Bancos", 65),
            ("Painel e revestimentos internos", 50),
            ("Para-choques e acabamentos", 35),
            ("Chicote elétrico", 15),
            ("Módulos eletrônicos", 15),
            ("Bateria 12 V", 15),
            ("Sistema de escapamento", 16),
            ("Catalisador", 4),
            ("Arrefecimento/climatização", 30),
            ("Sistema de combustível", 18),
            ("Airbags/dispositivos de segurança", 10),
            ("Faróis e lanternas", 8),
            ("Isolamentos", 10),
            ("Fixadores", 25),
            ("Fluidos/resíduos", 11),
        ]
        for nome, peso in componentes_pdf:
            session.add(Componentes(veiculo_id=veiculo.id, Categoria=nome, Peso=peso))
 
        #Seção 4 - Composição global por material
        materiais_pdf = {
            "Aço": 585,
            "Ferro fundido": 128,
            "Alumínio": 101,
            "Cobre": 28,
            "Plásticos": 193,
            "Vidro": 33,
            "Borracha": 50,
            "Chumbo": 13,
            "Outros": 58,
        }
        materiais_obj = {}
        for nome, peso in materiais_pdf.items():
            m = Materiais(veiculo_id=veiculo.id, Categoria=nome, Peso=peso)
            session.add(m)
            session.flush()  # garante m.id disponível para as tabelas dependentes
            materiais_obj[nome] = m
 
        #Seção 5 - Destinação dos materiais (cenário-base)
        # (material: % reciclagem, % reuso, % valorização, % disposição)
        destinacao_pdf = {
            "Aço": (95, 2, 0, 3),
            "Ferro fundido": (95, 0, 0, 5),
            "Alumínio": (92, 5, 0, 3),
            "Cobre": (98, 1, 0, 1),
            "Plásticos": (65, 10, 10, 15),
            "Vidro": (90, 2, 0, 8),
            "Borracha": (50, 10, 30, 10),
            "Chumbo": (95, 0, 0, 5),
            "Outros": (30, 5, 25, 40),
        }
        for nome, (rec, reu, val, disp) in destinacao_pdf.items():
            session.add(Destinacao(
                veiculo_id=veiculo.id,
                material_id=materiais_obj[nome].id,
                Cenario="base",
                PctReciclagem=rec,
                PctReuso=reu,
                PctValorizacao=val,
                PctDisposicao=disp,
            ))
 
        #Seção 6 - Componentes e resíduos especiais
        residuos_pdf = [
            ("Óleo lubrificante", 4.5, "L", "Coleta e tratamento"),
            ("Fluido de arrefecimento", 5.0, "L", "Tratamento"),
            ("Fluido de freio", 1.0, "L", "Tratamento especializado"),
            ("Combustível residual", 0.5, "L", "Recuperação/tratamento"),
            ("Bateria 12 V", 15, "kg", "Reciclagem específica"),
            ("Pneus", 40, "kg", "Rotas específicas"),
            ("Catalisador", 4, "kg", "Recuperação de materiais"),
            ("Componentes eletrônicos", 15, "kg", "Reciclagem especializada"),
        ]
        for nome, qtd, unidade, destino in residuos_pdf:
            session.add(ResiduoEspecial(
                veiculo_id=veiculo.id, Nome=nome, Quantidade=qtd, Unidade=unidade, Destino=destino
            ))
 
        #Seção 8 - Dados de atividade (cenário-base)
        atividades_pdf = {
            "transporte_inicial": (100, "km"),
            "massa_transportada_inicial": (1200, "kg"),
            "energia_desmontagem": (35, "kWh"),
            "diesel_operacoes": (8, "L"),
            "distancia_recicladores": (50, "km"),
            "distancia_reuso": (40, "km"),
            "distancia_valorizacao": (60, "km"),
            "distancia_disposicao": (30, "km"),
            "distancia_tratamento_fluidos": (80, "km"),
            "massa_reciclada": (1007.61, "kg"),
            "massa_reuso": (44.89, "kg"),
            "massa_valorizacao": (48.80, "kg"),
            "massa_disposicao": (87.70, "kg"),
            "massa_fluidos": (11, "kg"),
        }
        for processo, (valor, unidade) in atividades_pdf.items():
            session.add(DadoAtividade(
                veiculo_id=veiculo.id, Cenario="base", Processo=processo, Valor=valor, Unidade=unidade
            ))
 
        #Seção 9 - Fatores de emissão (genéricos, sem material)
        fatores_genericos_pdf = {
            "eletricidade": (0.0457, "kgCO2e/kWh", "Referência pública MCTI/SIN"),
            "diesel": (2.6702, "kgCO2e/L", "Referência PBGHG"),
            "transporte": (0.10, "kgCO2e/t.km", "Hipotético"),
            "disposicao": (0.15, "kgCO2e/kg", "Hipotético"),
            "tratamento_fluidos": (0.30, "kgCO2e/kg", "Hipotético"),
        }
        for processo, (valor, unidade, origem) in fatores_genericos_pdf.items():
            session.add(FatorEmissao(
                material_id=None, Processo=processo, Valor=valor, Unidade=unidade, Origem=origem
            ))
 
        #Seção 9 - Fatores de emissão de reciclagem (por material)
        fatores_reciclagem_pdf = {
            "Aço": 0.55,
            "Ferro fundido": 0.60,
            "Alumínio": 1.20,
            "Cobre": 1.10,
            "Plásticos": 0.80,
            "Vidro": 0.45,
            "Borracha": 0.70,
            "Chumbo": 0.50,
            "Outros": 0.50,
        }
        for nome, valor in fatores_reciclagem_pdf.items():
            session.add(FatorEmissao(
                material_id=materiais_obj[nome].id,
                Processo="reciclagem",
                Valor=valor,
                Unidade="kgCO2e/kg",
                Origem="Hipotético",
            ))
 
        #Seção 13 - Fatores de material virgem e deslocamento
        fatores_virgem_pdf = {
            "Aço": (2.00, 0.95),
            "Ferro fundido": (1.80, 0.95),
            "Alumínio": (8.00, 0.95),
            "Cobre": (4.00, 0.98),
            "Plásticos": (2.50, 0.80),
            "Vidro": (1.00, 0.90),
            "Borracha": (1.50, 0.70),
            "Chumbo": (2.00, 0.95),
            "Outros": (1.50, 0.50),
        }
        for nome, (fe_virgem, fd) in fatores_virgem_pdf.items():
            session.add(FatorMaterialVirgem(
                material_id=materiais_obj[nome].id, FEVirgem=fe_virgem, FD=fd
            ))
 
        session.commit()
        print(f"Dados de teste criados com sucesso. veiculo.id = {veiculo.id}")
    except Exception as e:
        session.rollback()
        print(f"Erro ao criar dados de debug: {e}")


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ExData()
#endregion