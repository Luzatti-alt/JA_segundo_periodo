import os
import socket
from datetime import datetime
from io import BytesIO

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from app.data.db import session, Session, QRFiles

PASTA_QRS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')

#region apilocal
def IpLocal():
    manual = os.environ.get("QR_IP")
    if manual:
        return manual
    try:
        candidatos = {i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except OSError:
        candidatos = set()
    for ip in sorted(candidatos):
        if ip.startswith("192.168.") and not ip.startswith(("192.168.56.", "192.168.137.")):
            return ip
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
#endregion apilocal

class QR:
    @staticmethod
    def _SalvarPng(base_url: str, qr_id: int) -> str:
        #Gera o PNG do QR com o link atual e devolve o caminho.
        link = f'{base_url}/download/{qr_id}'
        qr = qrcode.QRCode(version=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_L,
                           box_size=10, border=4)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')

        caminho = os.path.join(PASTA_QRS, f'qr_{qr_id}.png')
        img.save(caminho)
        return caminho
    @staticmethod
    def Gerar(base_url: str, data: str = '', veiculo_id=None,
              peca_id=None, material_id=None):
        os.makedirs(PASTA_QRS, exist_ok=True)

        registro = QRFiles(path='', data=data, veiculo_id=veiculo_id,
                           peca_id=peca_id, material_id=material_id)
        session.add(registro)
        session.flush()  # gera o registro.id

        registro.path = QR._SalvarPng(base_url, registro.id)
        session.commit()
        return registro.id
    @staticmethod
    def RegerarTodos(base_url=None, limpar_expirados=True):
        #Apaga os PNGs de temp e regera todos com o IP atual
        base_url = base_url or f"http://{IpLocal()}:5000"
        os.makedirs(PASTA_QRS, exist_ok=True)

        removidos = PDF.ApagarExpirados() if limpar_expirados else 0

        for nome in os.listdir(PASTA_QRS):
            if nome.lower().endswith(".png"):
                os.remove(os.path.join(PASTA_QRS, nome))

        registros = session.query(QRFiles).all()
        for r in registros:
            r.path = QR._SalvarPng(base_url, r.id)
        session.commit()

        print(f"QRs regerados: {len(registros)} | expirados removidos: {removidos}")
        print(f"Base URL dos QRs: {base_url}")
        return len(registros)
    @staticmethod
    def QrLido(qr_id: int):
        with Session() as s:
            registro = s.get(QRFiles, qr_id)
            if registro is None:
                return None
            return PDF.GerarPdf(registro)   


class PDF:
    @staticmethod
    def GerarPdf(registro):
        buf = BytesIO()
        estilos = getSampleStyleSheet()
        itens = [Paragraph(f"Relatório QR #{registro.id}", estilos['Title']),
                 Paragraph(str(registro.data or "Sem dados"), estilos['Normal']),
                 Spacer(1, 12)]

        v = registro.veiculo
        if v:
            itens.append(Paragraph(
                f"{v.veiculo} {v.Modelo} ({v.Ano}) - {v.MassaTotal} kg - {v.Estado}",
                estilos['Heading3']))
            linhas = [["Peça", "Peso (kg)", "Materiais"]]
            for p in v.pecas:
                mats = ", ".join(f"{m.Categoria} ({m.Peso} kg)" for m in p.materiais)
                linhas.append([p.Categoria, str(p.Peso), Paragraph(mats, estilos['Normal'])])
            itens.append(Table(linhas, colWidths=[90, 60, 340],
                               style=[('GRID', (0, 0), (-1, -1), 0.5, '#888888'),
                                      ('BACKGROUND', (0, 0), (-1, 0), '#dddddd')]))

        SimpleDocTemplate(buf, pagesize=A4).build(itens)
        buf.seek(0)
        return buf

    @staticmethod
    def ApagarExpirados():
        """Remove registros/PNGs de QRs expirados (ExpiraEm < agora)."""
        expirados = session.query(QRFiles).filter(QRFiles.ExpiraEm < datetime.now()).all()
        for r in expirados:
            if r.path and os.path.exists(r.path):
                os.remove(r.path)
            session.delete(r)
        session.commit()
        return len(expirados)