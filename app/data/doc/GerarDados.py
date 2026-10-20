import os
import socket
from datetime import datetime
from io import BytesIO

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from app.data.db import session, QRFiles

PASTA_QRS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')

#region apilocal
def IpLocal():
    """IP da rede local (o celular não acessa 'localhost' do PC)."""
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
    def Gerar(base_url: str, data: str = '', veiculo_id=None,
              peca_id=None, material_id=None):
        os.makedirs(PASTA_QRS, exist_ok=True)

        registro = QRFiles(path='', data=data, veiculo_id=veiculo_id,
                           peca_id=peca_id, material_id=material_id)
        session.add(registro)
        session.flush()  # gera o registro.id

        link = f'{base_url}/download/{registro.id}'
        qr = qrcode.QRCode(version=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_L,
                           box_size=10, border=4)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')

        caminho = os.path.join(PASTA_QRS, f'qr_{registro.id}.png')
        img.save(caminho)
        registro.path = caminho
        session.commit()
        return registro.id

    @staticmethod
    def QrLido(qr_id: int):
        """Regenera o PDF a partir do registro no banco (não guarda PDF em disco)."""
        registro = session.get(QRFiles, qr_id)
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