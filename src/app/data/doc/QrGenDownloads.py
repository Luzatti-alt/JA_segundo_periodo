#gerar qr para link baixar doc (api-> dados e "qrs"(download dos qr))
from qrcode import *
import os
from  src.app.data.db import QRFiles

PASTA_QRS = '../src/app/data/doc/temp/a'
class QR():
    def __init__(self):
        return None
    def Gerar(file:str):
        #check de existir
        existe = os.makedirs(PASTA_QRS, exist_ok=True)
        print(existe)
        
        return None
    def FileToApi(path):
        return None

if __name__ == '__main__':
    QR.Gerar("a")