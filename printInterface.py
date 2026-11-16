"""
Teste de interface (pyautogui) do software de pegada de carbono.

COMO USAR
    pip install pyautogui pyperclip pillow
    1) Suba o servidor:            python app/app.py          (porta 5000)
    2) Rode este script:           python test_interface.py
       (se o navegador JÁ estiver em tela cheia, use:  python test_interface.py --ja-em-tela-cheia)
    3) Quando a contagem começar, NÃO mexa no mouse nem no teclado.
       Para abortar: jogue o mouse no canto superior esquerdo da tela (fail-safe do pyautogui).

CONVENÇÃO DOS VALORES
    Todo texto digitado é  test_input_{stype},  onde {stype} é o tipo/nome do campo
    (o atributo name= do input):  test_input_veiculo, test_input_modelo, test_input_chassi,
    test_input_categoria, test_input_estado, test_input_codigo_peca, ...
    Campos numéricos recebem números (um input type=number não aceita texto).

COMO FUNCIONA
    - O pyautogui não enxerga o DOM, então a navegação é por TECLADO:
        * páginas: Ctrl+L + URL;
        * botões da página inicial: contagem de Tab a partir do topo da página;
        * campos do modal: Ctrl+F no texto "×" / "Fechar" (o foco de Tab passa a partir do texto achado),
          depois Tab na ordem dos campos do HTML.
    - A VERIFICAÇÃO é dupla:
        * API (GET) confere se o registro realmente foi gravado/removido e se o cálculo deu o resultado esperado;
        * a TELA é conferida com Ctrl+F + Ctrl+C (seleciona só a palavra achada). Nunca usa Ctrl+A,
          então a página não fica toda selecionada nos prints/gravações.
    - O navegador entra em TELA CHEIA (F11) e cada print é uma captura da TELA TODA com Win+PrintScreen
      (o Windows salva em Imagens\\Capturas de tela; o script copia o arquivo novo para
      ./prints_teste/<data_hora>/NN_nome.png, na ordem do teste). Se o Windows não gerar o arquivo,
      cai para pyautogui.screenshot (também tela cheia).
    - Só a UI da aplicação aparece nas capturas: antes de cada print o script confirma que o navegador está em
      tela cheia (se não estiver, aperta F11), leva o mouse para uma área vazia e fecha popups do navegador
      (sugestões de histórico) e seleções do Ctrl+F.
    - Páginas que ROLAM são capturadas inteiras: o script rola com PageDown até a tela parar de mudar e tira
      uma captura por tela (NN_nome.png, NN_nome_p2.png, ...). Tabelas com rolagem HORIZONTAL interna
      aparecem só até onde cabem na tela.
    - O print de cada passo é tirado ANTES de qualquer leitura de tela.
    - Depois, rode inserir_prints_no_manual.py para colocar as imagens no manual (.docx).

PREMISSAS (ajuste nas constantes abaixo se algo não bater)
    - Navegador Chrome/Edge (a busca Ctrl+F deixa o foco de Tab no texto achado).
    - Teclado do navegador em pt-BR; os textos são colados (Ctrl+V), então acentos/underscore não dependem do layout.
    - Os <select> dos modais listam os registros em ordem de id, então a tecla End escolhe o mais novo.
"""
import ctypes
import json
import os
import shutil
import unicodedata
import sys
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime

import pyautogui
import pyperclip

try:
    import ctypes.wintypes          # só existe/serve no Windows
except Exception:
    pass

#region config
BASE_URL = os.environ.get("TESTE_URL", "http://127.0.0.1:5000")
PASTA_BASE_PRINTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prints_teste")
PASTA_PRINTS = PASTA_BASE_PRINTS      # main() troca por uma subpasta data_hora a cada execução

# Onde o Win+PrintScreen grava. Se a sua pasta for outra, defina a variável PASTA_CAPTURAS (ex.: no PowerShell:
#   $env:PASTA_CAPTURAS="D:\\Fotos\\Capturas de tela"). Por padrão procuro nos lugares usuais do Windows.
_HOME = os.path.expanduser("~")
PASTAS_CAPTURAS = [p for p in [os.environ.get("PASTA_CAPTURAS"),
                               os.path.join(_HOME, "Pictures", "Screenshots"),
                               os.path.join(_HOME, "Imagens", "Capturas de tela"),
                               os.path.join(_HOME, "Pictures", "Capturas de tela"),
                               os.path.join(_HOME, "OneDrive", "Pictures", "Screenshots"),
                               os.path.join(_HOME, "OneDrive", "Imagens", "Capturas de tela"),
                               os.path.join(_HOME, "OneDrive", "Imagens", "Screenshots")] if p]
ESPERA_CAPTURA = 6.0       # s esperando o Windows gravar o arquivo do Win+PrintScreen
MAX_TELAS = 6              # máximo de capturas por página rolável (cada PageDown = ~1 tela, com sobreposição)
MAX_TELAS_POR_PAGINA = {"nav_Dados": 3, "nav_QR": 2}   # listas longas de dados: só as primeiras telas
X_VAZIO = 40               # x (px) de um ponto sempre em branco, à esquerda do conteúdo (fora do <main>)

ESPERA_PAGINA = 2.0        # s depois de carregar uma página
ESPERA_MODAL = 0.8         # s depois de abrir o modal
ESPERA_API = 1.0           # s depois de confirmar (a rede/JS atualizar)
PAUSA_TECLA = 0.12         # s entre teclas

# Posição (nº de Tab desde o topo da página) dos botões em index.html.
# Cabeçalho = 7 focáveis (Marca + 6 links), então o 1º botão é o 8º.
TAB_BOTAO = {
    ("VeiculoModelo", "adicionar"): 8, ("VeiculoModelo", "editar"): 9, ("VeiculoModelo", "remover"): 10,
    ("veiculo", "adicionar"): 12,      ("veiculo", "editar"): 13,      ("veiculo", "remover"): 14,
    ("componentes", "adicionar"): 16,  ("componentes", "editar"): 17,  ("componentes", "remover"): 18,
    ("materiais", "adicionar"): 19,    ("materiais", "editar"): 20,    ("materiais", "remover"): 21,
}
TAB_CABECALHO = 7          # Marca + 6 links do cabeçalho; o próximo Tab cai no 1º elemento da página

pyautogui.PAUSE = PAUSA_TECLA
pyautogui.FAILSAFE = True
#endregion config


#region valores
def T(stype):
    """Valor de texto padrão de todos os testes."""
    return f"test_input_{stype}"

V_VEICULO, V_MODELO, V_CHASSI = T("veiculo"), T("modelo"), T("chassi")
V_CATEGORIA, V_ESTADO = T("categoria"), T("estado")
V_ESTADO_EDITADO = T("estado_editado")
V_MATERIAL_CAT = T("categoria")          # lote de material: cria 'test_input_categoria' no catálogo
V_CAT_NOME = T("nome")                   # material do catálogo criado pela página Catálogo (sem grupo de cálculo)
V_CAT_CALC = T("nome_calculo")           # material NOVO já classificado para o cálculo (esquema 'pdf demo')
ESQUEMA_CALC, GRUPO_CALC = "pdf demo", "Alumínio"
#endregion valores


#region api (só LEITURA/verificação e limpeza; o teste em si é feito pela tela)
def api(metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE_URL + caminho, data=dados, method=metodo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            txt = r.read().decode() or "null"
            return r.status, json.loads(txt)
    except urllib.error.HTTPError as e:
        txt = e.read().decode() or "null"
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, txt
    except urllib.error.URLError:
        return 0, None


def listar(caminho):
    st, dados = api("GET", caminho)
    return dados if st == 200 and isinstance(dados, list) else []


def achar(caminho, **filtros):
    """Último registro da listagem cujas chaves batem com os filtros (o mais novo)."""
    achados = [x for x in listar(caminho) if all(x.get(k) == v for k, v in filtros.items())]
    return achados[-1] if achados else None
#endregion api


#region pyautogui helpers
def contagem(segundos=5):
    for i in range(segundos, 0, -1):
        print(f"  começando em {i}s... (não toque no mouse/teclado)")
        time.sleep(1)


def tab(n=1):
    for _ in range(n):
        pyautogui.press("tab")


def shift_tab(n=1):
    for _ in range(n):
        pyautogui.hotkey("shift", "tab")


def colar(texto):
    """Substitui o conteúdo do campo focado por `texto` (colar evita problemas de layout/acentos)."""
    pyperclip.copy(str(texto))
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")


def preencher(*valores):
    """Preenche campos em sequência. Cada item é um valor (vai com Tab depois) ou None (só pula o campo)."""
    for i, v in enumerate(valores):
        if v is not None:
            colar(v)
        if i < len(valores) - 1:
            tab()


def ir_para_url(caminho):
    pyautogui.hotkey("ctrl", "l")
    colar(BASE_URL + caminho)
    pyautogui.press("enter")
    time.sleep(ESPERA_PAGINA + 0.5)             # em tela cheia a barra de endereço recolhe depois do Enter


def ancora(texto, ultimo=True):
    """Ctrl+F no texto e Esc: o próximo Tab vai para o 1º focável depois do texto achado.
    ultimo=True usa a ÚLTIMA ocorrência (o modal fica no fim do HTML)."""
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.3)
    colar(texto)
    time.sleep(0.2)
    if ultimo:
        pyautogui.hotkey("shift", "enter")      # volta uma ocorrência = dá a volta até a última
        time.sleep(0.2)
    pyautogui.press("esc")
    time.sleep(0.2)


def selecionar_ultimo():
    """No <select> focado, escolhe a última opção (o registro mais novo)."""
    pyautogui.press("end")
    time.sleep(0.4)             # o JS costuma preencher os campos ao trocar o registro


_NUM_PRINT = [0]
_AVISOU_FALLBACK = [False]
INDICE_PRINTS = []


def _pngs_das_capturas():
    achados = {}
    for pasta in PASTAS_CAPTURAS:
        if os.path.isdir(pasta):
            for nome in os.listdir(pasta):
                if nome.lower().endswith(".png"):
                    caminho = os.path.join(pasta, nome)
                    achados[caminho] = os.path.getmtime(caminho)
    return achados


#region tela cheia / captura
HWND = [None]                      # janela do navegador (só Windows)
DETECCAO_TELA_CHEIA = [False]      # True se conseguimos CONFIRMAR a tela cheia depois do F11


def _janela_ativa():
    return ctypes.windll.user32.GetForegroundWindow() if os.name == "nt" else None


def em_tela_cheia(hwnd):
    """A janela cobre exatamente a tela (F11). Janela maximizada tem bordas fora da tela e NÃO conta."""
    if hwnd is None:
        return False
    r = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = pyautogui.size()
    return r.left <= 0 and r.top <= 0 and r.right >= w and r.bottom >= h and (r.right - r.left) <= w + 2 \
        and (r.bottom - r.top) <= h + 2


def tela_cheia(ja_esta=False):
    """Guarda a janela do navegador (a que está em primeiro plano) e coloca em tela cheia com F11."""
    HWND[0] = _janela_ativa()
    if not ja_esta:
        pyautogui.press("f11")
    time.sleep(4)                                     # espera o aviso 'saia com F11' sumir
    DETECCAO_TELA_CHEIA[0] = em_tela_cheia(HWND[0])
    if not DETECCAO_TELA_CHEIA[0]:
        print("  [aviso] não consegui confirmar a tela cheia pelo Windows; não vou re-checar antes de cada print. "
              "Confira se o navegador está em tela cheia.")


def garantir_tela_cheia():
    """Antes de cada print: navegador em primeiro plano e em tela cheia (se a tela cheia foi confirmada no início)."""
    if os.name != "nt" or HWND[0] is None:
        return
    if _janela_ativa() != HWND[0]:
        ctypes.windll.user32.SetForegroundWindow(HWND[0])
        time.sleep(0.4)
    if DETECCAO_TELA_CHEIA[0] and not em_tela_cheia(HWND[0]):
        pyautogui.press("f11")
        time.sleep(3)
        if not em_tela_cheia(HWND[0]):
            print("  [aviso] o navegador saiu da tela cheia e não voltou; os próximos prints podem mostrar a barra dele.")


def limpar_selecao():
    """Tira o destaque que o Ctrl+F deixa no texto achado (ex.: 'Fechar' azul): procurar algo que não existe
    desmarca a seleção. Sem clique, então nada na página é acionado."""
    ancora("zzz_texto_que_nao_existe_zzz", ultimo=False)


def _preparar_captura(limpar=False):
    garantir_tela_cheia()
    if limpar:
        limpar_selecao()
    largura, altura = pyautogui.size()
    pyautogui.moveTo(X_VAZIO, altura // 2)            # mouse fora do conteúdo: sem hover e sem a barra do navegador
    time.sleep(0.5)


def print_tela(nome, limpar=False):
    """Captura da TELA TODA com Win+PrintScreen e copia o PNG novo para prints_teste/<execução>/NN_nome.png.
    limpar=True remove antes o destaque do Ctrl+F (use depois de confirmar()/ancora())."""
    _preparar_captura(limpar)
    os.makedirs(PASTA_PRINTS, exist_ok=True)
    _NUM_PRINT[0] += 1
    destino = os.path.join(PASTA_PRINTS, f"{_NUM_PRINT[0]:02d}_{nome}.png")
    antes = set(_pngs_das_capturas())
    pyautogui.hotkey("win", "printscreen")
    time.sleep(0.8)                                   # a tela "pisca"; o arquivo vem logo depois
    novos, limite = set(), time.time() + ESPERA_CAPTURA
    while not novos and time.time() < limite:
        novos = set(_pngs_das_capturas()) - antes
        if not novos:
            time.sleep(0.3)
    if novos:
        origem = max(novos, key=os.path.getmtime)
        time.sleep(0.4)                               # deixa o Windows terminar de gravar
        shutil.copy2(origem, destino)
    else:
        if not _AVISOU_FALLBACK[0]:
            print("  [aviso] Win+PrintScreen não gerou arquivo nas pastas conhecidas; usando pyautogui.screenshot. "
                  "Defina PASTA_CAPTURAS com a sua pasta de capturas.")
            _AVISOU_FALLBACK[0] = True
        pyautogui.screenshot(destino)
    INDICE_PRINTS.append({"arquivo": os.path.basename(destino), "nome": nome})


def _telas_iguais(a, b):
    """Duas capturas (PIL) praticamente iguais? Reduz e compara a diferença média de brilho."""
    from PIL import ImageChops, ImageStat
    pequena = (480, 270)
    dif = ImageChops.difference(a.convert("L").resize(pequena), b.convert("L").resize(pequena))
    return ImageStat.Stat(dif).mean[0] < 0.15


def capturar_pagina(nome, maximo=None):
    """Captura a PÁGINA INTEIRA: topo e, enquanto a tela ainda mudar ao dar PageDown, uma captura por tela
    (NN_nome.png, NN_nome_p2.png, ...). Devolve quantas telas foram tiradas.
    Antes, um clique numa área vazia da página tira o foco de campos/<select> (PageDown num <select> focado
    trocaria o item). Só use em páginas SEM modal aberto: o clique no vazio poderia fechá-lo."""
    maximo = maximo or MAX_TELAS_POR_PAGINA.get(nome, MAX_TELAS)
    garantir_tela_cheia()
    _, altura = pyautogui.size()
    pyautogui.click(X_VAZIO, altura // 2)
    pyautogui.press("home")
    time.sleep(0.7)
    print_tela(nome)
    telas, anterior = 1, pyautogui.screenshot()
    while telas < maximo:
        pyautogui.press("pagedown")
        time.sleep(0.9)                               # rolagem suave
        atual = pyautogui.screenshot()
        if _telas_iguais(anterior, atual):            # chegou ao fim da página
            break
        telas += 1
        print_tela(f"{nome}_p{telas}")
        anterior = atual
    pyautogui.press("home")
    time.sleep(0.4)
    return telas
#endregion tela cheia / captura


def _norm(txt):
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def pagina_contem(texto):
    """True se `texto` aparece na página renderizada. Sem Ctrl+A: Ctrl+F acha o texto, Esc deixa SÓ aquela
    ocorrência selecionada e Ctrl+C copia. Ignora maiúsculas/acentos, como o próprio Ctrl+F do navegador.
    Chame DEPOIS de tirar o print (a ocorrência fica selecionada)."""
    pyperclip.copy("__vazio__")
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.3)
    colar(texto)
    time.sleep(0.5)
    pyautogui.press("esc")
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.3)
    return _norm(pyperclip.paste()) == _norm(texto)


def abrir_modal(entidade, acao):
    """Carrega a página inicial, aperta o botão (Adicionar/Editar/Remover) e deixa o foco no
    1º elemento focável depois do '×' do modal (o seletor de registro, ou o 1º campo)."""
    ir_para_url("/")
    tab(TAB_BOTAO[(entidade, acao)])
    pyautogui.press("enter")
    time.sleep(ESPERA_MODAL)
    ancora("×")
    tab()


def confirmar(remocao=False):
    """Foco no botão de confirmar (vem logo depois de 'Fechar') e Enter.
    remocao=True: o app abre um confirm() nativo do navegador ('Remover este ...?'); Enter de novo aceita (OK)."""
    ancora("Fechar")
    tab()
    pyautogui.press("enter")
    if remocao:
        time.sleep(0.7)
        pyautogui.press("enter")
    time.sleep(ESPERA_API)


def eh_o_ultimo(caminho, registro):
    """Trava de segurança: o End do <select> escolhe o ÚLTIMO item da lista. Só é seguro remover pela tela
    se esse último for o registro criado pelo teste (senão apagaria dado real)."""
    lista = listar(caminho)
    return bool(registro) and bool(lista) and lista[-1].get("id") == registro["id"]


#endregion pyautogui helpers


#region resultado
RESULTADOS = []


def checar(nome, ok, detalhe=""):
    RESULTADOS.append((nome, bool(ok), detalhe))
    print(f"  [{'OK' if ok else 'FALHOU'}] {nome}" + (f" - {detalhe}" if detalhe and not ok else ""))
    return bool(ok)


def passo(titulo):
    print(f"\n== {titulo}")
#endregion resultado


#region limpeza via API (o teste cria/remove pela tela; isto só garante um estado limpo)
def renomear_chassi_e_remover(v):
    """Remoção de veículo é LÓGICA e o chassi continua UNIQUE: renomeia antes, para o teste poder rodar de novo."""
    novo = f"{V_CHASSI}_{int(time.time())}"          # <= 30 caracteres (limite da coluna)
    api("PUT", f"/Veiculo/{v['id']}", {"chassi": novo})
    api("DELETE", f"/Veiculo/{v['id']}")


def limpar_restos():
    for v in listar("/Veiculo"):
        if str(v.get("chassi") or "").startswith("test_input_") or v.get("veiculo") == V_VEICULO:
            renomear_chassi_e_remover(v)
    for p in listar("/Componentes"):
        if p.get("categoria") == V_CATEGORIA and p.get("modelo_veiculo") == V_MODELO:
            api("DELETE", f"/Componentes/{p['id']}")
    for m in listar("/VeiculoModelo"):
        if m.get("veiculo") == V_VEICULO:
            api("DELETE", f"/VeiculoModelo/{m['id']}")
    for c in listar("/Catalogo"):
        if str(c.get("nome", "")).startswith("test_input_"):
            st, _ = api("DELETE", f"/Catalogo/{c['id']}")
            if st == 409:                              # em uso: ao menos desativa
                api("PUT", f"/Catalogo/{c['id']}", {"ativo": False})
#endregion limpeza


#region testes
def teste_navegacao():
    passo("Navegação: cada página abre e mostra seu título")
    paginas = [("/", "Cadastros"), ("/Dados", "Dados do banco"), ("/QR", "Controle QR"),
               ("/CatalogoMateriais", "Catálogo de materiais"), ("/Inventario", "Inventário do veículo"),
               ("/Calculos", "Pegada de carbono no fim de vida")]
    for caminho, esperado in paginas:
        ir_para_url(caminho)
        capturar_pagina("nav" + caminho.replace("/", "_"))
        checar(f"página {caminho} mostra '{esperado}'", pagina_contem(esperado))
    return True


def teste_criar_modelo():
    passo("Adicionar modelo de veículo")
    abrir_modal("VeiculoModelo", "adicionar")                 # foco em Marca
    preencher(V_VEICULO,          # Marca        (name=veiculo)
              V_MODELO,           # Modelo
              2020,               # Ano
              V_CHASSI,           # Chassi
              V_CATEGORIA,        # Categoria
              1000,               # Massa total (kg)
              1,                  # Quantidade deste modelo
              10,                 # Vida útil (anos)
              1000,               # Quilometragem (km)
              V_ESTADO)           # Estado
    tab()                                  # sai do último campo: fecha o popup de sugestões do navegador
    print_tela("modelo_preenchido")
    confirmar()
    print_tela("modelo_criado", limpar=True)
    m = achar("/VeiculoModelo", veiculo=V_VEICULO, modelo=V_MODELO)
    return (checar("modelo gravado no banco", m is not None)
            and checar("modelo com categoria/massa corretas",
                       m["categoria"] == V_CATEGORIA and float(m["massa_total_kg"]) == 1000.0,
                       str(m)))


def teste_editar_modelo():
    passo("Editar modelo de veículo")
    abrir_modal("VeiculoModelo", "editar")                    # foco no seletor de registro
    selecionar_ultimo()
    tab(10)                                                   # Marca...Estado: o Estado é o 10º campo
    colar(V_ESTADO_EDITADO)
    tab()                                                     # fecha o popup de sugestões do navegador
    print_tela("modelo_editando")
    confirmar()
    m = achar("/VeiculoModelo", veiculo=V_VEICULO, modelo=V_MODELO)
    return checar("estado do modelo alterado", m is not None and m["estado"] == V_ESTADO_EDITADO,
                  str(m))


def teste_criar_veiculo():
    passo("Adicionar veículo individual (a partir do modelo)")
    modelo = achar("/VeiculoModelo", veiculo=V_VEICULO, modelo=V_MODELO)
    abrir_modal("veiculo", "adicionar")                       # foco no seletor do modelo base
    selecionar_ultimo()
    tab()                                                     # -> Chassi
    preencher(V_CHASSI,                 # Chassi
              2020,                     # Ano
              V_CATEGORIA,              # Categoria
              900,                      # Massa total (kg): não pode passar da do modelo (1000)
              10,                       # Vida útil
              1000,                     # Quilometragem
              V_ESTADO,                 # Estado
              T("motorizacao"),         # Motorização
              T("combustivel"))         # Combustível (origem/fonte/cópia ficam no padrão)
    tab()                                                     # fecha o popup de sugestões do navegador
    print_tela("veiculo_preenchido")
    confirmar()
    print_tela("veiculo_criado", limpar=True)
    v = achar("/Veiculo", chassi=V_CHASSI)
    ok = checar("veículo gravado no banco", v is not None)
    if ok and modelo:
        ok = checar("veículo ligado ao modelo criado", v["modelo_id"] == modelo["id"], str(v))
    return ok and checar("campos do veículo corretos",
                         v["motorizacao"] == T("motorizacao") and v["combustivel"] == T("combustivel")
                         and float(v["massa_total_kg"]) == 900.0, str(v))


def teste_criar_componente():
    passo("Adicionar componente")
    veiculo = achar("/Veiculo", chassi=V_CHASSI)
    abrir_modal("componentes", "adicionar")                   # foco no seletor Veículo
    selecionar_ultimo()
    tab()                                                     # -> Categoria
    preencher(V_CATEGORIA,              # Categoria
              50,                       # Peso (kg)
              None,                     # Origem da massa (select, fica no padrão)
              T("codigo_peca"),         # Código da peça
              T("fornecedor"))          # Fornecedor
    tab()                                                     # fecha o popup de sugestões do navegador
    print_tela("componente_preenchido")
    confirmar()
    c = achar("/Componentes", categoria=V_CATEGORIA, codigo_peca=T("codigo_peca"))
    ok = checar("componente gravado no banco", c is not None)
    if ok and veiculo:
        ok = checar("componente ligado ao veículo", c["veiculo_id"] == veiculo["id"], str(c))
    return ok


def teste_criar_material():
    passo("Adicionar material (lote de uma peça)")
    comp = achar("/Componentes", categoria=V_CATEGORIA, codigo_peca=T("codigo_peca"))
    abrir_modal("materiais", "adicionar")                     # foco no seletor Peça
    selecionar_ultimo()
    tab()                                                     # -> Categoria
    preencher(V_MATERIAL_CAT,           # Categoria
              10)                       # Peso (kg)
    print_tela("material_preenchido")
    confirmar()
    m = achar("/Materiais", categoria=V_MATERIAL_CAT)
    ok = checar("material gravado no banco", m is not None)
    if ok and comp:
        ok = checar("material ligado ao componente", m["peca_id"] == comp["id"], str(m))
    return ok


def criar_material_catalogo(rotulo, nome, alias, grupos, esperado_status, esperado_grupos):
    """Preenche o formulário 'Novo material' da página Catálogo e confere o resultado na API e na tela."""
    ir_para_url("/CatalogoMateriais")
    ancora("Novo material", ultimo=False)
    tab()                                                     # -> Nome
    preencher(nome,                                    # Nome
              alias,                                   # Aliases (um por linha)
              grupos,                                  # Grupos de cálculo: esquema=grupo
              None,                                    # Status (automático)
              "kg",                                    # Unidade de referência
              "reciclagem, reuso",                     # Processos
              T("descricao"))                          # Descrição
    capturar_pagina(f"{rotulo}_preenchido")                   # lista no topo, formulário preenchido embaixo
    ancora("Ativo")                                           # a captura tirou o foco: volta ao botão Salvar
    tab()                                                     # texto 'Ativo' -> botão Salvar
    pyautogui.press("enter")
    time.sleep(ESPERA_API)
    capturar_pagina(f"{rotulo}_salvo")
    c = achar("/Catalogo", nome=nome)
    ok = checar(f"{rotulo}: material gravado no catálogo", c is not None)
    if ok:
        ok = checar(f"{rotulo}: alias, grupo e status", alias in c["aliases"]
                    and c["grupos"] == esperado_grupos and c["status"] == esperado_status, str(c))
    return ok and checar(f"{rotulo}: tabela do catálogo mostra o material", pagina_contem(nome))


def teste_catalogo():
    passo("Catálogo: material novo SEM grupo de cálculo (esquema inventado)")
    return criar_material_catalogo("catalogo", V_CAT_NOME, T("aliases"),
                                   f"{T('esquema')}={T('grupo')}", "classificado",
                                   {T("esquema"): T("grupo")})


def teste_catalogo_calculo():
    passo(f"Catálogo: material novo JÁ classificado no esquema '{ESQUEMA_CALC}' (entra no cálculo)")
    return criar_material_catalogo("catalogo_calculo", V_CAT_CALC, T("aliases_calculo"),
                                   f"{ESQUEMA_CALC}={GRUPO_CALC}", "classificado",
                                   {ESQUEMA_CALC: GRUPO_CALC})


def teste_criar_material_classificado():
    passo("Adicionar lote do material novo classificado (15 kg)")
    comp = achar("/Componentes", categoria=V_CATEGORIA, codigo_peca=T("codigo_peca"))
    cat = achar("/Catalogo", nome=V_CAT_CALC)
    abrir_modal("materiais", "adicionar")                     # foco no seletor Peça
    selecionar_ultimo()
    tab()                                                     # -> Categoria
    preencher(V_CAT_CALC,               # Categoria: resolve para o material do catálogo (pelo nome)
              15)                       # Peso (kg)
    print_tela("material_classificado_preenchido")
    confirmar()
    m = achar("/Materiais", categoria=V_CAT_CALC)
    ok = checar("lote do material novo gravado", m is not None)
    if ok and comp:
        ok = checar("lote ligado ao componente", m["peca_id"] == comp["id"], str(m))
    c = achar("/Componentes", id=comp["id"]) if comp else None
    itens = (c or {}).get("composicao") or []
    ok = checar("composição da peça aponta para o material do catálogo (identificado, sem recriar)",
                bool(cat) and any(i.get("material_id") == cat["id"] and i.get("status") == "identificado"
                                  for i in itens), str(itens)) and ok
    return ok


def teste_dados():
    passo("Página Dados: tabelas mostram o que foi cadastrado")
    ir_para_url("/Dados")
    time.sleep(1)
    capturar_pagina("dados")
    ok = True
    for esperado in (V_MODELO, V_CHASSI, V_CATEGORIA, T("codigo_peca"), V_CAT_NOME, V_CAT_CALC):
        ok = checar(f"Dados mostra '{esperado}'", pagina_contem(esperado)) and ok
    return ok


def teste_qr():
    passo("Controle QR: busca pelo chassi")
    ir_para_url("/QR")
    tab(TAB_CABECALHO + 1)                                    # campo de busca
    colar(V_CHASSI)
    time.sleep(2)                                             # debounce da busca (QRBusca.js)
    capturar_pagina("qr_busca")
    return checar("QR do veículo aparece na busca", pagina_contem(V_CHASSI))


def teste_inventario():
    passo("Inventário: veículo e suas peças")
    veiculo = achar("/Veiculo", chassi=V_CHASSI)
    if not eh_o_ultimo("/Veiculo", veiculo):
        return checar("veículo de teste é o último da lista", False)
    ir_para_url("/Inventario")
    tab(TAB_CABECALHO + 1)                                    # select de veículo
    selecionar_ultimo()
    time.sleep(1.5)
    capturar_pagina("inventario")
    return checar("inventário lista a peça do veículo", pagina_contem(V_CATEGORIA))


#region calculos
def calcular_pela_tela(rotulo):
    """Abre /Calculos, escolhe o veículo de teste (último da lista) e aperta Calcular. Devolve o JSON da API."""
    veiculo = achar("/Veiculo", chassi=V_CHASSI)
    if not eh_o_ultimo("/Veiculo", veiculo):
        checar(f"{rotulo}: veículo de teste é o último da lista", False)
        return None, None
    ir_para_url("/Calculos")
    tab(TAB_CABECALHO + 1)                                    # select de veículo
    selecionar_ultimo()
    time.sleep(0.5)
    tab()                                                     # botão Calcular
    pyautogui.press("enter")
    time.sleep(2.5)
    capturar_pagina(rotulo)                                   # o resultado é longo: uma captura por tela
    st, r = api("GET", f"/Calculos/{veiculo['id']}")
    checar(f"{rotulo}: API de cálculo responde 200", st == 200, f"status={st}")
    return (r if st == 200 else None), veiculo


def avisos_com(r, *trechos):
    return any(all(t in a for t in trechos) for a in (r or {}).get("avisos", []))


TOTAIS = {}


def teste_calculo_veiculo_novo():
    passo("Cálculos: veículo NOVO, peça sem composição e sem dados de atividade")
    r, v = calcular_pela_tela("calculo_veiculo_novo")
    if r is None:
        return False
    TOTAIS["sem_composicao"] = r["total_kg_co2e"]
    ok = checar("resultado marcado como parcial (não integral)", r["resultado_integral"] is False)
    ok = checar("aviso: peça sem composição informada", avisos_com(r, "sem composição informada"), str(r["avisos"])) and ok
    ok = checar("aviso: nenhum material entrou no cálculo", avisos_com(r, "Nenhum material entrou no cálculo")) and ok
    ok = checar("aviso: atividade não cadastrada (usa valores hipotéticos)",
                avisos_com(r, "Dados de atividade não cadastrados")) and ok
    ok = checar("total > 0 (só transporte, diesel e eletricidade)", r["total_kg_co2e"] > 0, str(r["total_kg_co2e"])) and ok
    ok = checar("nenhuma massa nos materiais", r["massas"]["solidos_kg"] == 0, str(r["massas"])) and ok
    # tela (a ocorrência fica selecionada: o print já foi tirado)
    ok = checar("tela mostra o aviso 'Nenhum material entrou no cálculo'",
                pagina_contem("Nenhum material entrou no cálculo")) and ok
    return ok


def teste_calculo_itens_novos():
    passo("Cálculos: veículo com material NOVO classificado + material NOVO sem grupo")
    r, v = calcular_pela_tela("calculo_itens_novos")
    if r is None:
        return False
    alum = next((x for x in r["reciclagem_por_material"] if x["material"] == GRUPO_CALC), None)
    ok = checar(f"material novo entrou no grupo {GRUPO_CALC} com 15 kg",
                alum is not None and alum["massa_kg"] == 15.0, str(alum))
    ok = checar("parte reciclada do material novo > 0 (emissão de reciclagem contabilizada)",
                alum is not None and alum["massa_reciclada_kg"] > 0 and alum["kg_co2e"] > 0) and ok
    ok = checar("massa sólida do cálculo = 15 kg (só o material classificado)",
                r["massas"]["solidos_kg"] == 15.0, str(r["massas"])) and ok
    ok = checar("material novo sem grupo FICA FORA do cálculo, com aviso",
                avisos_com(r, V_MATERIAL_CAT, "sem grupo de cálculo", "NÃO entrou no cálculo"), str(r["avisos"])) and ok
    ok = checar("resultado continua parcial", r["resultado_integral"] is False) and ok
    ok = checar("fora do cálculo: 10 kg sem grupo contabilizados na qualidade",
                r["qualidade"]["massa_fora_do_calculo_kg"] >= 10.0, str(r["qualidade"])) and ok
    antes = TOTAIS.get("sem_composicao")
    ok = checar("total aumentou em relação ao veículo sem composição",
                antes is not None and r["total_kg_co2e"] > antes, f"antes={antes} agora={r['total_kg_co2e']}") and ok
    st1, cen = api("GET", f"/Calculos/{v['id']}/cenarios")
    st2, sen = api("GET", f"/Calculos/{v['id']}/sensibilidade")
    ok = checar("cenários: baixa/base/alta", st1 == 200 and len(cen) == 3, f"status={st1}") and ok
    ok = checar("sensibilidade: 5 variáveis", st2 == 200 and len(sen) == 5, f"status={st2}") and ok
    # tela
    ok = checar("tela mostra o aviso do material sem grupo", pagina_contem("sem grupo de cálculo")) and ok
    ok = checar("tela cita o material novo sem grupo", pagina_contem(V_MATERIAL_CAT)) and ok
    ok = checar("tela mostra o grupo do material novo", pagina_contem(GRUPO_CALC)) and ok
    return ok


def teste_calculo_atividade():
    passo("Cálculos: editar 'Dados de atividade' do veículo novo (melhor esforço; depende do Calculos.js)")
    veiculo = achar("/Veiculo", chassi=V_CHASSI)
    if not eh_o_ultimo("/Veiculo", veiculo):
        return checar("veículo de teste é o último da lista", False)
    st, antes = api("GET", f"/Atividade/{veiculo['id']}")
    ir_para_url("/Calculos")
    tab(TAB_CABECALHO + 1)
    selecionar_ultimo()                                       # o formulário é preenchido para o veículo escolhido
    time.sleep(1.2)
    ancora("Dados de atividade do veículo selecionado", ultimo=False)
    tab()                                                     # próxima <summary>
    shift_tab()                                               # volta para a <summary> de atividade
    pyautogui.press("enter")                                  # abre o <details>
    time.sleep(0.6)
    tab()                                                     # 1º campo do formulário (qualquer que seja)
    colar(21)
    tab()                                                     # sai do campo (change/blur)
    time.sleep(ESPERA_API)

    def mudou():
        _, depois = api("GET", f"/Atividade/{veiculo['id']}")
        return depois and antes and any(float(depois[k]) == 21.0 and float(antes[k]) != 21.0 for k in depois)

    if not mudou():                                           # talvez o salvamento seja por Enter no campo
        shift_tab()
        pyautogui.press("enter")
        time.sleep(ESPERA_API)
    capturar_pagina("atividade_editada")                      # página inteira, com o <details> aberto
    return checar("valor digitado na atividade foi salvo (PUT /Atividade)", bool(mudou()),
                  "nenhum campo ficou 21; veja prints_teste/*atividade_editada* e o Calculos.js (como salva?)")
#endregion calculos


def remover_pela_tela(rotulo, entidade, caminho, registro):
    """Remove `registro` pela tela, mas só se ele for o último da lista (ver eh_o_ultimo)."""
    if registro is None:
        print(f"  [pulado] {rotulo}: não foi criado por este teste")
        return True
    if not eh_o_ultimo(caminho, registro):
        return checar(f"{rotulo}: removível com segurança (é o último da lista)", False,
                      "o último item da lista não é o do teste; remoção pela tela cancelada para não apagar dado real")
    abrir_modal(entidade, "remover")
    selecionar_ultimo()
    print_tela(f"remover_{entidade}")
    confirmar(remocao=True)
    return checar(f"{rotulo} removido", achar(caminho, id=registro["id"]) is None)


def teste_remover():
    passo("Remover (lotes -> componente -> veículo -> modelo)")
    ok = True
    # o lote do material novo foi criado por último: é o último da lista
    ok = remover_pela_tela("lote do material novo", "materiais", "/Materiais",
                           achar("/Materiais", categoria=V_CAT_CALC)) and ok
    ok = remover_pela_tela("lote sem grupo", "materiais", "/Materiais",
                           achar("/Materiais", categoria=V_MATERIAL_CAT)) and ok

    comp = achar("/Componentes", categoria=V_CATEGORIA, codigo_peca=T("codigo_peca"))
    ok = remover_pela_tela("componente", "componentes", "/Componentes", comp) and ok

    # remoção de veículo é lógica e o chassi continua UNIQUE: renomeia (via API) ANTES do clique,
    # senão a próxima execução toparia com "já existe um veículo com este chassi"
    v = achar("/Veiculo", chassi=V_CHASSI)
    if v:
        api("PUT", f"/Veiculo/{v['id']}", {"chassi": f"{V_CHASSI}_{int(time.time())}"})
    ok = remover_pela_tela("veículo", "veiculo", "/Veiculo", v) and ok

    mo = achar("/VeiculoModelo", veiculo=V_VEICULO, modelo=V_MODELO)
    ok = remover_pela_tela("modelo", "VeiculoModelo", "/VeiculoModelo", mo) and ok
    print_tela("remocoes")
    return ok
#endregion testes


def main():
    print("Teste de interface - valores no padrão test_input_{stype}")
    st, _ = api("GET", "/VeiculoModelo")
    if st != 200:
        sys.exit(f"Servidor não respondeu em {BASE_URL} (status {st}). Suba o app.py antes de rodar.")

    limpar_restos()
    global PASTA_PRINTS
    PASTA_PRINTS = os.path.join(PASTA_BASE_PRINTS, datetime.now().strftime("%Y%m%d_%H%M%S"))
    webbrowser.open_new(BASE_URL + "/")
    contagem(6)
    apertar_f11 = "--ja-em-tela-cheia" not in sys.argv
    tela_cheia(ja_esta=not apertar_f11)

    # cada passo depende do anterior; se um falhar, para (menos a limpeza final)
    fluxo = [teste_navegacao, teste_criar_modelo, teste_editar_modelo, teste_criar_veiculo,
             teste_criar_componente,
             teste_calculo_veiculo_novo,                  # veículo novo ainda SEM composição
             teste_criar_material,                        # lote sem grupo de cálculo
             teste_catalogo, teste_catalogo_calculo,      # materiais novos no catálogo
             teste_criar_material_classificado,           # lote do material novo classificado
             teste_dados, teste_qr, teste_inventario,
             teste_calculo_itens_novos,
             teste_calculo_atividade]
    continuar = "--continuar" in sys.argv
    try:
        for t in fluxo:
            if not t() and not continuar:
                print("\nPasso falhou; interrompendo (use --continuar para seguir mesmo assim).")
                break
    except pyautogui.FailSafeException:
        print("\nAbortado pelo fail-safe (mouse no canto da tela).")
    except Exception:
        traceback.print_exc()
        checar("execução sem exceção", False)
    finally:
        try:
            if achar("/Veiculo", chassi=V_CHASSI) or achar("/VeiculoModelo", veiculo=V_VEICULO):
                teste_remover()               # remoção também é testada pela tela
        except Exception:
            traceback.print_exc()
        limpar_restos()                       # garante estado limpo mesmo se algo falhou
        if INDICE_PRINTS:
            with open(os.path.join(PASTA_PRINTS, "indice.json"), "w", encoding="utf-8") as f:
                json.dump(INDICE_PRINTS, f, ensure_ascii=False, indent=1)
        if apertar_f11:
            try:
                pyautogui.press("f11")        # sai da tela cheia
            except Exception:
                pass

    print("\n================ RESUMO ================")
    falhas = [r for r in RESULTADOS if not r[1]]
    for nome, ok, detalhe in RESULTADOS:
        print(f"[{'OK' if ok else 'FALHOU'}] {nome}" + (f"  -> {detalhe}" if detalhe and not ok else ""))
    print(f"\n{len(RESULTADOS) - len(falhas)}/{len(RESULTADOS)} verificações passaram. Prints (tela cheia) em: {PASTA_PRINTS}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()