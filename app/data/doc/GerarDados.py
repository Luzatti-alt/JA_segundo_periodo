import os
import socket
from datetime import datetime
from functools import lru_cache
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

@lru_cache(maxsize=512)
def PngBytes(link: str) -> bytes:
    #PNG do QR gerado em memória. O cache evita refazer o mesmo link (alguns KB cada)."""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L,
                       box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    buf = BytesIO()
    qr.make_image(fill_color='black', back_color='white').save(buf, format='PNG')
    return buf.getvalue()


class QR:
    @staticmethod
    def BaseUrl(host=None) -> str:
        if not host or host.startswith(("127.0.0.1", "localhost")):
            host = f"{IpLocal()}:5000"
        return f"http://{host}"

    @staticmethod
    def Png(base_url: str, qr_id: int) -> BytesIO:
       #QR sob demanda(nada é gravado em disco)
        return BytesIO(PngBytes(f"{base_url}/download/{qr_id}"))

    @staticmethod
    def Gerar(base_url=None, data: str = '', veiculo_id=None, peca_id=None, material_id=None):
       #base_url é ignorado (mantido para não quebrar quem já chama). Só cria o registro; a imagem é montada quando alguém pede /QR/<id>/imagem
        registro = QRFiles(path='', data=data, veiculo_id=veiculo_id,
                           peca_id=peca_id, material_id=material_id)
        session.add(registro)
        session.commit()
        return registro.id

    @staticmethod
    def RegerarTodos(base_url=None, limpar_expirados=True):
       #Mantida por compatibilidade: limpa expirados, apaga PNGs antigos de temp/ e zera o cache.
        removidos = PDF.ApagarExpirados() if limpar_expirados else 0
        if os.path.isdir(PASTA_QRS):
            for nome in os.listdir(PASTA_QRS):
                if nome.lower().endswith(".png"):
                    os.remove(os.path.join(PASTA_QRS, nome))
        PngBytes.cache_clear()
        total = session.query(QRFiles).update({QRFiles.path: ''})
        session.commit()
        print(f"QRs cadastrados: {total} | expirados removidos: {removidos}")
        print(f"Base URL dos QRs: {base_url or QR.BaseUrl()}")
        return total

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
        expirados = session.query(QRFiles).filter(QRFiles.ExpiraEm < datetime.now()).all()
        for r in expirados:
            if r.path and os.path.exists(r.path):
                os.remove(r.path)
            session.delete(r)
        session.commit()
        return len(expirados)