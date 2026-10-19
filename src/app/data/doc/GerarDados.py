#qr
import qrcode
import os
from  src.app.data.db import session, QRFiles
#pdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Spacer, Paragraph, Table, SimpleDocTemplate, Image as RLImage
from reportlab.lib.units import cm
from PIL import Image, ImageOps
from pathlib import Path
from io import BytesIO


PASTA_QRS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')

class QR:
    @staticmethod
    def Gerar(base_url: str):
        os.makedirs(PASTA_QRS, exist_ok=True)

        registro = QRFiles(path='')
        session.add(registro)
        session.flush()  # gera o registro.id

        link = f'{base_url}/download/{registro.id}'
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')

        caminho = os.path.join(PASTA_QRS, f'qr_{registro.id}.png')
        img.save(caminho)
        registro.path = caminho
        session.commit()
        return registro.id
    def QrLido():
        #optimizar espaço usa como base arquivo no db para regerar pdf
        GerarPdf()
        return None

class PDF():
    def GerarPdf(QRFile):
        #usa dados do qr e dados do db para regerar pdf
        pass
    def ApagarPdf(tempo):
        #após 2h apagar arquivo pdf (optimizar armazenamento e duplicatas)
        pass
if __name__ == '__main__':
    #teste funcionou
    print(QR.Gerar("http://localhost:5000"))