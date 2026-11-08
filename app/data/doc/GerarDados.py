import os
import socket
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from xml.sax.saxutils import escape

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from app.data.db import Session, QRFiles, LinkTemporario, ComposicaoVeiculo
from app.services import Inventario

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
    #PNG do QR gerado em memória. O cache evita refazer o mesmo link (alguns KB cada).#
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
        fixa = os.environ.get("QR_BASE_URL", "").strip()
        if fixa:
            return fixa.rstrip("/")
        if not host or host.startswith(("127.0.0.1", "localhost")):
            host = f"{IpLocal()}:{os.environ.get('QR_PORT', '5000')}"
        return f"http://{host}"

    @staticmethod
    def Link(base_url: str, codigo: str) -> str:
        #O QR carrega o codigo PERMANENTE (uuid), não o id sequencial nem um link temporário.#
        return f"{base_url}/q/{codigo}"

    @staticmethod
    def Png(base_url: str, codigo: str) -> BytesIO:
        # QR sob demanda (nada é gravado em disco)
        return BytesIO(PngBytes(QR.Link(base_url, codigo)))

    @staticmethod
    def Gerar(base_url=None, data: str = '', veiculo_id=None, peca_id=None, material_id=None):
        # base_url é ignorado (mantido para não quebrar quem já chama). Só cria o registro permanente;
        # a imagem é montada quando alguém pede /QR/<id>/imagem. ExpiraEm fica vazio (QR não expira).
        with Session() as s:
            registro = QRFiles(path='', data=data, veiculo_id=veiculo_id, peca_id=peca_id,
                               material_id=material_id, ExpiraEm=None)
            s.add(registro)
            s.commit()
            return registro.id

    @staticmethod
    def RegerarTodos(base_url=None, limpar_expirados=True):
        #Zera o cache de imagens e apaga LINKS TEMPORÁRIOS vencidos. NUNCA apaga QRs.#
        removidos = PDF.ApagarExpirados() if limpar_expirados else 0
        if os.path.isdir(PASTA_QRS):
            for nome in os.listdir(PASTA_QRS):
                if nome.lower().endswith(".png"):
                    os.remove(os.path.join(PASTA_QRS, nome))
        PngBytes.cache_clear()
        with Session() as s:
            total = s.query(QRFiles).count()
        print(f"QRs cadastrados: {total} | links temporários vencidos removidos: {removidos}")
        print(f"Base URL dos QRs: {base_url or QR.BaseUrl()}")
        return total

    @staticmethod
    def QrLido(qr_id: int = None, codigo: str = None):
        #PDF do que o QR identifica. Aceita o id (links antigos) ou o codigo permanente.#
        with Session() as s:
            q = s.query(QRFiles)
            registro = q.filter(QRFiles.codigo == codigo).first() if codigo else s.get(QRFiles, qr_id)
            if registro is None or registro.ativo is False:
                return None
            return PDF.GerarPdf(registro, s)


class PDF:
    ROTULO_ORIGEM = {"exemplo": "DADOS DE EXEMPLO (demonstrativo)",
                     "referencia_pdf": "CENÁRIO HIPOTÉTICO DE REFERÊNCIA (PDF) - não são dados medidos",
                     "nao_informado": "Origem dos dados não informada"}

    @staticmethod
    def _txt(x):
        return escape(str(x)) if x not in (None, "") else "-"

    @staticmethod
    def _composicao(p, catalogo, estilo):
        itens = p.composicao
        if itens is None:
            return Paragraph("<i>composição não informada</i>", estilo)
        if not itens:
            return Paragraph("<i>composição vazia</i>", estilo)
        partes = []
        for i in itens:
            nome = i.get("categoria") or "não identificado"
            marca = ""
            if i.get("material_id") in catalogo and catalogo[i["material_id"]][1] == "nao_classificado":
                marca = " [sem classificação]"
            partes.append(f"{escape(nome)} ({i.get('massa_kg', 0):g} kg){marca}")
        return Paragraph(", ".join(partes), estilo)

    @staticmethod
    def _indicadores_texto(ind):
        if ind["cobertura_pct"] is None:
            return ind["estado"]
        return f"{ind['estado']} ({ind['cobertura_pct']:g}%)"

    @staticmethod
    def GerarPdf(registro, s):
        buf = BytesIO()
        e = getSampleStyleSheet()
        catalogo = Inventario.StatusCatalogo(s)
        itens = [Paragraph(f"Relatório QR #{registro.id}", e['Title']),
                 Paragraph(f"Código permanente: {registro.codigo}", e['Normal']),
                 Paragraph(PDF._txt(registro.data) if registro.data else "Sem dados", e['Normal']),
                 Spacer(1, 12)]
        estilo_tab = [('GRID', (0, 0), (-1, -1), 0.5, '#888888'), ('BACKGROUND', (0, 0), (-1, 0), '#dddddd'),
                      ('VALIGN', (0, 0), (-1, -1), 'TOP')]

        mat = registro.materiais
        peca = registro.pecas or (mat.pecas if mat else None)
        v = registro.veiculo or (peca.veiculo if peca else None)

        if v:
            if v.removido_em:
                itens.append(Paragraph(f"<b>REGISTRO REMOVIDO em {v.removido_em:%d/%m/%Y %H:%M}</b>", e['Normal']))
            rotulo = PDF.ROTULO_ORIGEM.get(v.origem_dados)
            if rotulo:
                itens.append(Paragraph(f"<b>{rotulo}</b>", e['Normal']))
            itens.append(Paragraph(f"{PDF._txt(v.veiculo)} {PDF._txt(v.Modelo)} ({PDF._txt(v.Ano)}) - "
                                   f"{PDF._txt(v.MassaTotal)} kg - {PDF._txt(v.Estado)} - "
                                   f"chassi {PDF._txt(v.Chassi)}", e['Heading3']))

        if mat is not None:                                   # QR de lote de material
            itens.append(Paragraph(f"Material (lote #{mat.id}): {PDF._txt(mat.Categoria)} - {mat.Peso} kg", e['Heading3']))
        if peca is not None and registro.veiculo_id is None:   # QR de peça (ou lote dela)
            ind = Inventario.IndicadoresPeca(peca, catalogo)
            itens.append(Paragraph(f"Peça #{peca.id}: {PDF._txt(peca.Categoria)} - {PDF._txt(peca.Peso)} kg "
                                   f"(origem da massa: {PDF._txt(peca.massa_origem)})", e['Heading3']))
            itens.append(Paragraph(f"Código: {PDF._txt(peca.codigo_peca)} | Fornecedor: {PDF._txt(peca.fornecedor)}",
                                   e['Normal']))
            itens.append(Paragraph(f"Composição: {PDF._indicadores_texto(ind)} - identificada "
                                   f"{ind['massa_identificada_kg']} kg, não identificada "
                                   f"{ind['massa_nao_identificada_kg']} kg", e['Normal']))
            itens.append(PDF._composicao(peca, catalogo, e['Normal']))
            for a in ind["alertas"]:
                itens.append(Paragraph(f"Atenção: {escape(a)}", e['Normal']))
        elif v is not None and registro.veiculo_id is not None:  # QR de veículo
            inv = Inventario.IndicadoresVeiculo(s, v)
            itens.append(Paragraph(
                "Composição do veículo: " + ("COMPLETA" if inv["resultado_integral"] else "INCOMPLETA - resultados parciais")
                + f" | cobertura {inv['cobertura_pct'] if inv['cobertura_pct'] is not None else '-'}% "
                  f"(fonte: {inv['fonte_composicao']})", e['Normal']))
            for m in inv["motivos_parcial"]:
                itens.append(Paragraph(f"- {escape(m)}", e['Normal']))
            itens.append(Spacer(1, 8))
            if inv["fonte_composicao"] == "agregada":
                # composição GLOBAL do veículo (é ela que vale); a das peças não se aplica nesta fonte
                agreg = s.query(ComposicaoVeiculo).filter(ComposicaoVeiculo.veiculo_id == v.id).all()
                linhas = [["Material", "Massa (kg)", "Origem", "Fonte"]]
                for c in agreg:
                    nome = catalogo[c.material_id][0] if c.material_id in catalogo else c.categoria_texto
                    sem_class = c.material_id in catalogo and catalogo[c.material_id][1] == "nao_classificado"
                    linhas.append([Paragraph(PDF._txt(nome) + (" [sem classificação]" if sem_class else ""), e['Normal']),
                                   PDF._txt(c.massa_kg), PDF._txt(c.origem),
                                   Paragraph(PDF._txt(c.fonte), e['Normal'])])
                itens.append(Paragraph("Composição global do veículo (fonte agregada)", e['Heading3']))
                itens.append(Table(linhas, colWidths=[140, 60, 70, 230], style=estilo_tab))
                itens.append(Spacer(1, 8))
                itens.append(Paragraph("Composição por peça não se aplica: o inventário traz a massa de cada peça, "
                                       "mas não a distribuição dos materiais dentro dela.", e['Normal']))
                itens.append(Spacer(1, 8))
                linhas = [["Peça", "Peso (kg)", "Origem massa"]]
                for p in v.pecas:
                    if p.removido_em is None:
                        linhas.append([Paragraph(PDF._txt(p.Categoria), e['Normal']), PDF._txt(p.Peso),
                                       PDF._txt(p.massa_origem)])
                itens.append(Table(linhas, colWidths=[260, 70, 120], style=estilo_tab))
            else:
                linhas = [["Peça", "Peso (kg)", "Origem massa", "Composição (cobertura)", "Materiais"]]
                for p in v.pecas:
                    if p.removido_em is not None:
                        continue
                    ind = Inventario.IndicadoresPeca(p, catalogo)
                    linhas.append([Paragraph(PDF._txt(p.Categoria), e['Normal']), PDF._txt(p.Peso),
                                   PDF._txt(p.massa_origem), PDF._indicadores_texto(ind),
                                   PDF._composicao(p, catalogo, e['Normal'])])
                itens.append(Table(linhas, colWidths=[75, 45, 60, 75, 245], style=estilo_tab))
            itens.append(Spacer(1, 8))
            itens.append(Paragraph("Destinação: os percentuais por material e as distâncias da página Cálculos são "
                                   "parâmetros simulados do modelo demonstrativo. Nenhuma destinação efetiva "
                                   "(real) está registrada para este veículo.", e['Normal']))

        SimpleDocTemplate(buf, pagesize=A4).build(itens)
        buf.seek(0)
        return buf

    @staticmethod
    def ApagarExpirados():
        #Remove só LinkTemporario vencido. O QR é permanente e nunca é apagado por expiração.#
        with Session() as s:
            n = s.query(LinkTemporario).filter(LinkTemporario.ExpiraEm < datetime.now()).delete()
            s.commit()
            return n