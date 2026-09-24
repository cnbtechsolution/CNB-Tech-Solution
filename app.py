# ======================================================================
# ======================================================================
# [ATUALIZAÇÃO] EQUIPE / QUEM SOMOS GERENCIÁVEL PELO DASHBOARD
# Fotos, nome, cargo, descrição, ordem e publicação dos integrantes.
# ======================================================================
# CNB TECH SOLUTION - V20: REDES SOCIAIS + CONTATOS + RECORTE DE IMAGENS
# ======================================================================
# Esta versão mantém as funções da V19 e acrescenta comentários de estudo.
# Os comentários mostram:
#   - a FUNÇÃO de cada bloco importante;
#   - a SEÇÃO do site/painel que o código controla;
#   - o significado das CORES principais;
#   - a ligação entre PYTHON, HTML, CSS, JINJA e o BANCO SQLITE.
#
# IMPORTANTE: linhas iniciadas com # (Python), /* ... */ (CSS) e
# <!-- ... --> (HTML) são comentários e NÃO alteram o funcionamento.
# ======================================================================

# -------------------------- [IMPORTAÇÕES] ------------------------------
# Bibliotecas usadas pelo servidor, banco de dados, login, arquivos e e-mail.
import webbrowser
from threading import Timer
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, send_from_directory, abort, send_file
import sqlite3
from pathlib import Path
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from urllib.parse import quote
import os
import secrets
import smtplib
import re
import base64
from email.message import EmailMessage

# ----------------------------------------------------------------------
# -------- [V20 / GITHUB + RENDER: INICIALIZAÇÃO SEGURA] --------------
# ----------------------------------------------------------------------
# O mesmo arquivo roda localmente pelo IDLE e também no Render/Gunicorn.
# No Render, SECRET_KEY deve ser configurada em Environment Variables.
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent

# [RENDER / PERSISTÊNCIA]
# Se DATA_DIR estiver configurado (ex.: /var/data em um Persistent Disk),
# banco, uploads e anexos ficam fora do filesystem efêmero do deploy.
STORAGE_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR))).expanduser().resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY_AMBIENTE = os.environ.get("SECRET_KEY", "").strip()
if SECRET_KEY_AMBIENTE:
    app.secret_key = SECRET_KEY_AMBIENTE
else:
    # Fallback somente para execução local/testes. No Render use SECRET_KEY.
    app.secret_key = secrets.token_urlsafe(48)
    print("[!] AVISO: SECRET_KEY não configurada. Defina essa variável no Render.")

# Banco SQLite: localmente fica junto do projeto; no Render pode usar DATA_DIR.
BANCO_DADOS = STORAGE_DIR / "cnb_tech_solution.db"

# ----------------------------------------------------------------------
# -------- [VÍDEO DA HOME: ARQUIVO JUNTO COM O PYTHON] -----------------
# ----------------------------------------------------------------------
# Para evitar falhas de caminho no IDLE, o MP4 fica na MESMA pasta
# deste arquivo Python. O Flask entrega o vídeo pela rota /video-home.
VIDEO_HOME_NOME = "cnb-tech-home.mp4"
VIDEO_HOME_ARQUIVO = BASE_DIR / VIDEO_HOME_NOME

# ----------------------------------------------------------------------
# -- [V19 AJUSTADA: LOGO CNB TECH SOLUTION EM ARQUIVO EXTERNO] ---------
# ----------------------------------------------------------------------
# Esta versão mantém a BASE DA V12, que já roda normalmente no IDLE.
# A única mudança importante é a logo: ela NÃO fica mais em Base64.
# Coloque o PNG transparente abaixo na MESMA pasta deste arquivo Python.
# Isso deixa o .py leve e evita travamentos do editor do IDLE.
LOGO_CNB_NOME = "cnb-tech-logo-transparente.png"
LOGO_CNB_ARQUIVO = BASE_DIR / LOGO_CNB_NOME

# ----------------------------------------------------------------------
# -- [V19 AJUSTADA: MÍDIAS + TEMAS + CORES + LOGO NO PAINEL ADMIN] -----
# ----------------------------------------------------------------------
# Logo e vídeo atualizados pelo Dashboard ficam nesta pasta.
# O código Python não precisa ser editado quando a identidade visual muda.
PASTA_MIDIA_SITE = STORAGE_DIR / "midia_site"
PASTA_MIDIA_SITE.mkdir(exist_ok=True)
EXTENSOES_LOGO_SITE = {"png", "webp", "jpg", "jpeg"}
EXTENSOES_VIDEO_SITE = {"mp4"}

# ----------------------------------------------------------------------
# ---- [MÍDIAS PÚBLICAS: GALERIA / NOTÍCIAS] ---------------------------
# ----------------------------------------------------------------------
# Fotos e vídeos enviados pelo Dashboard ficam fora do .py para manter
# o arquivo leve e facilitar a atualização do conteúdo sem editar código.
PASTA_GALERIA = PASTA_MIDIA_SITE / "galeria"
PASTA_NOTICIAS = PASTA_MIDIA_SITE / "noticias"

# ----------------------------------------------------------------------
# -------- [MÍDIAS: EQUIPE / QUEM SOMOS] -------------------------------
# ----------------------------------------------------------------------
# As fotos dos integrantes da CNB Tech Solution são enviadas pelo
# Dashboard e ficam nesta pasta. Assim, a equipe pode ser atualizada
# sem editar o código Python.
PASTA_EQUIPE = PASTA_MIDIA_SITE / "equipe"  # <<<< [PASTA DAS FOTOS DA EQUIPE]

PASTA_GALERIA.mkdir(exist_ok=True)
PASTA_NOTICIAS.mkdir(exist_ok=True)
PASTA_EQUIPE.mkdir(exist_ok=True)

EXTENSOES_IMAGEM_PUBLICA = {"png", "webp", "jpg", "jpeg", "gif"}
EXTENSOES_VIDEO_PUBLICO = {"mp4", "webm"}

# Permite upload de vídeo pelo painel. O limite vale para qualquer POST com arquivo.
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024  # 250 MB

# ----------------------------------------------------------------------
# -------- [ARQUIVOS DOS ORÇAMENTOS: PDF / DOCX / POWERPOINT] ----------
# ----------------------------------------------------------------------
PASTA_ANEXOS = STORAGE_DIR / "anexos_orcamentos"
PASTA_ANEXOS.mkdir(exist_ok=True)
EXTENSOES_PERMITIDAS = {"pdf", "docx", "ppt", "pptx"}
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024  # Limite global: permite vídeo pelo editor visual

def arquivo_permitido(nome_arquivo):
    return "." in nome_arquivo and nome_arquivo.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS

# [PYTHON + SQLITE] Abre a conexão com o banco cnb_tech_solution.db.
def conectar_banco():
    conexao = sqlite3.connect(BANCO_DADOS)
    conexao.row_factory = sqlite3.Row
    return conexao

# [CONFIGURAÇÃO VISUAL] Lê do banco uma configuração salva pelo painel.
def obter_config_site(chave, padrao=""):
    try:
        with conectar_banco() as conexao:
            linha = conexao.execute("SELECT valor FROM site_config WHERE chave=?", (chave,)).fetchone()
            if linha is not None and linha["valor"] is not None:
                return linha["valor"]
    except sqlite3.Error:
        pass
    return padrao

# [CONFIGURAÇÃO VISUAL] Salva/atualiza no banco uma opção do site ou Admin.
def salvar_config_site(chave, valor):
    with conectar_banco() as conexao:
        conexao.execute(
            "INSERT INTO site_config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor)
        )

def extensao_arquivo(nome):
    return nome.rsplit(".", 1)[1].lower() if "." in nome else ""


# [PYTHON] Valida links externos usados nas notícias.
# Aceita somente HTTP/HTTPS para evitar protocolos indevidos no navegador.
def normalizar_url_externa(valor):
    valor = (valor or "").strip()
    if not valor:
        return ""
    if valor.lower().startswith(("http://", "https://")):
        return valor
    return ""


# [PYTHON] Salva imagem/vídeo com nome seguro e único.
def salvar_midia_publica(arquivo, pasta_destino, extensoes_permitidas, prefixo):
    if not arquivo or not arquivo.filename:
        return ""
    nome_original = secure_filename(arquivo.filename)
    extensao = extensao_arquivo(nome_original)
    if extensao not in extensoes_permitidas:
        return ""
    nome_base = Path(nome_original).stem[:60] or prefixo
    carimbo = datetime.now().strftime("%Y%m%d%H%M%S%f")
    nome_salvo = f"{prefixo}_{carimbo}_{nome_base}.{extensao}"
    arquivo.save(pasta_destino / nome_salvo)
    return nome_salvo


def apagar_midia_publica(pasta, nome_arquivo):
    if not nome_arquivo:
        return
    caminho = pasta / Path(nome_arquivo).name
    try:
        if caminho.exists() and caminho.is_file():
            caminho.unlink()
    except OSError:
        pass


# ----------------------------------------------------------------------
# -------- [V20: CONTATOS E REDES SOCIAIS - VALIDAÇÃO] -----------------
# ----------------------------------------------------------------------
# Estas funções são usadas pelo Dashboard para validar os contatos e
# transformar o telefone em links "tel:" e WhatsApp sem editar o código.
def normalizar_email_site(valor):
    valor = (valor or "").strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valor):
        return valor
    return ""


def somente_digitos(valor):
    return re.sub(r"\D+", "", valor or "")


def telefone_para_link(valor):
    digitos = somente_digitos(valor)
    if len(digitos) == 11:
        return "+55" + digitos
    if len(digitos) == 13 and digitos.startswith("55"):
        return "+" + digitos
    return "+" + digitos if digitos else ""


def telefone_para_whatsapp(valor):
    digitos = somente_digitos(valor)
    if len(digitos) == 11:
        return "55" + digitos
    if len(digitos) == 13 and digitos.startswith("55"):
        return digitos
    return digitos


# ----------------------------------------------------------------------
# -------- [V20: SALVAR IMAGEM RECORTADA PELO DASHBOARD] ---------------
# ----------------------------------------------------------------------
# O navegador recorta/enquadra a imagem em um Canvas e envia uma cópia
# JPEG em Base64. O Python valida o conteúdo e salva a imagem final.
# Assim, o usuário visualiza o enquadramento ANTES de publicar.
def salvar_imagem_recortada_base64(valor, pasta_destino, prefixo):
    valor = (valor or "").strip()
    if not valor or not valor.startswith("data:image/") or ";base64," not in valor:
        return ""

    try:
        cabecalho, dados = valor.split(",", 1)
        mime = cabecalho[5:].split(";", 1)[0].lower()
        extensoes = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        extensao = extensoes.get(mime)
        if not extensao:
            return ""

        bruto = base64.b64decode(dados, validate=True)

        # <<<< [LIMITE DE SEGURANÇA: 12 MB PARA A IMAGEM RECORTADA]
        if not bruto or len(bruto) > 12 * 1024 * 1024:
            return ""

        if extensao == "jpg" and not bruto.startswith(b"\xff\xd8\xff"):
            return ""
        if extensao == "png" and not bruto.startswith(b"\x89PNG\r\n\x1a\n"):
            return ""
        if extensao == "webp" and not (bruto[:4] == b"RIFF" and bruto[8:12] == b"WEBP"):
            return ""

        carimbo = datetime.now().strftime("%Y%m%d%H%M%S%f")
        nome_salvo = f"{prefixo}_{carimbo}_recortada.{extensao}"
        caminho = pasta_destino / nome_salvo
        caminho.write_bytes(bruto)
        return nome_salvo
    except (ValueError, OSError):
        return ""


# ----------------------------------------------------------------------
# -------- [V20: COMPONENTE VISUAL DE RECORTE / ENQUADRAMENTO] ---------
# ----------------------------------------------------------------------
# Gera uma interface reutilizável para fotos da equipe, galeria e notícias.
# Recursos: prévia, zoom, deslocamento horizontal/vertical e recorte final.
def html_recorte_imagem(
    input_name,
    input_id,
    hidden_name,
    bloco_id,
    titulo="Imagem",
    proporcao_largura=4,
    proporcao_altura=3,
    aceitar_video=False,
):
    largura_canvas = 960 if proporcao_largura == 16 else 800
    altura_canvas = 540 if proporcao_altura == 9 else 600
    accept = "image/*,video/mp4,video/webm" if aceitar_video else "image/*"

    html = r"""
    <!-- ============================================================ -->
    <!-- [V20 / HTML] RECORTE DE IMAGEM ANTES DE SALVAR               -->
    <!-- O arquivo original é escolhido abaixo. Se for uma imagem,     -->
    <!-- o Canvas abre a prévia para zoom e enquadramento.             -->
    <!-- ============================================================ -->
    <div class="crop-admin" id="__BLOCO__">
        <label>__TITULO__</label>
        <input class="campo crop-file" type="file" name="__INPUT_NAME__" id="__INPUT_ID__" accept="__ACCEPT__">
        <input type="hidden" name="__HIDDEN_NAME__" id="__BLOCO___resultado">

        <div class="crop-painel" id="__BLOCO___painel" hidden>
            <p class="nota-admin"><strong>Enquadre antes de salvar:</strong> ajuste zoom e posição até a imagem ficar como deseja.</p>
            <canvas id="__BLOCO___canvas" width="__CW__" height="__CH__"></canvas>

            <div class="crop-controles">
                <label>Zoom
                    <input type="range" min="100" max="260" value="100" id="__BLOCO___zoom">
                </label>
                <label>Horizontal
                    <input type="range" min="-100" max="100" value="0" id="__BLOCO___x">
                </label>
                <label>Vertical
                    <input type="range" min="-100" max="100" value="0" id="__BLOCO___y">
                </label>
            </div>
            <div class="crop-status" id="__BLOCO___status">Prévia pronta para salvar.</div>
        </div>
    </div>

    <style>
        /* [CSS] ÁREA DE RECORTE DO DASHBOARD */
        #__BLOCO__ .crop-painel {
            margin: 12px 0 18px;
            padding: 14px;
            border: 1px solid var(--admin-border);
            border-radius: 12px;
            background: var(--admin-bg);
        }
        #__BLOCO__ canvas {
            display: block;
            width: min(100%, 680px);
            height: auto;
            margin: 12px auto;
            border: 1px solid var(--admin-border);
            border-radius: 10px;
            background: #020617;
        }
        #__BLOCO__ .crop-controles {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
        }
        #__BLOCO__ .crop-controles label {
            margin: 0;
            font-size: .82rem;
        }
        #__BLOCO__ .crop-controles input[type=range] { width: 100%; }
        #__BLOCO__ .crop-status {
            color: var(--admin-accent);
            font-size: .78rem;
            font-weight: 700;
            margin-top: 9px;
        }
        @media (max-width: 680px) {
            #__BLOCO__ .crop-controles { grid-template-columns: 1fr; }
        }
    </style>

    <script>
    (() => {
        const input = document.getElementById("__INPUT_ID__");
        const painel = document.getElementById("__BLOCO___painel");
        const canvas = document.getElementById("__BLOCO___canvas");
        const hidden = document.getElementById("__BLOCO___resultado");
        const zoom = document.getElementById("__BLOCO___zoom");
        const posX = document.getElementById("__BLOCO___x");
        const posY = document.getElementById("__BLOCO___y");
        const status = document.getElementById("__BLOCO___status");

        if (!input || !painel || !canvas || !hidden) return;

        const ctx = canvas.getContext("2d");
        const imagem = new Image();
        let urlObjeto = "";

        function desenhar() {
            if (!imagem.naturalWidth || !imagem.naturalHeight) return;

            const cw = canvas.width;
            const ch = canvas.height;
            const escalaBase = Math.max(cw / imagem.naturalWidth, ch / imagem.naturalHeight);
            const escala = escalaBase * (Number(zoom.value) / 100);
            const dw = imagem.naturalWidth * escala;
            const dh = imagem.naturalHeight * escala;

            const sobraX = Math.max(0, dw - cw);
            const sobraY = Math.max(0, dh - ch);
            const dx = (cw - dw) / 2 + (Number(posX.value) / 100) * (sobraX / 2);
            const dy = (ch - dh) / 2 + (Number(posY.value) / 100) * (sobraY / 2);

            ctx.clearRect(0, 0, cw, ch);
            ctx.drawImage(imagem, dx, dy, dw, dh);

            hidden.value = canvas.toDataURL("image/jpeg", 0.90);
            status.textContent = "Enquadramento atualizado. Ao salvar, esta será a imagem publicada.";
        }

        input.addEventListener("change", () => {
            hidden.value = "";
            const arquivo = input.files && input.files[0];

            if (!arquivo) {
                painel.hidden = true;
                return;
            }

            if (!arquivo.type.startsWith("image/")) {
                painel.hidden = true;
                return;
            }

            if (urlObjeto) URL.revokeObjectURL(urlObjeto);
            urlObjeto = URL.createObjectURL(arquivo);

            imagem.onload = () => {
                zoom.value = "100";
                posX.value = "0";
                posY.value = "0";
                painel.hidden = false;
                desenhar();
            };
            imagem.src = urlObjeto;
        });

        [zoom, posX, posY].forEach(controle => controle.addEventListener("input", desenhar));
    })();
    </script>
    """

    trocas = {
        "__BLOCO__": bloco_id,
        "__TITULO__": titulo,
        "__INPUT_NAME__": input_name,
        "__INPUT_ID__": input_id,
        "__HIDDEN_NAME__": hidden_name,
        "__ACCEPT__": accept,
        "__CW__": str(largura_canvas),
        "__CH__": str(altura_canvas),
    }
    for chave, valor in trocas.items():
        html = html.replace(chave, str(valor))
    return html

# ----------------------------------------------------------------------
# -------- [V19 ATUALIZADA: SITE + DASHBOARD COM TEMAS E CORES] --------
# ----------------------------------------------------------------------
CONFIG_VISUAL_PADRAO = {
    "tema_site": "cnb-tech",       # <<<< [TEMA VISUAL ATIVO DA HOME]
    "logo_largura": "245",        # <<<< [TAMANHO DA LOGO NO TOPO / HOME]
    "cor_destaque": "#38bdf8",    # <<<< [AZUL DE DESTAQUE: BOTÕES, LINKS E ÍCONES]
    "cor_fundo": "#050c15",       # <<<< [COR DE FUNDO GERAL DA HOME]
    "cor_navbar": "#071426",      # <<<< [COR DA BARRA SUPERIOR / MENU]
    "cor_card": "#0f1e30",        # <<<< [COR DE FUNDO DOS CARDS DE SERVIÇOS]
    "cor_card_borda": "#334155",  # <<<< [COR DA BORDA DOS CARDS]
    "cor_titulo": "#f1f5f9",      # <<<< [COR DOS TÍTULOS PRINCIPAIS]
    "cor_texto": "#94a3b8",       # <<<< [COR DOS TEXTOS SECUNDÁRIOS]
    "card_radius": "14",          # <<<< [ARREDONDAMENTO DOS CARDS EM PIXELS]
    "overlay_video": "48",        # <<<< [ESCURECIMENTO DO VÍDEO DA HOME: 0 A 85]
    "animacao_cards": "media",    # <<<< [INTENSIDADE DA ANIMAÇÃO DOS CARDS]
}

# ----------------------------------------------------------------------
# ---- [PAINEL ADMIN: SINCRONIZAÇÃO COM O SITE + AJUSTE MANUAL] --------
# ----------------------------------------------------------------------
# Por padrão, o Dashboard acompanha a identidade visual do site.
# Ao desativar a sincronização no Editar Site 2.0, estas cores passam
# a controlar o painel administrativo de forma independente.
ADMIN_VISUAL_PADRAO = {
    "admin_sync_tema": "1",            # <<<< [1 = PAINEL HERDA AS CORES DO SITE]
    "admin_cor_fundo": "#050c15",      # <<<< [FUNDO GERAL DO DASHBOARD ADMIN]
    "admin_cor_topo": "#071426",       # <<<< [BARRA SUPERIOR DO PAINEL ADMIN]
    "admin_cor_superficie": "#0f1e30", # <<<< [CARDS, FORMULÁRIOS E BLOCOS DO ADMIN]
    "admin_cor_borda": "#334155",      # <<<< [BORDAS DOS ELEMENTOS DO ADMIN]
    "admin_cor_titulo": "#f1f5f9",     # <<<< [TÍTULOS E NÚMEROS DO DASHBOARD]
    "admin_cor_texto": "#94a3b8",      # <<<< [TEXTOS SECUNDÁRIOS DO ADMIN]
    "admin_cor_destaque": "#38bdf8",   # <<<< [BOTÕES, LINKS E REALCES DO ADMIN]
}


# ----------------------------------------------------------------------
# -------- [V20: CONTATOS E LINKS DAS REDES SOCIAIS] -------------------
# ----------------------------------------------------------------------
# Os valores são criados no banco na primeira execução da V20.
# Depois podem ser alterados em Dashboard > Contatos & Redes.
CONTATOS_REDES_PADRAO = {
    "contato_email": "cnbtvpara2019@gmail.com",  # <<<< [E-MAIL NO CONTATO E RODAPÉ]
    "contato_telefone": "(91) 99231-6147",       # <<<< [TELEFONE / WHATSAPP]
    "facebook_url": "",                          # <<<< [LINK DO FACEBOOK]
    "youtube_url": "",                           # <<<< [LINK DO YOUTUBE]
    "instagram_url": "",                         # <<<< [LINK DO INSTAGRAM]
}

# ----------------------------------------------------------------------
# -------------------- [PALETAS PRONTAS DO SITE] -----------------------
# ----------------------------------------------------------------------
# Cada tema abaixo preenche automaticamente as mesmas variáveis de cor.
# Depois de selecionar um tema no Admin, as cores ainda podem ser
# modificadas manualmente no Editar Site 2.0.
TEMAS_VISUAIS = {
    "cnb-tech": {
        "cor_destaque": "#38bdf8", "cor_fundo": "#050c15", "cor_navbar": "#071426",
        "cor_card": "#0f1e30", "cor_card_borda": "#334155", "cor_titulo": "#f1f5f9",
        "cor_texto": "#94a3b8", "card_radius": "14", "overlay_video": "48", "animacao_cards": "media"
    },
    "dark": {
        "cor_destaque": "#22d3ee", "cor_fundo": "#020617", "cor_navbar": "#020617",
        "cor_card": "#111827", "cor_card_borda": "#1f2937", "cor_titulo": "#f8fafc",
        "cor_texto": "#9ca3af", "card_radius": "10", "overlay_video": "62", "animacao_cards": "leve"
    },
    "corporate": {
        "cor_destaque": "#2563eb", "cor_fundo": "#0b1220", "cor_navbar": "#0f172a",
        "cor_card": "#172033", "cor_card_borda": "#334155", "cor_titulo": "#ffffff",
        "cor_texto": "#cbd5e1", "card_radius": "8", "overlay_video": "56", "animacao_cards": "leve"
    },
}

def normalizar_cor_hex(valor, padrao):
    valor = (valor or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", valor):
        return valor.lower()
    return padrao

def limitar_inteiro(valor, minimo, maximo, padrao):
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        numero = int(padrao)
    return max(minimo, min(maximo, numero))

def normalizar_opcao(valor, permitidas, padrao):
    return valor if valor in permitidas else padrao

def configuracao_visual_atual():
    cfg = {}
    cfg["tema_site"] = normalizar_opcao(
        obter_config_site("tema_site", CONFIG_VISUAL_PADRAO["tema_site"]),
        set(TEMAS_VISUAIS), CONFIG_VISUAL_PADRAO["tema_site"]
    )
    for chave in ("cor_destaque", "cor_fundo", "cor_navbar", "cor_card", "cor_card_borda", "cor_titulo", "cor_texto"):
        cfg[chave] = normalizar_cor_hex(obter_config_site(chave, CONFIG_VISUAL_PADRAO[chave]), CONFIG_VISUAL_PADRAO[chave])
    cfg["logo_largura"] = limitar_inteiro(obter_config_site("logo_largura", CONFIG_VISUAL_PADRAO["logo_largura"]), 140, 420, CONFIG_VISUAL_PADRAO["logo_largura"])
    cfg["card_radius"] = limitar_inteiro(obter_config_site("card_radius", CONFIG_VISUAL_PADRAO["card_radius"]), 0, 32, CONFIG_VISUAL_PADRAO["card_radius"])
    cfg["overlay_video"] = limitar_inteiro(obter_config_site("overlay_video", CONFIG_VISUAL_PADRAO["overlay_video"]), 0, 85, CONFIG_VISUAL_PADRAO["overlay_video"])
    cfg["animacao_cards"] = normalizar_opcao(obter_config_site("animacao_cards", CONFIG_VISUAL_PADRAO["animacao_cards"]), {"desligada", "leve", "media"}, CONFIG_VISUAL_PADRAO["animacao_cards"])
    return cfg

def configuracao_admin_atual():
    sync = obter_config_site("admin_sync_tema", ADMIN_VISUAL_PADRAO["admin_sync_tema"]) != "0"
    manual = {}
    for chave in (
        "admin_cor_fundo", "admin_cor_topo", "admin_cor_superficie",
        "admin_cor_borda", "admin_cor_titulo", "admin_cor_texto",
        "admin_cor_destaque"
    ):
        manual[chave] = normalizar_cor_hex(
            obter_config_site(chave, ADMIN_VISUAL_PADRAO[chave]),
            ADMIN_VISUAL_PADRAO[chave]
        )

    if sync:
        site = configuracao_visual_atual()
        efetiva = {
            "admin_cor_fundo": site["cor_fundo"],
            "admin_cor_topo": site["cor_navbar"],
            "admin_cor_superficie": site["cor_card"],
            "admin_cor_borda": site["cor_card_borda"],
            "admin_cor_titulo": site["cor_titulo"],
            "admin_cor_texto": site["cor_texto"],
            "admin_cor_destaque": site["cor_destaque"],
        }
    else:
        efetiva = manual.copy()

    return {"sync": sync, "manual": manual, "efetiva": efetiva}

# [BANCO DE DADOS] Cria as tabelas necessárias sem apagar dados existentes.
def iniciar_banco():
    with conectar_banco() as conexao:
        conexao.executescript("""
        CREATE TABLE IF NOT EXISTS administradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'administrador',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cnpj TEXT, responsavel TEXT, email TEXT, telefone TEXT,
            observacoes TEXT, criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orcamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL, empresa TEXT, email TEXT NOT NULL, telefone TEXT,
            servico TEXT NOT NULL, mensagem TEXT, status TEXT NOT NULL DEFAULT 'Novo',
            valor REAL, criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL, empresa TEXT, servico TEXT,
            status TEXT NOT NULL DEFAULT 'Planejamento', valor REAL,
            criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rota TEXT NOT NULL, ip TEXT, agente TEXT, criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS atividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_email TEXT, acao TEXT NOT NULL, criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS anexos_orcamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orcamento_id INTEGER NOT NULL,
            nome_original TEXT NOT NULL,
            nome_salvo TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (orcamento_id) REFERENCES orcamentos(id)
        );
        CREATE TABLE IF NOT EXISTS site_config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );
        CREATE TABLE IF NOT EXISTS galeria_publica (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            categoria TEXT,
            cliente_origem TEXT,
            tipo_midia TEXT NOT NULL DEFAULT 'imagem',
            arquivo TEXT,
            url_externa TEXT,
            destaque INTEGER NOT NULL DEFAULT 0,
            publicado INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS noticias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            resumo TEXT,
            conteudo TEXT,
            categoria TEXT,
            imagem TEXT,
            link_externo TEXT,
            destaque INTEGER NOT NULL DEFAULT 0,
            publicado INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        );

        -- ==============================================================
        -- [SQLITE] EQUIPE / QUEM SOMOS
        -- Guarda os integrantes exibidos na página Empresa.
        -- ==============================================================
        CREATE TABLE IF NOT EXISTS equipe_empresa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cargo TEXT NOT NULL,
            descricao TEXT,
            foto TEXT,
            ordem INTEGER NOT NULL DEFAULT 0,
            publicado INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        );
        """)
        # Atualiza bancos criados por versões anteriores sem apagar os dados existentes
        colunas_orcamento = {linha["name"] for linha in conexao.execute("PRAGMA table_info(orcamentos)").fetchall()}
        novas_colunas = {
            "tipo_cliente": "TEXT DEFAULT 'Empresa'",
            "documento": "TEXT",
            "cidade": "TEXT",
            "empresa_id": "INTEGER"
        }
        for nome_coluna, definicao in novas_colunas.items():
            if nome_coluna not in colunas_orcamento:
                conexao.execute(f"ALTER TABLE orcamentos ADD COLUMN {nome_coluna} {definicao}")

        # A tabela empresas também funciona como cadastro comercial de clientes/solicitantes.
        colunas_empresa = {linha["name"] for linha in conexao.execute("PRAGMA table_info(empresas)").fetchall()}
        novas_colunas_empresa = {
            "tipo_cliente": "TEXT DEFAULT 'Empresa'",
            "documento": "TEXT",
            "cidade": "TEXT"
        }
        for nome_coluna, definicao in novas_colunas_empresa.items():
            if nome_coluna not in colunas_empresa:
                conexao.execute(f"ALTER TABLE empresas ADD COLUMN {nome_coluna} {definicao}")

        # Configurações editáveis da Home. INSERT OR IGNORE preserva alterações do painel.
        configuracoes_padrao = {
            "status_home": "Ecossistema de soluções digitais",
            "titulo_home": "Tecnologia que conecta infraestrutura e inovação.",
            "subtitulo_home": "Soluções integradas para conectividade, infraestrutura de TI, desenvolvimento de sistemas, educação digital e produção audiovisual.",
            "rodape_home": "Tecnologia, infraestrutura e soluções digitais.",
            "logo_arquivo": "",
            "video_arquivo": "",

            # ----------------------------------------------------------
            # [V20] CONTATOS E REDES SOCIAIS
            # INSERT OR IGNORE mantém qualquer valor alterado no Dashboard.
            # ----------------------------------------------------------
            **CONTATOS_REDES_PADRAO,

            # ----------------------------------------------------------
            # [CONTEÚDO EDITÁVEL] PÁGINAS DE APLICAÇÃO DA TECNOLOGIA
            # Cada chave pode ser alterada pelo Dashboard / Conteúdo das Áreas.
            # ----------------------------------------------------------
            "industria_titulo": "Tecnologia aplicada à Indústria",
            "industria_subtitulo": "Infraestrutura, conectividade e sistemas digitais para operações industriais mais integradas, seguras e eficientes.",
            "industria_texto": "A CNB Tech Solution aplica tecnologia para conectar equipes, equipamentos, dados e processos. Nossas soluções podem apoiar ambientes operacionais que precisam de redes confiáveis, infraestrutura de TI, sistemas de gestão, monitoramento e comunicação audiovisual.",
            "industria_aplicacoes": "Redes corporativas e industriais\nInfraestrutura de servidores e estações\nIntegração de sistemas e dados\nMonitoramento e suporte técnico\nComunicação audiovisual para operações e treinamentos",

            "educacao_titulo": "Tecnologia aplicada à Educação",
            "educacao_subtitulo": "Ambientes digitais que ampliam o acesso ao conhecimento e conectam instituições, professores e alunos.",
            "educacao_texto": "Desenvolvemos e integramos recursos para educação presencial, híbrida e a distância, incluindo plataformas EAD, transmissão de aulas, produção audiovisual, infraestrutura de rede e ferramentas administrativas.",
            "educacao_aplicacoes": "Plataformas EAD e portais de aprendizagem\nAulas ao vivo e conteúdo gravado\nInfraestrutura de rede para escolas e centros de formação\nProdução de videoaulas e materiais digitais\nSistemas para gestão de turmas e usuários",

            "treinamentos_titulo": "Tecnologia para Treinamentos",
            "treinamentos_subtitulo": "Soluções digitais e audiovisuais para capacitação profissional, corporativa e técnica.",
            "treinamentos_texto": "A tecnologia pode transformar treinamentos em experiências mais organizadas, acessíveis e mensuráveis. A CNB Tech Solution integra transmissão, gravação, plataformas digitais, salas interativas e infraestrutura para programas de capacitação.",
            "treinamentos_aplicacoes": "Treinamentos corporativos presenciais e remotos\nSalas virtuais e transmissão ao vivo\nBiblioteca de aulas gravadas\nControle de acesso e apoio à presença\nProdução audiovisual para cursos e capacitações",

            "laboratorio_titulo": "Laboratório de Tecnologia e P&D",
            "laboratorio_subtitulo": "Pesquisa, testes, prototipagem e validação antes da implantação em ambiente real.",
            "laboratorio_texto": "O Laboratório representa a área de experimentação da CNB Tech Solution. É onde novas integrações, equipamentos, sistemas, redes e fluxos de trabalho podem ser avaliados antes de chegar à operação do cliente.",
            "laboratorio_aplicacoes": "Testes de hardware e software\nPrototipagem de sistemas e integrações\nValidação de redes, servidores e transmissão\nHomologação de novas tecnologias\nDemonstrações técnicas e provas de conceito",

            **CONFIG_VISUAL_PADRAO
        }
        for chave, valor in configuracoes_padrao.items():
            conexao.execute("INSERT OR IGNORE INTO site_config (chave, valor) VALUES (?, ?)", (chave, valor))

        existe = conexao.execute("SELECT id FROM administradores LIMIT 1").fetchone()
        if not existe:
            # ==========================================================
            # [V20 / PUBLICAÇÃO / SEGURANÇA] ADMIN INICIAL POR ENVIRONMENT
            # ==========================================================
            # Nenhuma senha administrativa fica gravada no GitHub.
            admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
            admin_password = os.environ.get("ADMIN_PASSWORD", "")
            admin_name = os.environ.get("ADMIN_NAME", "Administrador Master").strip() or "Administrador Master"

            if admin_email and admin_password:
                conexao.execute(
                    "INSERT INTO administradores (nome,email,senha_hash,perfil,ativo,criado_em) VALUES (?,?,?,?,?,?)",
                    (
                        admin_name,
                        admin_email,
                        generate_password_hash(admin_password),
                        "master",
                        1,
                        datetime.now().strftime("%d/%m/%Y %H:%M")
                    )
                )
                print(f"[+] Administrador inicial criado: {admin_email}")
            else:
                print("[!] Nenhum administrador cadastrado. Configure ADMIN_EMAIL e ADMIN_PASSWORD no Render.")

# Inicializa o banco também quando o app for executado por WSGI/Gunicorn/Render.
# O CREATE TABLE IF NOT EXISTS é idempotente e preserva os dados já existentes.
iniciar_banco()

def registrar_atividade(acao):
    with conectar_banco() as conexao:
        conexao.execute("INSERT INTO atividades (admin_email,acao,criado_em) VALUES (?,?,?)",
                        (session.get("admin_email", "sistema"), acao, datetime.now().strftime("%d/%m/%Y %H:%M")))

def login_obrigatorio(funcao):
    @wraps(funcao)
    def protegida(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return funcao(*args, **kwargs)
    return protegida

@app.before_request
def registrar_visita():
    if request.path.startswith("/static") or request.path.startswith("/admin"):
        return
    try:
        with conectar_banco() as conexao:
            conexao.execute("INSERT INTO visitas (rota,ip,agente,criado_em) VALUES (?,?,?,?)",
                            (request.path, request.remote_addr, request.headers.get("User-Agent", "")[:250], datetime.now().strftime("%d/%m/%Y %H:%M")))
    except sqlite3.Error:
        pass

# ----------------------------------------------------------------------
# ----------------- [INÍCIO DA PÁGINA: EMPRESA CNB TECH SOLUTION] -----
# ----------------------------------------------------------------------
# [ATUALIZAÇÃO VISUAL]
# Esta página agora herda automaticamente a MESMA PALETA selecionada
# no Editar Site 2.0. Assim, CNB Tech / Dark / Corporate e qualquer
# ajuste manual de cores também são aplicados na seção EMPRESA.
# ----------------------------------------------------------------------
LAYOUT_EMPRESA_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sobre a {{ nome_empresa }}</title>

    <!-- ================================================================ -->
    <!-- -------------------------- [CSS] -------------------------------- -->
    <!-- CSS = VISUAL, CORES, TAMANHOS E EFEITOS DA PÁGINA EMPRESA       -->
    <!-- ESTA PÁGINA USA AS MESMAS CORES DEFINIDAS NO EDITAR SITE 2.0     -->
    <!-- ================================================================ -->
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        html {
            scroll-behavior: smooth;
        }

        /* ============================================================ */
        /* 1. VARIÁVEIS DA PALETA VISUAL                               */
        /* Valores enviados pelo Python conforme o tema ativo do site. */
        /* ============================================================ */
        :root {
            --cnb-accent: {{ cor_destaque }};        /* <<<< [COR DE DESTAQUE: BOTÕES, LINHAS E ÍCONES] */
            --cnb-bg: {{ cor_fundo }};               /* <<<< [COR DE FUNDO: PÁGINA EMPRESA] */
            --cnb-navbar: {{ cor_navbar }};          /* <<<< [COR DE FUNDO: BARRA SUPERIOR] */
            --cnb-card: {{ cor_card }};              /* <<<< [COR DE FUNDO: BLOCOS / CARDS] */
            --cnb-card-border: {{ cor_card_borda }}; /* <<<< [COR DAS BORDAS: CARDS] */
            --cnb-title: {{ cor_titulo }};           /* <<<< [COR DOS TÍTULOS] */
            --cnb-text: {{ cor_texto }};             /* <<<< [COR DOS TEXTOS SECUNDÁRIOS] */
            --cnb-radius: {{ card_radius }}px;       /* <<<< [ARREDONDAMENTO DOS CARDS] */
            --cnb-logo: {{ logo_largura }}px;        /* <<<< [LARGURA DA LOGO] */
        }

        /* ============================================================ */
        /* 2. FUNDO GERAL DA PÁGINA EMPRESA                           */
        /* Mantém a mesma identidade escura/tecnológica da Home.       */
        /* ============================================================ */
        body {
            min-height: 100vh;
            background-color: var(--cnb-bg); /* <<<< [FUNDO GERAL: EMPRESA] */
            background-image:
                radial-gradient(circle at 12% 18%, color-mix(in srgb, var(--cnb-accent) 15%, transparent) 0, transparent 330px),
                radial-gradient(circle at 86% 28%, color-mix(in srgb, var(--cnb-accent) 10%, transparent) 0, transparent 360px),
                linear-gradient(135deg, color-mix(in srgb, var(--cnb-bg) 96%, #000000), var(--cnb-bg));
            color: var(--cnb-text); /* <<<< [TEXTO PADRÃO: EMPRESA] */
            line-height: 1.65;
        }

        /* Grade tecnológica discreta ao fundo da página. */
        body::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: 0.18;
            background-image:
                linear-gradient(color-mix(in srgb, var(--cnb-accent) 11%, transparent) 1px, transparent 1px),
                linear-gradient(90deg, color-mix(in srgb, var(--cnb-accent) 11%, transparent) 1px, transparent 1px);
            background-size: 46px 46px;
            mask-image: linear-gradient(to bottom, rgba(0,0,0,.8), transparent 82%);
        }

        /* ============================================================ */
        /* 3. BARRA SUPERIOR / NAVBAR                                  */
        /* Mesma linguagem visual utilizada na página inicial.         */
        /* ============================================================ */
        .navbar {
            position: relative;
            z-index: 10;
            min-height: 108px;
            overflow: hidden;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 24px;
            padding: 26px 5%;
            background-color: var(--cnb-navbar); /* <<<< [FUNDO: NAVBAR EMPRESA] */
            background-image:
                radial-gradient(circle at 10% 50%, color-mix(in srgb, var(--cnb-accent) 24%, transparent) 0, transparent 310px),
                radial-gradient(circle at 90% 60%, color-mix(in srgb, var(--cnb-accent) 16%, transparent) 0, transparent 300px),
                linear-gradient(110deg, color-mix(in srgb, var(--cnb-navbar) 92%, #000000), var(--cnb-navbar));
            border-bottom: 1px solid color-mix(in srgb, var(--cnb-accent) 25%, transparent); /* <<<< [BORDA: NAVBAR] */
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.30);
        }

        /* [CSS] LOGO DA CNB TECH SOLUTION */
        .logo {
            position: relative;
            z-index: 2;
            display: flex;
            align-items: center;
            flex-shrink: 0;
            text-decoration: none;
        }

        .logo-img {
            width: min(var(--cnb-logo), 310px); /* <<<< [TAMANHO DA LOGO: HERDADO DO EDITAR SITE] */
            max-height: 96px;
            object-fit: contain;
            display: block;
            border-radius: 10px;
            filter: drop-shadow(0 0 12px color-mix(in srgb, var(--cnb-accent) 25%, transparent));
            transition: transform 0.25s ease, filter 0.25s ease;
        }

        .logo:hover .logo-img {
            transform: scale(1.025);
            filter: drop-shadow(0 0 17px color-mix(in srgb, var(--cnb-accent) 42%, transparent));
        }

        /* [CSS] BOTÃO PARA VOLTAR À HOME */
        .btn-voltar {
            position: relative;
            z-index: 2;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: var(--cnb-accent); /* <<<< [FUNDO: BOTÃO VOLTAR] */
            color: #06101c;               /* <<<< [TEXTO: BOTÃO VOLTAR] */
            text-decoration: none;
            padding: 10px 17px;
            border-radius: 8px;
            font-weight: 800;
            font-size: 0.88rem;
            box-shadow: 0 8px 22px color-mix(in srgb, var(--cnb-accent) 22%, transparent);
            transition: transform 0.22s ease, filter 0.22s ease, box-shadow 0.22s ease;
        }

        .btn-voltar:hover {
            transform: translateY(-2px);
            filter: brightness(1.10);
            box-shadow: 0 12px 28px color-mix(in srgb, var(--cnb-accent) 30%, transparent);
        }

        /* ============================================================ */
        /* 4. HERO / CABEÇALHO DA SEÇÃO EMPRESA                        */
        /* Apresenta a área institucional com o padrão premium da Home. */
        /* ============================================================ */
        .empresa-hero {
            position: relative;
            z-index: 2;
            max-width: 1180px;
            margin: 0 auto;
            padding: 68px 5% 28px;
            text-align: center;
        }

        .empresa-status {
            width: fit-content;
            margin: 0 auto 18px;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 7px 13px;
            border-radius: 30px;
            border: 1px solid color-mix(in srgb, var(--cnb-accent) 30%, transparent); /* <<<< [BORDA: INDICADOR EMPRESA] */
            background: color-mix(in srgb, var(--cnb-card) 72%, transparent);          /* <<<< [FUNDO: INDICADOR EMPRESA] */
            color: var(--cnb-text);
            font-size: 0.78rem;
            backdrop-filter: blur(8px);
        }

        .empresa-status-ponto {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--cnb-accent); /* <<<< [COR: PONTO DO INDICADOR] */
            box-shadow: 0 0 12px color-mix(in srgb, var(--cnb-accent) 70%, transparent);
        }

        .empresa-hero h1 {
            max-width: 900px;
            margin: 0 auto 16px;
            font-size: clamp(2.1rem, 4vw, 3.3rem);
            line-height: 1.12;
            color: var(--cnb-title); /* <<<< [COR: TÍTULO PRINCIPAL EMPRESA] */
        }

        .empresa-hero h1 span {
            color: var(--cnb-accent); /* <<<< [COR: DESTAQUE NO TÍTULO EMPRESA] */
        }

        .empresa-hero p {
            max-width: 760px;
            margin: 0 auto;
            color: var(--cnb-text); /* <<<< [COR: SUBTÍTULO EMPRESA] */
            font-size: 1rem;
        }

        /* Linha tecnológica abaixo do título. */
        .linha-tech {
            width: 92px;
            height: 3px;
            margin: 26px auto 0;
            border-radius: 20px;
            background: linear-gradient(90deg, transparent, var(--cnb-accent), transparent); /* <<<< [COR: LINHA DE DESTAQUE] */
            box-shadow: 0 0 18px color-mix(in srgb, var(--cnb-accent) 45%, transparent);
        }

        /* ============================================================ */
        /* 5. CONTEÚDO INSTITUCIONAL / CARDS                           */
        /* Quem Somos, O Que Fazemos e Políticas da Empresa.           */
        /* ============================================================ */
        .container {
            position: relative;
            z-index: 2;
            max-width: 1120px;
            margin: 0 auto;
            padding: 28px 5% 85px;
        }

        .grid-empresa {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 20px;
            align-items: stretch;
        }

        .bloco-info {
            position: relative;
            overflow: hidden;
            min-height: 100%;
            background: color-mix(in srgb, var(--cnb-card) 92%, transparent); /* <<<< [FUNDO: CARD EMPRESA] */
            border: 1px solid var(--cnb-card-border);                         /* <<<< [BORDA: CARD EMPRESA] */
            border-radius: var(--cnb-radius);                                 /* <<<< [ARREDONDAMENTO: CARD EMPRESA] */
            padding: 30px 27px;
            box-shadow: 0 14px 35px rgba(0, 0, 0, 0.22);
            backdrop-filter: blur(10px);
            transition: transform 0.28s ease, border-color 0.28s ease, box-shadow 0.28s ease;
        }

        /* Brilho decorativo no canto superior do card. */
        .bloco-info::before {
            content: "";
            position: absolute;
            top: -70px;
            right: -70px;
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: color-mix(in srgb, var(--cnb-accent) 16%, transparent);
            filter: blur(8px);
            transition: transform 0.28s ease, opacity 0.28s ease;
        }

        /* Linha azul/cor de destaque no topo do card. */
        .bloco-info::after {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, var(--cnb-accent), transparent); /* <<<< [DESTAQUE: TOPO DOS CARDS] */
        }

        .bloco-info:hover {
            transform: translateY(-6px);
            border-color: color-mix(in srgb, var(--cnb-accent) 72%, var(--cnb-card-border));
            box-shadow: 0 20px 42px rgba(0, 0, 0, 0.31), 0 0 24px color-mix(in srgb, var(--cnb-accent) 10%, transparent);
        }

        .bloco-info:hover::before {
            transform: scale(1.12);
        }

        /* [CSS] ÍCONE DO CARD INSTITUCIONAL */
        .icone-bloco {
            width: 48px;
            height: 48px;
            display: grid;
            place-items: center;
            margin-bottom: 20px;
            border-radius: 12px;
            background: color-mix(in srgb, var(--cnb-accent) 14%, transparent); /* <<<< [FUNDO: ÍCONE EMPRESA] */
            border: 1px solid color-mix(in srgb, var(--cnb-accent) 28%, transparent);
            color: var(--cnb-accent); /* <<<< [COR: ÍCONE EMPRESA] */
            font-size: 1.35rem;
            font-weight: 800;
        }

        .bloco-info h2 {
            position: relative;
            z-index: 2;
            font-size: 1.22rem;
            color: var(--cnb-title); /* <<<< [COR: TÍTULO DO CARD] */
            margin-bottom: 13px;
        }

        .bloco-info p {
            position: relative;
            z-index: 2;
            color: var(--cnb-text); /* <<<< [COR: TEXTO DO CARD] */
            font-size: 0.95rem;
        }

        .bloco-info strong {
            color: var(--cnb-title); /* <<<< [COR: PALAVRAS IMPORTANTES] */
        }

        .bloco-info ul {
            position: relative;
            z-index: 2;
            list-style: none;
            margin-top: 15px;
        }

        .bloco-info li {
            position: relative;
            padding-left: 18px;
            margin-bottom: 11px;
            color: var(--cnb-text); /* <<<< [COR: ITENS DAS LISTAS] */
            font-size: 0.92rem;
        }

        .bloco-info li::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0.67em;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--cnb-accent); /* <<<< [COR: MARCADOR DAS LISTAS] */
            box-shadow: 0 0 8px color-mix(in srgb, var(--cnb-accent) 60%, transparent);
        }

        /* ============================================================ */
        /* 6. NOSSA EQUIPE / CARDS DOS INTEGRANTES                     */
        /* Fotos, nomes, cargos e descrições vêm do Dashboard.          */
        /* ============================================================ */
        .equipe-secao {
            margin-top: 34px; /* <<<< [ESPAÇO ACIMA DA SEÇÃO NOSSA EQUIPE] */
        }

        .equipe-cabecalho {
            text-align: center;
            max-width: 760px;
            margin: 0 auto 24px;
        }

        .equipe-cabecalho h2 {
            color: var(--cnb-title); /* <<<< [COR: TÍTULO NOSSA EQUIPE] */
            font-size: clamp(1.7rem, 3vw, 2.35rem);
            margin-bottom: 8px;
        }

        .equipe-cabecalho p {
            color: var(--cnb-text); /* <<<< [COR: SUBTÍTULO NOSSA EQUIPE] */
        }

        .equipe-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr)); /* <<<< [3 CARDS POR LINHA] */
            gap: 20px;
        }

        .membro-card {
            overflow: hidden;
            background: color-mix(in srgb, var(--cnb-card) 94%, transparent); /* <<<< [FUNDO: CARD DO INTEGRANTE] */
            border: 1px solid var(--cnb-card-border);                         /* <<<< [BORDA: CARD DO INTEGRANTE] */
            border-radius: var(--cnb-radius);                                 /* <<<< [ARREDONDAMENTO: CARD DO INTEGRANTE] */
            box-shadow: 0 14px 34px rgba(0,0,0,.22);
            transition: transform .25s ease, border-color .25s ease, box-shadow .25s ease;
        }

        .membro-card:hover {
            transform: translateY(-5px);
            border-color: color-mix(in srgb, var(--cnb-accent) 62%, var(--cnb-card-border));
            box-shadow: 0 20px 42px rgba(0,0,0,.30);
        }

        .membro-foto {
            width: 100%;
            aspect-ratio: 4 / 3; /* <<<< [FORMATO DA FOTO DO INTEGRANTE] */
            object-fit: cover;
            object-position: center;
            display: block;
            background: color-mix(in srgb, var(--cnb-card) 82%, #000);
        }

        /* Mostrado quando ainda não foi enviada uma foto pelo Dashboard. */
        .membro-foto-placeholder {
            width: 100%;
            aspect-ratio: 4 / 3;
            display: grid;
            place-items: center;
            background:
                radial-gradient(circle at 50% 25%, color-mix(in srgb, var(--cnb-accent) 22%, transparent), transparent 45%),
                var(--cnb-card);
            color: var(--cnb-accent); /* <<<< [COR: INICIAL DO NOME SEM FOTO] */
            font-size: 3.4rem;
            font-weight: 900;
        }

        .membro-info {
            padding: 20px;
        }

        .membro-info h3 {
            color: var(--cnb-title); /* <<<< [COR: NOME DO INTEGRANTE] */
            font-size: 1.08rem;
            margin-bottom: 5px;
        }

        .membro-cargo {
            color: var(--cnb-accent); /* <<<< [COR: CARGO / FUNÇÃO] */
            font-size: .84rem;
            font-weight: 800;
            margin-bottom: 11px;
        }

        .membro-descricao {
            color: var(--cnb-text); /* <<<< [COR: DESCRIÇÃO DO INTEGRANTE] */
            font-size: .88rem;
            line-height: 1.55;
        }

        .equipe-vazia {
            grid-column: 1 / -1;
            padding: 24px;
            text-align: center;
            color: var(--cnb-text);
            border: 1px dashed var(--cnb-card-border);
            border-radius: var(--cnb-radius);
            background: color-mix(in srgb, var(--cnb-card) 72%, transparent);
        }

        /* ============================================================ */
        /* 7. FAIXA FINAL / CHAMADA PARA SOLUÇÕES                       */
        /* ============================================================ */
        .empresa-cta {
            margin-top: 24px;
            padding: 25px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
            background: color-mix(in srgb, var(--cnb-card) 88%, transparent); /* <<<< [FUNDO: CHAMADA FINAL] */
            border: 1px solid var(--cnb-card-border);                         /* <<<< [BORDA: CHAMADA FINAL] */
            border-radius: var(--cnb-radius);
            box-shadow: 0 14px 32px rgba(0,0,0,.20);
        }

        .empresa-cta h3 {
            color: var(--cnb-title); /* <<<< [COR: TÍTULO DA CHAMADA FINAL] */
            margin-bottom: 4px;
        }

        .empresa-cta p {
            color: var(--cnb-text); /* <<<< [COR: TEXTO DA CHAMADA FINAL] */
            font-size: 0.92rem;
        }

        .empresa-cta a {
            flex-shrink: 0;
            text-decoration: none;
            background: var(--cnb-accent); /* <<<< [FUNDO: BOTÃO CONHECER SOLUÇÕES] */
            color: #06101c;
            padding: 10px 16px;
            border-radius: 8px;
            font-weight: 800;
            transition: transform .22s ease, filter .22s ease;
        }

        .empresa-cta a:hover {
            transform: translateY(-2px);
            filter: brightness(1.10);
        }

        /* ============================================================ */
        /* 7. RESPONSIVIDADE / CELULAR                                 */
        /* ============================================================ */
        @media (max-width: 900px) {
            .grid-empresa {
                grid-template-columns: 1fr;
            }

            .equipe-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr)); /* <<<< [TABLET: 2 INTEGRANTES POR LINHA] */
            }

            .empresa-cta {
                flex-direction: column;
                align-items: flex-start;
            }
        }

        @media (max-width: 640px) {
            .equipe-grid {
                grid-template-columns: 1fr; /* <<<< [CELULAR: 1 INTEGRANTE POR LINHA] */
            }

            .navbar {
                min-height: auto;
                padding: 18px 20px;
            }

            .logo-img {
                width: min(var(--cnb-logo), 190px);
            }

            .btn-voltar {
                padding: 9px 12px;
                font-size: 0.78rem;
            }

            .empresa-hero {
                padding: 48px 20px 20px;
            }

            .container {
                padding: 24px 20px 60px;
            }

            .bloco-info {
                padding: 25px 22px;
            }
        }
    </style>
</head>

<!-- ================================================================ -->
<!-- -------------------------- [HTML] ------------------------------- -->
<!-- HTML = ESTRUTURA E CONTEÚDO VISÍVEL DA PÁGINA EMPRESA           -->
<!-- ================================================================ -->
<body>

    <!-- ============================================================ -->
    <!-- [HTML] BARRA SUPERIOR: MESMA LOGO E IDENTIDADE DA HOME      -->
    <!-- ============================================================ -->
    <header class="navbar">
        <a href="/" class="logo" aria-label="{{ nome_empresa }} - Página inicial">
            <img src="/logo-cnb?v=19" class="logo-img" alt="{{ nome_empresa }}">
        </a>
        <a href="/" class="btn-voltar">← Voltar ao Início</a>
    </header>

    <!-- ============================================================ -->
    <!-- [HTML] CABEÇALHO PRINCIPAL DA SEÇÃO EMPRESA                  -->
    <!-- ============================================================ -->
    <section class="empresa-hero">
        <div class="empresa-status">
            <span class="empresa-status-ponto"></span>
            Institucional • CNB Tech Solution
        </div>

        <h1>Engenharia, infraestrutura e <span>soluções em tecnologia</span></h1>
        <p>Infraestrutura, inovação e soluções digitais integradas para empresas e instituições que precisam conectar tecnologia, operação e crescimento.</p>
        <div class="linha-tech"></div>
    </section>

    <!-- ============================================================ -->
    <!-- [HTML] CONTEÚDO INSTITUCIONAL: 3 CARDS PRINCIPAIS            -->
    <!-- ============================================================ -->
    <main class="container">
        <div class="grid-empresa">

            <!-- [CARD 1] QUEM SOMOS -->
            <section class="bloco-info">
                <div class="icone-bloco">CNB</div>
                <h2>Quem Somos</h2>
                <p>A <strong>{{ nome_empresa }}</strong> é uma integradora de soluções digitais especializada em automação, arquitetura de servidores de alta disponibilidade e computação em nuvem. Nascemos com a missão de transformar rotinas industriais e operacionais através de softwares de alto desempenho e telemetria em tempo real.</p>
            </section>

            <!-- [CARD 2] O QUE FAZEMOS -->
            <section class="bloco-info">
                <div class="icone-bloco">⚙</div>
                <h2>O Que Fazemos</h2>
                <p>Desenvolvemos ecossistemas tecnológicos integrados para empresas que exigem confiabilidade, desempenho e segurança:</p>
                <ul>
                    <li><strong>Monitoramento de Servidores:</strong> Rastreamento contínuo de recursos e diagnósticos de latência.</li>
                    <li><strong>Desenvolvimento de Software:</strong> Aplicações web modernas e APIs robustas de backend.</li>
                    <li><strong>Laboratório de P&D:</strong> Pesquisa, testes e validação de novas tecnologias.</li>
                </ul>
            </section>

            <!-- [CARD 3] POLÍTICAS DA EMPRESA -->
            <section class="bloco-info">
                <div class="icone-bloco">◆</div>
                <h2>Políticas da Empresa</h2>
                <p>Nossas diretrizes corporativas são baseadas em segurança, disponibilidade e evolução tecnológica:</p>
                <ul>
                    <li><strong>Segurança & Privacidade:</strong> Proteção de sistemas, redes e dados.</li>
                    <li><strong>Disponibilidade Contínua:</strong> Infraestrutura resiliente para serviços digitais.</li>
                    <li><strong>Inovação Sustentável:</strong> Otimização constante de hardware, software e processamento.</li>
                </ul>
            </section>

        </div>

        <!-- ============================================================ -->
        <!-- [HTML + JINJA] NOSSA EQUIPE                                  -->
        <!-- Cada card abaixo é carregado do banco SQLite pelo Python.     -->
        <!-- Foto, nome, cargo, descrição, ordem e publicação vêm do Admin.-->
        <!-- ============================================================ -->
        <section class="equipe-secao" id="nossa-equipe">
            <div class="equipe-cabecalho">
                <h2>Nossa Equipe</h2>
                <p>Profissionais que unem tecnologia, operação, inovação e experiência para transformar necessidades em soluções.</p>
            </div>

            <div class="equipe-grid">
                {% for membro in equipe %}
                <article class="membro-card">
                    {% if membro.foto %}
                    <img class="membro-foto" src="/midia-equipe/{{ membro.foto }}" alt="{{ membro.nome }}">
                    {% else %}
                    <div class="membro-foto-placeholder">{{ membro.nome[0] if membro.nome else 'C' }}</div>
                    {% endif %}

                    <div class="membro-info">
                        <h3>{{ membro.nome }}</h3>
                        <div class="membro-cargo">{{ membro.cargo }}</div>
                        {% if membro.descricao %}
                        <p class="membro-descricao">{{ membro.descricao }}</p>
                        {% endif %}
                    </div>
                </article>
                {% else %}
                <div class="equipe-vazia">Os integrantes da equipe serão exibidos aqui quando forem cadastrados pelo Dashboard.</div>
                {% endfor %}
            </div>
        </section>

        <!-- [HTML] CHAMADA FINAL PARA VOLTAR ÀS SOLUÇÕES DA HOME -->
        <section class="empresa-cta">
            <div>
                <h3>Tecnologia aplicada à necessidade de cada projeto.</h3>
                <p>Conheça os serviços e módulos que fazem parte do ecossistema CNB Tech Solution.</p>
            </div>
            <a href="/#servicos">Conhecer Soluções</a>
        </section>
    </main>

</body>
</html>
"""

# ----------------------------------------------------------------------
# ------------------ [FIM DA PÁGINA: EMPRESA TECH] ---------------------
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# -------- [PÁGINAS: INDÚSTRIA / EDUCAÇÃO / TREINAMENTOS / LAB] -------
# ----------------------------------------------------------------------
# Um único template atende as quatro áreas. O Python troca título, texto,
# aplicações e ícone conforme a rota escolhida. As cores vêm do tema ativo.
LAYOUT_AREA_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ titulo }} | CNB Tech Solution</title>
    <style>
        * { box-sizing:border-box; margin:0; padding:0; font-family:'Segoe UI',Tahoma,sans-serif; }
        :root {
            --cnb-accent: {{ cor_destaque }};        /* <<<< [COR DE DESTAQUE DA ÁREA] */
            --cnb-bg: {{ cor_fundo }};               /* <<<< [FUNDO DA PÁGINA] */
            --cnb-navbar: {{ cor_navbar }};          /* <<<< [FUNDO DA BARRA SUPERIOR] */
            --cnb-card: {{ cor_card }};              /* <<<< [FUNDO DOS CARDS] */
            --cnb-border: {{ cor_card_borda }};      /* <<<< [BORDA DOS CARDS] */
            --cnb-title: {{ cor_titulo }};           /* <<<< [COR DOS TÍTULOS] */
            --cnb-text: {{ cor_texto }};             /* <<<< [COR DOS TEXTOS] */
            --cnb-radius: {{ card_radius }}px;
        }
        body { min-height:100vh; background:var(--cnb-bg); color:var(--cnb-text); line-height:1.65; }
        .navbar { min-height:104px; padding:20px 5%; display:flex; align-items:center; justify-content:space-between; gap:20px; background:linear-gradient(110deg,var(--cnb-navbar),color-mix(in srgb,var(--cnb-navbar) 80%,var(--cnb-accent)),var(--cnb-navbar)); border-bottom:1px solid color-mix(in srgb,var(--cnb-accent) 28%,transparent); }
        .logo-img { width:min({{ logo_largura }}px,280px); max-height:88px; object-fit:contain; filter:drop-shadow(0 0 12px color-mix(in srgb,var(--cnb-accent) 30%,transparent)); }
        .btn-voltar,.btn-cta { text-decoration:none; color:#06101c; background:var(--cnb-accent); padding:10px 16px; border-radius:9px; font-weight:800; display:inline-flex; align-items:center; gap:8px; }
        .hero-area { padding:72px 5% 35px; text-align:center; background:radial-gradient(circle at 50% 0,color-mix(in srgb,var(--cnb-accent) 18%,transparent),transparent 420px); }
        .area-icone { width:62px; height:62px; margin:0 auto 18px; display:grid; place-items:center; border:1px solid color-mix(in srgb,var(--cnb-accent) 34%,transparent); border-radius:16px; color:var(--cnb-accent); background:color-mix(in srgb,var(--cnb-card) 82%,transparent); font-size:1.7rem; font-weight:900; }
        .hero-area h1 { color:var(--cnb-title); font-size:clamp(2rem,4vw,3.2rem); margin-bottom:14px; }
        .hero-area p { max-width:800px; margin:auto; font-size:1.05rem; }
        .wrap-area { max-width:1120px; margin:auto; padding:25px 5% 75px; }
        .apresentacao { padding:28px; background:var(--cnb-card); border:1px solid var(--cnb-border); border-radius:var(--cnb-radius); box-shadow:0 15px 36px rgba(0,0,0,.20); }
        .apresentacao h2,.aplicacoes h2 { color:var(--cnb-title); margin-bottom:12px; }
        .aplicacoes { margin-top:22px; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:15px; }
        .aplicacao { padding:18px 20px; border-radius:var(--cnb-radius); background:var(--cnb-card); border:1px solid var(--cnb-border); color:var(--cnb-text); }
        .aplicacao::before { content:'✓'; color:var(--cnb-accent); font-weight:900; margin-right:9px; }
        .cta-area { margin-top:24px; padding:24px 26px; display:flex; justify-content:space-between; align-items:center; gap:18px; background:color-mix(in srgb,var(--cnb-card) 94%,transparent); border:1px solid var(--cnb-border); border-radius:var(--cnb-radius); }
        .cta-area h3 { color:var(--cnb-title); }
        @media(max-width:700px){ .navbar{flex-direction:column;align-items:flex-start}.aplicacoes{grid-template-columns:1fr}.cta-area{flex-direction:column;align-items:flex-start}.logo-img{width:min({{ logo_largura }}px,200px)} }
    </style>
</head>
<body>
    <!-- [HTML] CABEÇALHO DA PÁGINA DE APLICAÇÃO -->
    <header class="navbar">
        <a href="/"><img class="logo-img" src="/logo-cnb" alt="CNB Tech Solution"></a>
        <a class="btn-voltar" href="/">← Voltar ao Início</a>
    </header>

    <section class="hero-area">
        <div class="area-icone">{{ icone }}</div>
        <h1>{{ titulo }}</h1>
        <p>{{ subtitulo }}</p>
    </section>

    <main class="wrap-area">
        <section class="apresentacao">
            <h2>Onde a tecnologia se aplica</h2>
            <p>{{ texto }}</p>
        </section>
        <section class="aplicacoes">
            {% for item in aplicacoes %}<div class="aplicacao">{{ item }}</div>{% endfor %}
        </section>
        <section class="cta-area">
            <div><h3>Precisa aplicar essa tecnologia no seu projeto?</h3><p>Conheça as soluções da CNB Tech Solution e solicite uma análise da sua necessidade.</p></div>
            <a class="btn-cta" href="/#servicos">Ver soluções</a>
        </section>
    </main>
</body>
</html>
"""


# ----------------------------------------------------------------------
# ---------------- [PÁGINA PÚBLICA: PROJETOS & GALERIA] ----------------
# ----------------------------------------------------------------------
LAYOUT_GALERIA_HTML = """
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Projetos & Galeria | CNB Tech Solution</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;background:{{ cor_fundo }};color:{{ cor_texto }}}a{color:inherit}.top{padding:20px 5%;display:flex;justify-content:space-between;align-items:center;gap:20px;background:{{ cor_navbar }};border-bottom:1px solid {{ cor_card_borda }}}.top img{width:min({{ logo_largura }}px,270px);max-height:90px;object-fit:contain}.voltar{background:{{ cor_destaque }};color:#06101c;text-decoration:none;font-weight:800;padding:10px 15px;border-radius:8px}.hero{text-align:center;padding:58px 5% 28px}.hero h1{color:{{ cor_titulo }};font-size:clamp(2rem,4vw,3rem);margin:0 0 10px}.hero p{max-width:760px;margin:auto}.grid{max-width:1180px;margin:auto;padding:25px 5% 75px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.item{overflow:hidden;background:{{ cor_card }};border:1px solid {{ cor_card_borda }};border-radius:{{ card_radius }}px;box-shadow:0 14px 32px rgba(0,0,0,.2)}.midia{width:100%;aspect-ratio:16/10;background:#020617;display:block;object-fit:cover}.conteudo{padding:18px}.tag{display:inline-block;font-size:.72rem;font-weight:800;color:{{ cor_destaque }};margin-bottom:7px}.conteudo h3{color:{{ cor_titulo }};margin:0 0 8px}.conteudo p{margin:0;line-height:1.55;font-size:.9rem}.externo{display:inline-block;margin-top:12px;color:{{ cor_destaque }};font-weight:800;text-decoration:none}.vazio{grid-column:1/-1;text-align:center;padding:45px;border:1px dashed {{ cor_card_borda }};border-radius:12px}@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.grid{grid-template-columns:1fr}.top{flex-direction:column;align-items:flex-start}}
</style></head><body>
<header class="top"><a href="/"><img src="/logo-cnb" alt="CNB Tech Solution"></a><a class="voltar" href="/">← Início</a></header>
<section class="hero"><h1>Projetos & Galeria</h1><p>Registros de projetos, instalações, produções, testes, clientes e atividades da CNB Tech Solution.</p></section>
<main class="grid">
{% for item in itens %}
<article class="item">
{% if item.tipo_midia == 'video' and item.arquivo %}<video class="midia" controls preload="metadata"><source src="/midia-galeria/{{ item.arquivo }}"></video>
{% elif item.arquivo %}<img class="midia" src="/midia-galeria/{{ item.arquivo }}" alt="{{ item.titulo }}">
{% else %}<div class="midia" style="display:grid;place-items:center;color:{{ cor_destaque }};font-weight:800">CNB TECH</div>{% endif %}
<div class="conteudo"><span class="tag">{{ item.categoria or 'Projeto' }}{% if item.cliente_origem %} • {{ item.cliente_origem }}{% endif %}</span><h3>{{ item.titulo }}</h3><p>{{ item.descricao or '' }}</p>{% if item.url_externa %}<a class="externo" href="{{ item.url_externa }}" target="_blank" rel="noopener noreferrer">Abrir conteúdo ↗</a>{% endif %}</div>
</article>
{% else %}<div class="vazio">Nenhum item publicado na galeria ainda.</div>{% endfor %}
</main></body></html>
"""


# ----------------------------------------------------------------------
# ---------------------- [PÁGINA PÚBLICA: NOTÍCIAS] --------------------
# ----------------------------------------------------------------------
LAYOUT_NOTICIAS_HTML = """
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Notícias | CNB Tech Solution</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;background:{{ cor_fundo }};color:{{ cor_texto }}}.top{padding:20px 5%;display:flex;justify-content:space-between;align-items:center;background:{{ cor_navbar }};border-bottom:1px solid {{ cor_card_borda }}}.top img{width:min({{ logo_largura }}px,270px);max-height:90px;object-fit:contain}.voltar,.ler{background:{{ cor_destaque }};color:#06101c;text-decoration:none;font-weight:800;padding:9px 14px;border-radius:8px;display:inline-block}.hero{text-align:center;padding:58px 5% 25px}.hero h1{color:{{ cor_titulo }};font-size:clamp(2rem,4vw,3rem);margin:0 0 10px}.grid{max-width:1120px;margin:auto;padding:25px 5% 75px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.card{overflow:hidden;background:{{ cor_card }};border:1px solid {{ cor_card_borda }};border-radius:{{ card_radius }}px;display:flex;flex-direction:column}.capa{width:100%;aspect-ratio:16/9;object-fit:cover;background:#020617}.corpo{padding:18px;display:flex;flex-direction:column;flex:1}.meta{font-size:.74rem;color:{{ cor_destaque }};font-weight:800;margin-bottom:8px}.corpo h2{font-size:1.08rem;color:{{ cor_titulo }};margin:0 0 9px}.corpo p{font-size:.9rem;line-height:1.55;margin:0 0 15px}.ler{margin-top:auto;align-self:flex-start}.vazio{grid-column:1/-1;text-align:center;padding:45px;border:1px dashed {{ cor_card_borda }};border-radius:12px}@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.grid{grid-template-columns:1fr}.top{flex-direction:column;gap:12px;align-items:flex-start}}
</style></head><body>
<header class="top"><a href="/"><img src="/logo-cnb" alt="CNB Tech Solution"></a><a class="voltar" href="/">← Início</a></header>
<section class="hero"><h1>Notícias & Tecnologia</h1><p>Conteúdo sobre tecnologia, inovação, projetos e atualizações selecionadas pela CNB Tech Solution.</p></section>
<main class="grid">
{% for item in itens %}<article class="card">{% if item.imagem %}<img class="capa" src="/midia-noticias/{{ item.imagem }}" alt="{{ item.titulo }}">{% else %}<div class="capa" style="display:grid;place-items:center;color:{{ cor_destaque }};font-weight:900">CNB TECH NEWS</div>{% endif %}<div class="corpo"><div class="meta">{{ item.categoria or 'Tecnologia' }} • {{ item.criado_em }}</div><h2>{{ item.titulo }}</h2><p>{{ item.resumo or '' }}</p>{% if item.link_externo %}<a class="ler" href="{{ item.link_externo }}" target="_blank" rel="noopener noreferrer">Ler notícia ↗</a>{% else %}<a class="ler" href="/noticias/{{ item.id }}">Ler notícia →</a>{% endif %}</div></article>
{% else %}<div class="vazio">Nenhuma notícia publicada ainda.</div>{% endfor %}
</main></body></html>
"""

LAYOUT_NOTICIA_DETALHE_HTML = """
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{{ noticia.titulo }} | CNB Tech Solution</title>
<style>*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;background:{{ cor_fundo }};color:{{ cor_texto }};line-height:1.75}.top{padding:18px 5%;background:{{ cor_navbar }};border-bottom:1px solid {{ cor_card_borda }};display:flex;justify-content:space-between;align-items:center}.top img{width:min({{ logo_largura }}px,260px);max-height:84px;object-fit:contain}.btn{background:{{ cor_destaque }};color:#06101c;text-decoration:none;font-weight:800;padding:9px 14px;border-radius:8px}.artigo{max-width:900px;margin:auto;padding:55px 5% 80px}.meta{color:{{ cor_destaque }};font-weight:800;font-size:.8rem}.artigo h1{color:{{ cor_titulo }};font-size:clamp(2rem,4vw,3.1rem);line-height:1.15}.resumo{font-size:1.08rem}.capa{width:100%;max-height:520px;object-fit:cover;border-radius:{{ card_radius }}px;margin:24px 0;border:1px solid {{ cor_card_borda }}}.conteudo{white-space:pre-wrap;background:{{ cor_card }};border:1px solid {{ cor_card_borda }};padding:25px;border-radius:{{ card_radius }}px}</style></head><body>
<header class="top"><a href="/"><img src="/logo-cnb" alt="CNB Tech Solution"></a><a class="btn" href="/noticias">← Notícias</a></header><article class="artigo"><div class="meta">{{ noticia.categoria or 'Tecnologia' }} • {{ noticia.criado_em }}</div><h1>{{ noticia.titulo }}</h1><p class="resumo">{{ noticia.resumo or '' }}</p>{% if noticia.imagem %}<img class="capa" src="/midia-noticias/{{ noticia.imagem }}" alt="{{ noticia.titulo }}">{% endif %}<div class="conteudo">{{ noticia.conteudo or noticia.resumo or '' }}</div></article></body></html>
"""


# ----------------------------------------------------------------------
# -------------------- [INÍCIO DA HOME PAGE: VISUAL] -------------------
# ----------------------------------------------------------------------
LAYOUT_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ nome_empresa }} - Tecnologia & Soluções</title>

    <!-- ============================================================= -->
    <!-- =========================== [CSS] ============================ -->
    <!-- CSS = VISUAL, CORES, TAMANHOS, FUNDOS E ANIMAÇÕES            -->
    <!-- ============================================================= -->

    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        html {
            scroll-behavior: smooth;
        }

        /* 1. FUNDO GERAL DA TELA */
        body {
            background-color: #050c15;  /* <<<< [COR DE FUNDO: SITE INTEIRO / HOME] */
            color: #e2e8f0;             /* <<<< [COR DO TEXTO: PADRÃO DA HOME] */
        }

        /* ============================================================ */
        /* 2. BARRA SUPERIOR (NAVBAR)                                 */
        /* ============================================================ */
        .navbar {
            position: relative;
            overflow: hidden;
            min-height: 108px;
            background-color: #071426; /* <<<< [COR BASE: BARRA SUPERIOR / NAVBAR] */
            background-image:
                radial-gradient(circle at 10% 50%,
                    rgba(14, 165, 233, 0.25) 0px,
                    rgba(14, 165, 233, 0.07) 160px,
                    transparent 320px),
                radial-gradient(circle at 90% 60%,
                    rgba(37, 99, 235, 0.20) 0px,
                    transparent 300px),
                linear-gradient(110deg, #050c16, #0f2740, #07111f);

            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 25px;
            padding: 28px 5%;
            color: #ffffff;
            border-bottom: 1px solid rgba(56, 189, 248, 0.20);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.30);
            z-index: 10;
        }

        /* 3. LOGO CNB TECH SOLUTION - NOVA IDENTIDADE VISUAL */
        .logo {
            position: relative;
            z-index: 2;
            display: flex;
            align-items: center;
            flex-shrink: 0;
            text-decoration: none;
        }

        .logo-img {
            width: 205px; /* <<<< [TAMANHO BASE DA LOGO NA HOME] */
            max-height: 94px;
            object-fit: contain;
            display: block;
            border-radius: 10px;
            filter: drop-shadow(0 0 12px rgba(0, 174, 255, 0.22));
            transition: transform 0.25s ease, filter 0.25s ease;
        }

        .logo:hover .logo-img {
            transform: scale(1.025);
            filter: drop-shadow(0 0 16px rgba(0, 210, 255, 0.35));
        }

        /* 4. LINKS DO MENU */
        .nav-links {
            position: relative;
            z-index: 2;
            display: flex;
            align-items: center;
            list-style: none;
            gap: 24px;
        }

        .nav-links a {
            position: relative;
            color: #cbd5e1; /* <<<< [COR NORMAL: TEXTOS DO MENU SUPERIOR] */
            text-decoration: none;
            font-size: 0.90rem; /* <<<< [TAMANHO DO TEXTO DO MENU] */
            font-weight: 500;
            display: inline-block;
            padding: 8px 0;
            transition: transform 0.25s ease, color 0.25s ease;
        }

        .nav-links a::after {
            content: ""; /* <<<< [LINHA AZUL QUE APARECE SOB O ITEM DO MENU] */
            position: absolute;
            left: 50%;
            bottom: 0;
            width: 0;
            height: 2px;
            background: #38bdf8; /* <<<< [COR DA LINHA DE DESTAQUE DO MENU] */
            transform: translateX(-50%);
            transition: width 0.25s ease;
        }

        .nav-links a:hover {
            transform: translateY(-2px) scale(1.08); /* <<<< [ZOOM + MOVIMENTO DO MENU] */
            color: #ffffff; /* <<<< [COR DO MENU AO PASSAR O MOUSE] */
        }

        .nav-links a:hover::after {
            width: 70%;
        }

        /* 5. CAMPO DE BUSCA */
        .search-container {
            position: relative;
            z-index: 2;
            display: flex;
            align-items: center;
            flex-shrink: 0;
            background: rgba(15, 23, 42, 0.72); /* <<<< [FUNDO: CAMPO DE BUSCA] */
            border-radius: 8px;
            padding: 5px;
            border: 1px solid rgba(148, 163, 184, 0.20);
        }

        .search-container input {
            background: transparent;
            border: none;
            color: #ffffff;
            outline: none;
            padding: 7px 9px;
            font-size: 0.85rem;
            width: 155px;
        }

        .search-container button {
            background: #38bdf8; /* <<<< [FUNDO: BOTÃO BUSCAR] */
            border: none;
            color: #07111f;         /* <<<< [TEXTO: BOTÃO BUSCAR] */
            font-weight: bold;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
        }

        /* ============================================================ */
        /* 6. ÁREA PRINCIPAL - FUNDO TECNOLÓGICO COM VÍDEO             */
        /* ============================================================ */
        /* ============================================================ */
        /* 6. HOME / HERO: vídeo, camada de contraste, título e cards      */
        /* ============================================================ */
        .hero {
            position: relative;
            overflow: hidden;
            max-width: 100%;
            min-height: 680px;
            margin: 0;
            padding: 65px 5% 80px;

            /* Fundo de segurança: aparece enquanto o vídeo carrega
               ou caso o navegador bloqueie a reprodução automática. */
            background-color: #050c15; /* <<<< [FUNDO DE SEGURANÇA CASO O VÍDEO NÃO CARREGUE] */
            background-image:
                radial-gradient(circle at 15% 25%,
                    rgba(14, 165, 233, 0.18) 0px,
                    transparent 320px),
                radial-gradient(circle at 82% 30%,
                    rgba(37, 99, 235, 0.17) 0px,
                    transparent 340px),
                linear-gradient(135deg, #050b13, #091827 50%, #050c15);
        }

        /* ------------------------------------------------------------ */
        /* 6.1 VÍDEO DE FUNDO                                          */
        /* O vídeo fica atrás de todo o conteúdo da página.             */
        /* ------------------------------------------------------------ */
        /* [VÍDEO DA HOME] fica atrás dos textos e cards */
        .hero-video {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center center;
            z-index: 0;

            /* Transparência e tratamento visual para não competir
               com os textos, botões e cartões da página principal. */
            opacity: 0.72;
            filter: saturate(0.86) contrast(0.96) brightness(0.82);
            pointer-events: none;
            user-select: none;
        }

        /* ------------------------------------------------------------ */
        /* 6.2 CAMADA ESCURA SOBRE O VÍDEO                             */
        /* Garante contraste e leitura confortável em qualquer cena.    */
        /* ------------------------------------------------------------ */
        /* [OVERLAY] escurece o vídeo para o texto ficar legível */
        .hero-video-overlay {
            position: absolute;
            inset: 0;
            z-index: 1;
            pointer-events: none;
            background:
                radial-gradient(circle at 50% 22%,
                    rgba(14, 165, 233, 0.10) 0px,
                    transparent 420px),
                linear-gradient(90deg,
                    rgba(5, 12, 21, 0.56) 0%,
                    rgba(5, 12, 21, 0.42) 48%,
                    rgba(5, 12, 21, 0.54) 100%),
                linear-gradient(180deg,
                    rgba(5, 12, 21, 0.16) 0%,
                    rgba(5, 12, 21, 0.36) 100%);
        }

        /* ------------------------------------------------------------ */
        /* 6.3 CONTEÚDO ACIMA DO VÍDEO                                */
        /* Mantém títulos, cartões e botões sempre na frente.           */
        /* ------------------------------------------------------------ */
        .hero-conteudo {
            position: relative;
            z-index: 2;
            max-width: 1180px;
            margin: 0 auto;
        }

        /* 7. INDICADOR DE TECNOLOGIA */
        .status-tech {
            width: fit-content;
            margin: 0 auto 17px;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 7px 13px;
            border-radius: 30px;
            border: 1px solid rgba(56, 189, 248, 0.20);
            background: rgba(15, 23, 42, 0.55);
            color: #94a3b8; /* <<<< [COR: SUBTÍTULO DA HOME] */
            font-size: 0.78rem;
        }

        .status-ponto {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #22c55e;
            box-shadow: 0 0 10px rgba(34, 197, 94, 0.65);
        }

        /* 8. TÍTULO PRINCIPAL */
        .hero-cabecalho {
            max-width: 800px;
            margin: 0 auto 48px;
            text-align: center;
        }

        .hero-cabecalho h1 {
            font-size: clamp(2.1rem, 4vw, 3.2rem);
            line-height: 1.13;
            color: #f8fafc; /* <<<< [COR: TÍTULO PRINCIPAL DA HOME] */
            margin-bottom: 17px;
        }

        .hero-cabecalho h1 span {
            color: #38bdf8; /* <<<< [AZUL DE DESTAQUE: PALAVRA / TRECHO DO TÍTULO] */
        }

        .hero-cabecalho p {
            max-width: 680px;
            margin: 0 auto;
            font-size: 1rem;
            line-height: 1.7;
            color: #94a3b8; /* <<<< [COR: SUBTÍTULO PRINCIPAL DA HOME] */
        }

        /* 9. GRADE DOS CARTÕES */
        .grid-servicos {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 18px;
        }

        /* 10. CARTÕES DE SERVIÇOS */
        /* ============================================================ */
        /* 7. CARDS DE SERVIÇOS: fundo, borda, ícone, textos e botões     */
        /* ============================================================ */
        .card-servico {
            position: relative;
            overflow: hidden;
            min-height: 205px;
            display: flex;
            flex-direction: column;
            background: linear-gradient(145deg,
                        rgba(15, 30, 48, 0.94),
                        rgba(9, 21, 35, 0.96));
            padding: 25px;
            border-radius: 12px;
            border: 1px solid rgba(148, 163, 184, 0.12); /* <<<< [BORDA: CARD DE SERVIÇO] */
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
            text-decoration: none;
            transition: transform 0.28s ease,
                        box-shadow 0.28s ease,
                        border-color 0.28s ease;
        }

        .card-servico:hover {
            transform: translateY(-6px);
            border-color: rgba(56, 189, 248, 0.38);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.28);
        }

        /* ============================================================ */
        /* 11. ÍCONES SVG DOS SERVIÇOS                                 */
        /* Cada card recebe um desenho vetorial correspondente à função.*/
        /* "currentColor" faz o SVG acompanhar a COR DE DESTAQUE do tema.*/
        /* ============================================================ */
        .card-icone {
            width: 50px;                 /* <<<< [LARGURA: BLOCO DO ÍCONE] */
            height: 50px;                /* <<<< [ALTURA: BLOCO DO ÍCONE] */
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 18px;
            border-radius: 12px;         /* <<<< [ARREDONDAMENTO: BLOCO DO ÍCONE] */
            background: rgba(56, 189, 248, 0.09);
            border: 1px solid rgba(56, 189, 248, 0.15);
            color: #38bdf8;              /* <<<< [COR BASE: ÍCONE SVG] */
            box-shadow: inset 0 0 18px rgba(56, 189, 248, 0.03);
            transition: transform 0.28s ease, box-shadow 0.28s ease, background 0.28s ease;
        }

        /* [CSS] TAMANHO E TRAÇO DOS DESENHOS SVG */
        .card-icone svg {
            width: 27px;                 /* <<<< [TAMANHO: DESENHO DO ÍCONE] */
            height: 27px;
            display: block;
            fill: none;
            stroke: currentColor;        /* <<<< [HERDA A COR DA PALETA DO SITE] */
            stroke-width: 1.8;
            stroke-linecap: round;
            stroke-linejoin: round;
            vector-effect: non-scaling-stroke;
            filter: drop-shadow(0 0 5px color-mix(in srgb, currentColor 28%, transparent));
        }

        /* [CSS] EFEITO DO ÍCONE QUANDO O MOUSE PASSA SOBRE O CARD */
        .card-servico:hover .card-icone {
            transform: translateY(-2px) scale(1.06);
            background: color-mix(in srgb, var(--cnb-accent) 16%, transparent);
            box-shadow: 0 0 22px color-mix(in srgb, var(--cnb-accent) 18%, transparent);
        }

        /* 12. TÍTULO DOS SERVIÇOS */
        .card-servico h3 {
            font-size: 1.05rem;
            color: #f1f5f9; /* <<<< [COR: TÍTULO DO CARD DE SERVIÇO] */
            margin-bottom: 9px;
            transition: transform 0.25s ease, color 0.25s ease;
        }

        .card-servico:hover h3 {
            transform: translateX(3px);
            color: #38bdf8;
        }

        .card-servico p {
            font-size: 0.85rem;
            line-height: 1.6;
            color: #94a3b8; /* <<<< [COR: DESCRIÇÃO DO CARD DE SERVIÇO] */
            margin-bottom: 18px;
        }

        .card-link {
            margin-top: auto;
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 600;
        }

        .card-servico:hover .card-link {
            color: #38bdf8;
        }

        .card-acoes {
            margin-top: auto;
            display: flex;
            gap: 9px;
            flex-wrap: wrap;
        }

        .card-link, .card-orcamento {
            display: inline-block;
            text-decoration: none;
            border-radius: 7px;
            padding: 9px 11px;
            font-size: 0.78rem;
            font-weight: 700;
        }

        .card-link {
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.18);
        }

        .card-orcamento {
            background: #38bdf8; /* <<<< [FUNDO: BOTÃO ORÇAMENTO NO CARD] */
            color: #07111f;      /* <<<< [TEXTO: BOTÃO ORÇAMENTO NO CARD] */
        }

        /* 13. RODAPÉ */
        .footer {
            background: #040a11; /* <<<< [FUNDO: RODAPÉ DA HOME] */
            border-top: 1px solid rgba(148, 163, 184, 0.10);
            padding: 22px 5%;
            text-align: center;
            color: #475569;
            font-size: 0.78rem;
        }

        /* 14. RESPONSIVIDADE */
        @media (max-width: 1100px) {
            .navbar {
                flex-wrap: wrap;
            }

            .nav-links {
                order: 3;
                width: 100%;
                justify-content: center;
                flex-wrap: wrap;
            }

            .grid-servicos {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 700px) {
            .navbar {
                padding: 20px;
            }

            .logo-img {
                width: 165px;
                max-height: 80px;
            }

            .search-container {
                display: none;
            }

            .nav-links {
                gap: 12px 18px;
            }

            .hero {
                padding: 50px 20px 65px;
            }

            .grid-servicos {
                grid-template-columns: 1fr;
            }
        }


        /* ============================================================ */
        /* 15. EDITAR SITE 2.0 - VARIÁVEIS CONTROLADAS PELO ADMIN      */
        /* ============================================================ */
        /* Os valores Jinja abaixo vêm do Python/SQLite e permitem
           trocar a paleta sem editar manualmente este CSS. */
        :root {
            --cnb-accent: {{ cor_destaque }};        /* <<<< [DESTAQUE: botões, links e ícones] */
            --cnb-bg: {{ cor_fundo }};               /* <<<< [FUNDO GERAL DA HOME] */
            --cnb-navbar: {{ cor_navbar }};          /* <<<< [FUNDO DA NAVBAR] */
            --cnb-card: {{ cor_card }};              /* <<<< [FUNDO DOS CARDS] */
            --cnb-card-border: {{ cor_card_borda }}; /* <<<< [BORDA DOS CARDS] */
            --cnb-title: {{ cor_titulo }};           /* <<<< [TÍTULOS PRINCIPAIS] */
            --cnb-text: {{ cor_texto }};             /* <<<< [TEXTOS SECUNDÁRIOS] */
            --cnb-radius: {{ card_radius }}px;        /* <<<< [ARREDONDAMENTO DOS CARDS] */
        }

        body { background-color: var(--cnb-bg); }
        .navbar {
            background-color: var(--cnb-navbar);
            background-image: linear-gradient(110deg, var(--cnb-navbar), #0f2740, var(--cnb-navbar));
            border-bottom-color: color-mix(in srgb, var(--cnb-accent) 28%, transparent);
        }
        .logo-img {
            width: {{ logo_largura }}px;
            max-height: 132px;
            filter: drop-shadow(0 0 12px color-mix(in srgb, var(--cnb-accent) 28%, transparent));
        }
        .logo:hover .logo-img {
            filter: drop-shadow(0 0 18px color-mix(in srgb, var(--cnb-accent) 42%, transparent));
        }
        .nav-links a::after, .search-container button, .card-orcamento { background: var(--cnb-accent); }
        .hero { background-color: var(--cnb-bg); }
        .hero-video-overlay {
            background: linear-gradient(180deg, rgba(5,12,21,{{ overlay_alpha_top }}), rgba(5,12,21,{{ overlay_alpha_bottom }}));
        }
        .status-tech { border-color: color-mix(in srgb, var(--cnb-accent) 25%, transparent); }
        .hero-cabecalho h1, .card-servico h3 { color: var(--cnb-title); }
        .hero-cabecalho p, .card-servico p { color: var(--cnb-text); }
        .hero-cabecalho h1 span, .card-icone, .card-servico:hover h3, .card-servico:hover .card-link { color: var(--cnb-accent); }
        .card-servico {
            background: var(--cnb-card);
            border-color: var(--cnb-card-border);
            border-radius: var(--cnb-radius);
            transition-duration: {{ animacao_duracao }};
        }
        .card-servico:hover {
            transform: {{ animacao_transform }};
            border-color: var(--cnb-accent);
            box-shadow: {{ animacao_sombra }};
        }
        .card-icone {
            background: color-mix(in srgb, var(--cnb-accent) 11%, transparent);
            border-color: color-mix(in srgb, var(--cnb-accent) 25%, transparent);
        }
        .card-link { color: var(--cnb-text); border-color: var(--cnb-card-border); }
        .footer { background: var(--cnb-navbar); color: var(--cnb-text); }

        @media (max-width: 700px) {
            .logo-img { width: min({{ logo_largura }}px, 210px); max-height: 96px; }
        }


        /* ============================================================ */
        /* 16. HOME: PRÉVIA DE GALERIA, NOTÍCIAS E CONTATO             */
        /* As cores abaixo seguem a paleta escolhida no Editar Site.   */
        /* ============================================================ */
        .home-secao { background:var(--cnb-bg); padding:62px 5%; border-top:1px solid var(--cnb-card-border); }
        .home-secao-inner { max-width:1180px; margin:0 auto; }
        .home-secao-cabecalho { display:flex; justify-content:space-between; align-items:end; gap:18px; margin-bottom:24px; }
        .home-secao-cabecalho h2 { color:var(--cnb-title); font-size:1.8rem; margin:0 0 5px; }
        .home-secao-cabecalho p { color:var(--cnb-text); margin:0; }
        .home-secao-link { color:var(--cnb-accent); text-decoration:none; font-weight:800; white-space:nowrap; }
        .home-galeria-grid,.home-noticias-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }
        .home-midia-card,.home-noticia-card { overflow:hidden; background:var(--cnb-card); border:1px solid var(--cnb-card-border); border-radius:var(--cnb-radius); text-decoration:none; color:var(--cnb-text); transition:.25s ease; }
        .home-midia-card:hover,.home-noticia-card:hover { transform:translateY(-4px); border-color:var(--cnb-accent); }
        .home-midia-preview,.home-noticia-capa { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; background:#020617; }
        .home-midia-info,.home-noticia-info { padding:16px; }
        .home-midia-info strong,.home-noticia-info strong { display:block; color:var(--cnb-title); margin-bottom:6px; }
        .home-tag { color:var(--cnb-accent); font-size:.72rem; font-weight:800; display:block; margin-bottom:6px; }
        .home-noticia-info p,.home-midia-info p { font-size:.84rem; line-height:1.5; margin:0; }
        .home-contato { background:linear-gradient(120deg,var(--cnb-navbar),var(--cnb-card)); }
        .contato-card { max-width:1180px; margin:auto; display:flex; justify-content:space-between; align-items:center; gap:24px; padding:28px; border:1px solid var(--cnb-card-border); border-radius:var(--cnb-radius); background:color-mix(in srgb,var(--cnb-card) 90%,transparent); }
        .contato-card h2 { color:var(--cnb-title); margin:0 0 7px; }
        .contato-acoes { display:flex; gap:10px; flex-wrap:wrap; }
        .contato-btn { text-decoration:none; font-weight:800; padding:11px 15px; border-radius:8px; border:1px solid var(--cnb-accent); color:var(--cnb-accent); }
        .contato-btn.primario { background:var(--cnb-accent); color:var(--cnb-bg); }

        /* ============================================================ */
        /* [V20 / CSS] CARDS DAS REDES SOCIAIS                         */
        /* Links são cadastrados pelo Dashboard > Contatos & Redes.    */
        /* ============================================================ */
        .home-redes { background:var(--cnb-bg); }
        .redes-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }
        .rede-card {
            min-height:150px; padding:23px; display:flex; flex-direction:column;
            justify-content:space-between; gap:15px; text-decoration:none;
            background:var(--cnb-card); border:1px solid var(--cnb-card-border);
            border-radius:var(--cnb-radius); color:var(--cnb-text);
            transition:transform .25s ease,border-color .25s ease,box-shadow .25s ease;
        }
        .rede-card[href]:hover { transform:translateY(-4px); border-color:var(--cnb-accent); box-shadow:0 16px 34px rgba(0,0,0,.24); }
        .rede-card.desativado { opacity:.62; cursor:default; }
        .rede-topo { display:flex; align-items:center; gap:12px; }
        .rede-icone {
            width:44px;height:44px;display:grid;place-items:center;border-radius:11px;
            border:1px solid color-mix(in srgb,var(--cnb-accent) 35%,transparent);
            background:color-mix(in srgb,var(--cnb-accent) 10%,transparent);
            color:var(--cnb-accent);
        }
        .rede-icone svg { width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round; }
        .rede-card strong { color:var(--cnb-title); font-size:1.04rem; }
        .rede-card small { color:var(--cnb-text); }

        /* ============================================================ */
        /* [V20 / CSS] RODAPÉ COM E-MAIL E TELEFONE                    */
        /* ============================================================ */
        .footer { text-align:left; }
        .footer-inner { max-width:1180px;margin:auto;display:flex;justify-content:space-between;align-items:center;gap:20px; }
        .footer-marca { display:flex;flex-direction:column;gap:4px; }
        .footer-marca strong { color:var(--cnb-title); }
        .footer-contatos { display:flex;gap:14px;flex-wrap:wrap;justify-content:flex-end; }
        .footer-contatos a { color:var(--cnb-accent);text-decoration:none;font-weight:700; }

        @media(max-width:900px){
            .home-galeria-grid,.home-noticias-grid{grid-template-columns:repeat(2,1fr)}
            .redes-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
        }
        @media(max-width:650px){
            .home-galeria-grid,.home-noticias-grid,.redes-grid{grid-template-columns:1fr}
            .home-secao-cabecalho,.contato-card,.footer-inner{align-items:flex-start;flex-direction:column}
            .footer-contatos{justify-content:flex-start}
        }
    </style>
</head>


<!-- ================================================================ -->
<!-- ============================ [HTML] ============================= -->
<!-- HTML = ESTRUTURA VISÍVEL DA HOME                                -->
<!-- ================================================================ -->

<body>

    <!-- [HTML] BARRA SUPERIOR: logo + menu de navegação + campo de busca -->
    <header class="navbar">

        <!-- Logo da Empresa -->
        <a href="/" class="logo" aria-label="CNB Tech Solution - Página inicial">
            <img src="/logo-cnb?v=12" class="logo-img" alt="CNB Tech Solution">
        </a>

        <!-- Títulos da Home Page -->
        <ul class="nav-links">
            <li><a href="/empresa">Empresa</a></li>
            <li><a href="#servicos">Soluções</a></li>
            <li><a href="/industria">Indústria</a></li>
            <li><a href="/educacao">Educação</a></li>
            <li><a href="/treinamentos">Treinamentos</a></li>
            <li><a href="/laboratorio">Laboratório</a></li>
            <li><a href="/galeria">Galeria</a></li>
            <li><a href="/noticias">Notícias</a></li>
            <li><a href="#contato">Contato</a></li>
        </ul>

        <!-- Campo de Busca -->
        <div class="search-container">
            <input type="text" placeholder="Buscar...">
            <button type="button">Buscar</button>
        </div>
    </header>


    <!-- [HTML] HOME / HERO: vídeo de fundo + textos + cards de serviços -->
    <main class="hero">

        <!-- ========================================================== -->
        <!-- =============== [HTML: VÍDEO DE FUNDO] =================== -->
        <!-- O vídeo inicia sem áudio, repete em loop e não interfere  -->
        <!-- na leitura porque recebe transparência + overlay no CSS.   -->
        <!-- ========================================================== -->
        <video
            id="video-home"
            class="hero-video"
            autoplay
            muted
            loop
            playsinline
            preload="auto"
            aria-hidden="true">
            <source src="{{ url_for('video_home') }}?v=11" type="video/mp4">
        </video>

        <!-- [HTML] OVERLAY: camada escura entre o vídeo e o conteúdo -->
        <div class="hero-video-overlay" aria-hidden="true"></div>

        <!-- Conteúdo textual e cartões ficam acima do vídeo -->
        <div class="hero-conteudo">

            <!-- Indicador Visual -->
            <div class="status-tech">
                <span class="status-ponto"></span>
                {{ status_home }}
            </div>

            <!-- [HTML] TÍTULO E SUBTÍTULO PRINCIPAIS DA HOME -->
            <div class="hero-cabecalho">
                <h1>{{ titulo_home }}</h1>
                <p>{{ subtitulo_home }}</p>
            </div>


            <!-- ====================================================== -->
            <!-- ======================= [JINJA] ====================== -->
            <!-- JINJA = FAZ A LIGAÇÃO ENTRE O PYTHON E O HTML        -->
            <!-- ====================================================== -->

            <!-- [HTML + JINJA] GRADE DE CARDS GERADA PELOS SERVIÇOS DO PYTHON -->
            <div class="grid-servicos" id="servicos">

                {% for item in lista_servicos %}

                <article class="card-servico">

                    <!-- Ícone do Serviço -->
                    <!-- [HTML + JINJA] ÍCONE SVG DO SERVIÇO: definido no Python e renderizado no card -->
                    <div class="card-icone" aria-hidden="true">{{ item.icone|safe }}</div>

                    <!-- Título do Serviço -->
                    <h3>{{ item.titulo }}</h3>

                    <!-- Descrição do Serviço -->
                    <p>{{ item.descricao }}</p>

                    <!-- Ações do Card -->
                    <div class="card-acoes">
                        <a href="{{ item.link }}" class="card-link">Conhecer solução →</a>
                        <a href="/solicitar-orcamento/{{ item.slug }}" class="card-orcamento">Quero solicitar orçamento</a>
                    </div>

                </article>

                {% endfor %}

            </div>

        </div>

    </main>


    <!-- ============================================================ -->
    <!-- [HOME] PROJETOS & GALERIA: 3 itens recentes publicados        -->
    <!-- ============================================================ -->
    <section class="home-secao" id="galeria-home">
        <div class="home-secao-inner">
            <div class="home-secao-cabecalho"><div><h2>Projetos & Galeria</h2><p>Veja registros de trabalhos, instalações, produções e atividades.</p></div><a class="home-secao-link" href="/galeria">Ver galeria completa →</a></div>
            <div class="home-galeria-grid">
                {% for item in galeria_home %}
                <a class="home-midia-card" href="/galeria">
                    {% if item.tipo_midia == 'video' and item.arquivo %}<video class="home-midia-preview" muted preload="metadata"><source src="/midia-galeria/{{ item.arquivo }}"></video>{% elif item.arquivo %}<img class="home-midia-preview" src="/midia-galeria/{{ item.arquivo }}" alt="{{ item.titulo }}">{% else %}<div class="home-midia-preview" style="display:grid;place-items:center;color:var(--cnb-accent);font-weight:900">CNB TECH</div>{% endif %}
                    <div class="home-midia-info"><span class="home-tag">{{ item.categoria or 'Projeto' }}</span><strong>{{ item.titulo }}</strong><p>{{ item.descricao or '' }}</p></div>
                </a>
                {% else %}<div class="home-midia-card"><div class="home-midia-info"><strong>Galeria pronta para receber conteúdo</strong><p>Adicione fotos e vídeos pelo Dashboard.</p></div></div>{% endfor %}
            </div>
        </div>
    </section>

    <!-- ============================================================ -->
    <!-- [HOME] NOTÍCIAS: links internos ou externos gerenciados Admin -->
    <!-- ============================================================ -->
    <section class="home-secao" id="noticias-home">
        <div class="home-secao-inner">
            <div class="home-secao-cabecalho"><div><h2>Notícias & Tecnologia</h2><p>Atualizações, inovação e conteúdos selecionados pela CNB Tech Solution.</p></div><a class="home-secao-link" href="/noticias">Ver todas as notícias →</a></div>
            <div class="home-noticias-grid">
                {% for item in noticias_home %}
                <a class="home-noticia-card" href="{{ item.link_externo if item.link_externo else '/noticias/' ~ item.id }}" {% if item.link_externo %}target="_blank" rel="noopener noreferrer"{% endif %}>
                    {% if item.imagem %}<img class="home-noticia-capa" src="/midia-noticias/{{ item.imagem }}" alt="{{ item.titulo }}">{% else %}<div class="home-noticia-capa" style="display:grid;place-items:center;color:var(--cnb-accent);font-weight:900">CNB TECH NEWS</div>{% endif %}
                    <div class="home-noticia-info"><span class="home-tag">{{ item.categoria or 'Tecnologia' }}</span><strong>{{ item.titulo }}</strong><p>{{ item.resumo or '' }}</p></div>
                </a>
                {% else %}<div class="home-noticia-card"><div class="home-noticia-info"><strong>Área de notícias pronta</strong><p>Cadastre a primeira notícia pelo Dashboard.</p></div></div>{% endfor %}
            </div>
        </div>
    </section>

    <!-- ============================================================ -->
    <!-- [V20 / HOME] CONTATO: DADOS VINDOS DO DASHBOARD              -->
    <!-- ============================================================ -->
    <section class="home-secao home-contato" id="contato">
        <div class="contato-card">
            <div>
                <h2>Vamos conversar sobre o seu projeto?</h2>
                <p>Entre em contato ou solicite um orçamento diretamente pelo site.</p>
            </div>
            <div class="contato-acoes">
                <a class="contato-btn primario" href="/solicitar-orcamento/redes-conectividade">Solicitar orçamento</a>
                <a class="contato-btn" href="mailto:{{ contato_email }}">E-mail</a>
                {% if telefone_tel %}<a class="contato-btn" href="tel:{{ telefone_tel }}">Ligar</a>{% endif %}
                {% if whatsapp_numero %}<a class="contato-btn" href="https://wa.me/{{ whatsapp_numero }}" target="_blank" rel="noopener noreferrer">WhatsApp</a>{% endif %}
            </div>
        </div>
    </section>

    <!-- ============================================================ -->
    <!-- [V20 / HOME] CARDS DAS REDES SOCIAIS                         -->
    <!-- Facebook, YouTube e Instagram recebem os links pelo Admin.   -->
    <!-- ============================================================ -->
    <section class="home-secao home-redes" id="redes-sociais">
        <div class="home-secao-inner">
            <div class="home-secao-cabecalho">
                <div>
                    <h2>Conecte-se com a CNB Tech Solution</h2>
                    <p>Acompanhe projetos, conteúdos, bastidores e novidades nas nossas redes.</p>
                </div>
            </div>
            <div class="redes-grid">
                {% if facebook_url %}<a class="rede-card" href="{{ facebook_url }}" target="_blank" rel="noopener noreferrer">{% else %}<div class="rede-card desativado">{% endif %}
                    <div class="rede-topo"><span class="rede-icone"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 8h3V4h-3c-3 0-5 2-5 5v3H6v4h3v5h4v-5h3l1-4h-4V9c0-.7.3-1 1-1Z"/></svg></span><strong>Facebook</strong></div>
                    <small>{{ 'Acessar página oficial' if facebook_url else 'Adicione o link pelo Dashboard' }}</small>
                {% if facebook_url %}</a>{% else %}</div>{% endif %}

                {% if youtube_url %}<a class="rede-card" href="{{ youtube_url }}" target="_blank" rel="noopener noreferrer">{% else %}<div class="rede-card desativado">{% endif %}
                    <div class="rede-topo"><span class="rede-icone"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="6" width="18" height="12" rx="4"/><path d="m10 9 5 3-5 3Z"/></svg></span><strong>YouTube</strong></div>
                    <small>{{ 'Assistir aos conteúdos' if youtube_url else 'Adicione o link pelo Dashboard' }}</small>
                {% if youtube_url %}</a>{% else %}</div>{% endif %}

                {% if instagram_url %}<a class="rede-card" href="{{ instagram_url }}" target="_blank" rel="noopener noreferrer">{% else %}<div class="rede-card desativado">{% endif %}
                    <div class="rede-topo"><span class="rede-icone"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/></svg></span><strong>Instagram</strong></div>
                    <small>{{ 'Ver novidades e bastidores' if instagram_url else 'Adicione o link pelo Dashboard' }}</small>
                {% if instagram_url %}</a>{% else %}</div>{% endif %}
            </div>
        </div>
    </section>

    <!-- ============================================================ -->
    <!-- [V20 / HTML] RODAPÉ COM CONTATOS DA CNB TECH SOLUTION         -->
    <!-- ============================================================ -->
    <footer class="footer">
        <div class="footer-inner">
            <div class="footer-marca">
                <strong>CNB TECH SOLUTION</strong>
                <span>{{ rodape_home }}</span>
            </div>
            <div class="footer-contatos">
                <a href="mailto:{{ contato_email }}">E-mail: {{ contato_email }}</a>
                {% if contato_telefone %}<a href="tel:{{ telefone_tel }}">Fone: {{ contato_telefone }}</a>{% endif %}
            </div>
        </div>
    </footer>

    <!-- ============================================================ -->
    <!-- ========== [JAVASCRIPT: GARANTIA DO VÍDEO DE FUNDO] ======== -->
    <!-- Tenta iniciar o vídeo novamente após o carregamento da Home. -->
    <!-- Como o vídeo está sem áudio (muted), navegadores modernos     -->
    <!-- normalmente permitem autoplay sem interação do visitante.    -->
    <!-- ============================================================ -->
    <script>
        window.addEventListener('DOMContentLoaded', function () {
            const videoHome = document.getElementById('video-home');
            if (!videoHome) return;

            videoHome.muted = true;
            videoHome.defaultMuted = true;
            videoHome.playsInline = true;

            const tentarReproduzir = () => {
                const tentativa = videoHome.play();
                if (tentativa && typeof tentativa.catch === 'function') {
                    tentativa.catch(() => {
                        // Se o navegador adiar o autoplay, tenta de novo
                        // na primeira interação do usuário com a página.
                        const liberar = () => {
                            videoHome.play().catch(() => {});
                            document.removeEventListener('click', liberar);
                            document.removeEventListener('touchstart', liberar);
                        };
                        document.addEventListener('click', liberar, { once: true });
                        document.addEventListener('touchstart', liberar, { once: true });
                    });
                }
            };

            if (videoHome.readyState >= 2) {
                tentarReproduzir();
            } else {
                videoHome.addEventListener('canplay', tentarReproduzir, { once: true });
            }
        });
    </script>

</body>
</html>
"""

# ----------------------------------------------------------------------
# --------------------- [FIM DA HOME PAGE: VISUAL] ---------------------
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# --------------- [INÍCIO DA PÁGINA: SERVIÇOS TECH] -------------------
# ----------------------------------------------------------------------
LAYOUT_SERVICO_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ titulo }} | CNB TECH SOLUTION</title>

    <!-- ============================================================= -->
    <!-- =========================== [CSS] ============================ -->
    <!-- CSS = VISUAL DA PÁGINA DE CADA SERVIÇO                       -->
    <!-- ============================================================= -->

    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        html {
            scroll-behavior: smooth;
        }

        /* [CSS] FUNDO GERAL DA PÁGINA DE SERVIÇO */
        body {
            background-color: #050c15; /* <<<< [COR BASE: FUNDO DA PÁGINA DE SERVIÇO] */
            background-image:
                radial-gradient(circle at 15% 20%,
                    rgba(14, 165, 233, 0.16),
                    transparent 350px),
                radial-gradient(circle at 85% 50%,
                    rgba(37, 99, 235, 0.12),
                    transparent 400px),
                linear-gradient(135deg, #050c16, #0b1e32, #06101d);
            color: #e2e8f0; /* <<<< [COR PADRÃO DOS TEXTOS DA PÁGINA] */
            min-height: 100vh;
        }

        /* 1. BARRA SUPERIOR */
        .navbar {
            background: rgba(7, 17, 31, 0.96); /* <<<< [FUNDO: NAVBAR DO SERVIÇO] */
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 40px;
            border-bottom: 1px solid rgba(56, 189, 248, 0.25);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.30);
        }

        .logo {
            display: flex;
            align-items: center;
            text-decoration: none;
        }

        .logo-img {
            width: 185px;
            max-height: 86px;
            object-fit: contain;
            display: block;
            border-radius: 10px;
            filter: drop-shadow(0 0 10px rgba(0, 174, 255, 0.20));
        }

        .btn-voltar {
            background: rgba(56, 189, 248, 0.10);
            color: #38bdf8;
            text-decoration: none;
            padding: 9px 16px;
            border: 1px solid rgba(56, 189, 248, 0.30);
            border-radius: 7px;
            font-size: 0.88rem;
            font-weight: 600;
            transition: background 0.25s ease, color 0.25s ease;
        }

        .btn-voltar:hover {
            background: #38bdf8;
            color: #07111f;
        }

        /* 2. CONTEÚDO PRINCIPAL */
        .container {
            max-width: 1050px;
            margin: 0 auto;
            padding: 65px 25px 80px;
        }

        .categoria {
            display: inline-block;
            color: #38bdf8; /* <<<< [COR: ETIQUETA SOLUÇÃO CNB TECH] */
            background: rgba(56, 189, 248, 0.08);
            border: 1px solid rgba(56, 189, 248, 0.20);
            padding: 7px 13px;
            border-radius: 20px;
            font-size: 0.78rem;
            margin-bottom: 18px;
        }

        /* 3. CABEÇALHO DO SERVIÇO */
        .cabecalho-servico {
            max-width: 780px;
            margin-bottom: 45px;
        }

        .cabecalho-servico h1 {
            color: #ffffff; /* <<<< [COR: TÍTULO DO SERVIÇO] */
            font-size: 2.6rem;
            line-height: 1.15;
            margin-bottom: 15px;
        }

        .cabecalho-servico p {
            color: #94a3b8;
            font-size: 1.05rem;
            line-height: 1.7;
        }

        /* 4. CONTEÚDO DO SERVIÇO */
        .conteudo-servico {
            display: grid;
            grid-template-columns: 1.5fr 1fr;
            gap: 25px;
        }

        .painel {
            background: rgba(15, 30, 48, 0.88); /* <<<< [FUNDO: PAINEL DE CONTEÚDO DO SERVIÇO] */
            border: 1px solid rgba(148, 163, 184, 0.13);
            border-radius: 12px;
            padding: 28px;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.20);
        }

        .painel h2 {
            color: #f1f5f9;
            font-size: 1.2rem;
            margin-bottom: 18px;
        }

        /* 5. LISTA DO SERVIÇO */
        .lista-servico {
            list-style: none;
        }

        .lista-servico li {
            position: relative;
            color: #cbd5e1;
            padding: 12px 0 12px 25px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.10);
            font-size: 0.92rem;
            line-height: 1.5;
        }

        .lista-servico li:last-child {
            border-bottom: none;
        }

        .lista-servico li::before {
            content: "✓";
            position: absolute;
            left: 0;
            color: #38bdf8;
            font-weight: bold;
        }

        /* 6. PAINEL DE ORÇAMENTO */
        .orcamento {
            background: linear-gradient(145deg,
                        rgba(14, 42, 66, 0.95),
                        rgba(7, 22, 38, 0.95));
            border: 1px solid rgba(56, 189, 248, 0.25);
        }

        .orcamento p {
            color: #94a3b8;
            font-size: 0.90rem;
            line-height: 1.6;
            margin-bottom: 20px;
        }

        .btn-orcamento {
            display: block;
            width: 100%;
            background: #38bdf8; /* <<<< [FUNDO: BOTÃO SOLICITAR ORÇAMENTO] */
            color: #07111f;      /* <<<< [TEXTO: BOTÃO SOLICITAR ORÇAMENTO] */
            text-align: center;
            text-decoration: none;
            padding: 12px 18px;
            border-radius: 7px;
            font-size: 0.90rem;
            font-weight: 700;
            transition: transform 0.2s ease, background 0.2s ease;
        }

        .btn-orcamento:hover {
            background: #7dd3fc;
            transform: translateY(-2px);
        }

        /* 7. ETAPAS DO ATENDIMENTO */
        .etapas {
            margin-top: 25px;
        }

        .etapas h2 {
            color: #f1f5f9;
            font-size: 1.2rem;
            margin-bottom: 20px;
        }

        .grid-etapas {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
        }

        .etapa {
            background: rgba(15, 30, 48, 0.70);
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 10px;
            padding: 20px;
        }

        .numero-etapa {
            color: #38bdf8;
            font-size: 0.80rem;
            font-weight: bold;
            margin-bottom: 8px;
        }

        .etapa h3 {
            color: #f1f5f9;
            font-size: 0.95rem;
            margin-bottom: 6px;
        }

        .etapa p {
            color: #64748b;
            font-size: 0.80rem;
            line-height: 1.5;
        }

        /* 8. RESPONSIVIDADE */
        @media (max-width: 800px) {
            .conteudo-servico {
                grid-template-columns: 1fr;
            }

            .grid-etapas {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 550px) {
            .navbar {
                padding: 18px 20px;
            }

            .cabecalho-servico h1 {
                font-size: 2rem;
            }

            .grid-etapas {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>


<!-- ================================================================ -->
<!-- ============================ [HTML] ============================= -->
<!-- HTML = ESTRUTURA DA PÁGINA DE CADA SERVIÇO                      -->
<!-- ================================================================ -->

<body>

    <!-- [HTML] BARRA SUPERIOR: logo, menu de navegação e busca -->
    <header class="navbar">
        <a href="/" class="logo" aria-label="CNB Tech Solution - Página inicial">
            <img src="/logo-cnb?v=12" class="logo-img" alt="CNB Tech Solution">
        </a>
        <a href="/" class="btn-voltar">← Voltar aos Serviços</a>
    </header>


    <!-- Conteúdo Principal -->
    <main class="container">

        <div class="categoria">SOLUÇÃO CNB TECH</div>

        <!-- Título e Descrição -->
        <div class="cabecalho-servico">
            <h1>{{ titulo }}</h1>
            <p>{{ descricao }}</p>
        </div>


        <!-- ========================================================== -->
        <!-- ========================= [JINJA] ======================== -->
        <!-- JINJA RECEBE AS INFORMAÇÕES DO PYTHON                    -->
        <!-- ========================================================== -->

        <div class="conteudo-servico">

            <!-- Informações do Serviço -->
            <section class="painel">

                <h2>O que podemos oferecer</h2>

                <ul class="lista-servico">

                    {% for item in itens %}

                    <li>{{ item }}</li>

                    {% endfor %}

                </ul>

            </section>


            <!-- Solicitação de Orçamento -->
            <aside class="painel orcamento" id="orcamento">

                <h2>Solicite um orçamento</h2>

                <p>Conte para nossa equipe o que sua empresa ou instituição precisa. A CNB Tech Solution poderá avaliar o projeto e preparar uma solução adequada à sua necessidade.</p>

                <a href="/solicitar-orcamento/{{ slug }}" class="btn-orcamento">
                    Quero solicitar orçamento
                </a>

            </aside>

        </div>


        <!-- Etapas do Atendimento -->
        <section class="etapas">

            <h2>Etapas do atendimento</h2>

            <div class="grid-etapas">

                <div class="etapa">
                    <div class="numero-etapa">ETAPA 01</div>
                    <h3>Solicitação</h3>
                    <p>O cliente apresenta sua necessidade ou projeto.</p>
                </div>

                <div class="etapa">
                    <div class="numero-etapa">ETAPA 02</div>
                    <h3>Análise Técnica</h3>
                    <p>Nossa equipe analisa os requisitos e a estrutura necessária.</p>
                </div>

                <div class="etapa">
                    <div class="numero-etapa">ETAPA 03</div>
                    <h3>Proposta</h3>
                    <p>Preparamos a solução e o orçamento para o projeto.</p>
                </div>

                <div class="etapa">
                    <div class="numero-etapa">ETAPA 04</div>
                    <h3>Execução</h3>
                    <p>Após aprovação, iniciamos a implantação da solução.</p>
                </div>

            </div>

        </section>

    </main>

</body>
</html>
"""

# ----------------------------------------------------------------------
# ----------------- [FIM DA PÁGINA: SERVIÇOS TECH] ---------------------
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# -------------- [PYTHON: ROTA DA NOVA LOGO CNB TECH] ------------------
# ----------------------------------------------------------------------
@app.route("/logo-cnb")
def logo_cnb():
    # Primeiro tenta a logo enviada pelo painel administrativo.
    nome_configurado = obter_config_site("logo_arquivo", "").strip()
    if nome_configurado:
        arquivo = PASTA_MIDIA_SITE / nome_configurado
        if arquivo.exists() and arquivo.is_file():
            resposta = send_from_directory(PASTA_MIDIA_SITE, nome_configurado, conditional=True, max_age=0)
            resposta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return resposta

    # Fallback: logo que acompanha o projeto.
    if not LOGO_CNB_ARQUIVO.exists():
        abort(404, description="Logo CNB Tech Solution não encontrada.")
    resposta = send_from_directory(BASE_DIR, LOGO_CNB_NOME, conditional=True, max_age=0)
    resposta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resposta


# ----------------------------------------------------------------------
# ------------- [PYTHON: ROTA DO VÍDEO DA PÁGINA INICIAL] --------------
# ----------------------------------------------------------------------
@app.route("/video-home")
def video_home():
    # Primeiro tenta o vídeo enviado pelo painel administrativo.
    nome_configurado = obter_config_site("video_arquivo", "").strip()
    if nome_configurado:
        arquivo = PASTA_MIDIA_SITE / nome_configurado
        if arquivo.exists() and arquivo.is_file():
            resposta = send_from_directory(PASTA_MIDIA_SITE, nome_configurado, mimetype="video/mp4", conditional=True, max_age=0)
            resposta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return resposta

    # Fallback: vídeo original ao lado do Python.
    if not VIDEO_HOME_ARQUIVO.exists():
        abort(404, description="Vídeo da Home não encontrado na pasta do projeto.")
    resposta = send_from_directory(BASE_DIR, VIDEO_HOME_NOME, mimetype="video/mp4", conditional=True, max_age=0)
    resposta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resposta


# ----------------------------------------------------------------------
# ------------------ [PYTHON: ROTA 1 - HOME PAGE] ----------------------
# ----------------------------------------------------------------------
@app.route("/")
def home():
    visual = configuracao_visual_atual()
    animacoes = {
        "desligada": ("0s", "none", "0 12px 30px rgba(0,0,0,.18)"),
        "leve": ("0.18s", "translateY(-2px)", "0 16px 34px rgba(0,0,0,.24)"),
        "media": ("0.28s", "translateY(-6px)", "0 20px 40px rgba(0,0,0,.30)"),
    }
    duracao, transformacao, sombra = animacoes[visual["animacao_cards"]]
    overlay = visual["overlay_video"] / 100

    # [PYTHON + SQLITE] Conteúdo dinâmico exibido nos cards da Home.
    with conectar_banco() as conexao:
        galeria_home = conexao.execute(
            "SELECT * FROM galeria_publica WHERE publicado=1 ORDER BY destaque DESC, id DESC LIMIT 3"
        ).fetchall()
        noticias_home = conexao.execute(
            "SELECT * FROM noticias WHERE publicado=1 ORDER BY destaque DESC, id DESC LIMIT 3"
        ).fetchall()

    dados = {
        "nome_empresa": "CNB TECH SOLUTION",
        "status_home": obter_config_site("status_home", "Ecossistema de soluções digitais"),
        "titulo_home": obter_config_site("titulo_home", "Tecnologia que conecta infraestrutura e inovação."),
        "subtitulo_home": obter_config_site("subtitulo_home", "Soluções integradas para conectividade, infraestrutura de TI, desenvolvimento de sistemas, educação digital e produção audiovisual."),
        "rodape_home": obter_config_site("rodape_home", "Tecnologia, infraestrutura e soluções digitais."),

        # --------------------------------------------------------------
        # [V20 / PYTHON] CONTATOS E REDES SOCIAIS DA HOME / RODAPÉ
        # --------------------------------------------------------------
        "contato_email": obter_config_site("contato_email", CONTATOS_REDES_PADRAO["contato_email"]),
        "contato_telefone": obter_config_site("contato_telefone", CONTATOS_REDES_PADRAO["contato_telefone"]),
        "facebook_url": normalizar_url_externa(obter_config_site("facebook_url", "")),
        "youtube_url": normalizar_url_externa(obter_config_site("youtube_url", "")),
        "instagram_url": normalizar_url_externa(obter_config_site("instagram_url", "")),
        **visual,
        "overlay_alpha_top": f"{max(0.0, overlay - 0.12):.2f}",
        "overlay_alpha_bottom": f"{min(0.95, overlay + 0.10):.2f}",
        "animacao_duracao": duracao,
        "animacao_transform": transformacao,
        "animacao_sombra": sombra,
        "galeria_home": galeria_home,       # <<<< [CARDS DA GALERIA NA HOME]
        "noticias_home": noticias_home,     # <<<< [CARDS DE NOTÍCIAS NA HOME]

        "lista_servicos": [
            {
                # [SVG] Redes e Conectividade: nós interligados representam a rede.
                "icone": '<svg viewBox="0 0 24 24" role="img"><circle cx="12" cy="5" r="2.2"/><circle cx="5" cy="18" r="2.2"/><circle cx="19" cy="18" r="2.2"/><path d="M10.7 6.8 6.4 16M13.3 6.8l4.3 9.2M7.3 18h9.4"/><circle cx="12" cy="12" r="1.8"/></svg>',
                "titulo": "Redes e Conectividade",
                "descricao": "Projetos e soluções de redes, conectividade e comunicação entre equipamentos e sistemas.",
                "link": "/servico/redes-conectividade",
                "slug": "redes-conectividade"
            },

            {
                # [SVG] Infraestrutura de TI: rack/servidores representam a infraestrutura.
                "icone": '<svg viewBox="0 0 24 24" role="img"><rect x="4" y="3" width="16" height="6" rx="2"/><rect x="4" y="15" width="16" height="6" rx="2"/><path d="M7.5 6h.01M7.5 18h.01M11 6h6M11 18h6M12 9v6"/></svg>',
                "titulo": "Infraestrutura de TI",
                "descricao": "Implantação e organização de infraestrutura tecnológica para empresas e ambientes corporativos.",
                "link": "/servico/infraestrutura-ti",
                "slug": "infraestrutura-ti"
            },

            {
                # [SVG] Desenvolvimento: símbolos de código representam programação e sistemas.
                "icone": '<svg viewBox="0 0 24 24" role="img"><path d="m8.5 7-5 5 5 5M15.5 7l5 5-5 5M14 4l-4 16"/></svg>',
                "titulo": "Desenvolvimento de Sistemas",
                "descricao": "Desenvolvimento de sistemas web, plataformas digitais e soluções personalizadas para empresas.",
                "link": "/servico/desenvolvimento-sistemas",
                "slug": "desenvolvimento-sistemas"
            },

            {
                # [SVG] Educação: capelo representa ensino, treinamento e EAD.
                "icone": '<svg viewBox="0 0 24 24" role="img"><path d="m3 9 9-5 9 5-9 5-9-5Z"/><path d="M7 11.3V16c0 1.5 2.2 3 5 3s5-1.5 5-3v-4.7M21 9v6"/></svg>',
                "titulo": "Soluções para Educação",
                "descricao": "Plataformas de ensino, ambientes EAD e ferramentas digitais para instituições educacionais.",
                "link": "/servico/educacao",
                "slug": "educacao"
            },

            {
                # [SVG] Audiovisual: câmera e play representam vídeo, live e produção.
                "icone": '<svg viewBox="0 0 24 24" role="img"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3zM8 9.5l4 2.5-4 2.5z"/></svg>',
                "titulo": "Soluções Audiovisuais",
                "descricao": "Estrutura para produção audiovisual, transmissões ao vivo e integração de áudio e vídeo.",
                "link": "/servico/audiovisual",
                "slug": "audiovisual"
            },

            {
                # [SVG] Informática e Suporte: monitor + engrenagem representam suporte técnico.
                "icone": '<svg viewBox="0 0 24 24" role="img"><rect x="3" y="4" width="14" height="10" rx="2"/><path d="M7 20h6M10 14v6"/><circle cx="18" cy="17" r="3"/><path d="M18 12.5v1.5M18 20v1.5M13.5 17H15M21 17h1.5M14.8 13.8l1.1 1.1M20.1 19.1l1.1 1.1M21.2 13.8l-1.1 1.1M15.9 19.1l-1.1 1.1"/></svg>',
                "titulo": "Serviços de Informática & Suporte",
                "descricao": "Manutenção e acompanhamento técnico de equipamentos, serviços de rede e sistemas.",
                "link": "/servico/suporte",
                "slug": "suporte"
            }
        ]
    }

    # [V20] Gera os href de telefone e WhatsApp a partir do número editável.
    dados["telefone_tel"] = telefone_para_link(dados["contato_telefone"])
    dados["whatsapp_numero"] = telefone_para_whatsapp(dados["contato_telefone"])

    return render_template_string(LAYOUT_HTML, **dados)


# ----------------------------------------------------------------------
# --------------- [PYTHON: DADOS DOS SERVIÇOS TECH] --------------------
# ----------------------------------------------------------------------
SERVICOS = {
    "redes-conectividade": {
        "titulo": "Redes e Conectividade",
        "descricao": "Projetos e soluções para conexão, comunicação e integração segura entre equipamentos, sistemas e ambientes corporativos.",
        "itens": [
            "Planejamento e organização de redes",
            "Infraestrutura de conectividade",
            "Configuração de equipamentos de rede",
            "Integração entre equipamentos e sistemas",
            "Análise e melhoria da conectividade",
            "Suporte técnico para ambientes de rede"
        ]
    },

    "infraestrutura-ti": {
        "titulo": "Infraestrutura de TI",
        "descricao": "Implantação e organização de infraestrutura tecnológica para empresas e ambientes corporativos.",
        "itens": [
            "Planejamento de infraestrutura tecnológica",
            "Organização de equipamentos e ambientes de TI",
            "Estrutura para servidores e armazenamento",
            "Integração de equipamentos",
            "Organização de redes e conectividade",
            "Suporte e acompanhamento técnico"
        ]
    },

    "desenvolvimento-sistemas": {
        "titulo": "Desenvolvimento de Sistemas",
        "descricao": "Desenvolvimento de sistemas web, plataformas digitais e soluções personalizadas para empresas.",
        "itens": [
            "Desenvolvimento de sistemas web",
            "Plataformas digitais personalizadas",
            "Sistemas para gerenciamento empresarial",
            "Portais e ambientes de acesso",
            "Integração entre sistemas",
            "Desenvolvimento de novas funcionalidades"
        ]
    },

    "educacao": {
        "titulo": "Soluções para Educação",
        "descricao": "Plataformas de ensino, ambientes EAD e ferramentas digitais para instituições educacionais.",
        "itens": [
            "Plataformas de ensino a distância",
            "Ambientes para aulas ao vivo",
            "Disponibilização de aulas gravadas",
            "Áreas de acesso para alunos e instrutores",
            "Gerenciamento de turmas",
            "Soluções digitais para instituições de ensino"
        ]
    },

    "audiovisual": {
        "titulo": "Soluções Audiovisuais",
        "descricao": "Estrutura para produção audiovisual, transmissões ao vivo e integração profissional de áudio e vídeo.",
        "itens": [
            "Produção audiovisual",
            "Transmissões ao vivo",
            "Captação com múltiplas câmeras",
            "Integração de áudio e vídeo",
            "Produção de conteúdo digital",
            "Estrutura audiovisual para eventos e empresas"
        ]
    },

    "suporte": {
        "titulo": "Serviços de Informática & Suporte",
        "descricao": "Manutenção e acompanhamento técnico de equipamentos, serviços de rede e sistemas.",
        "itens": [
            "Suporte técnico",
            "Manutenção de equipamentos",
            "Configuração de computadores",
            "Acompanhamento de redes",
            "Configuração de sistemas",
            "Diagnóstico de problemas tecnológicos"
        ]
    }
}


# ----------------------------------------------------------------------
# ---------------- [PYTHON: ROTAS DOS SERVIÇOS] ------------------------
# ----------------------------------------------------------------------
@app.route("/servico/<slug>")
def pagina_servico(slug):
    servico = SERVICOS.get(slug)

    # Se o serviço solicitado não existir, retorna erro 404
    if servico is None:
        return "Serviço não encontrado.", 404

    return render_template_string(
        LAYOUT_SERVICO_HTML,
        titulo=servico["titulo"],
        descricao=servico["descricao"],
        itens=servico["itens"],
        slug=slug
    )


# ----------------------------------------------------------------------
# ---------------- [PYTHON: ROTA 2 - PÁGINA EMPRESA] -------------------
# ----------------------------------------------------------------------
@app.route("/empresa")
def empresa():
    # [PYTHON] Lê a MESMA configuração visual usada pela Home.
    # Assim, a página Empresa acompanha automaticamente o tema escolhido
    # no Editar Site 2.0 e também qualquer ajuste manual de cores.
    visual = configuracao_visual_atual()

    # ------------------------------------------------------------------
    # [PYTHON + SQLITE] EQUIPE / QUEM SOMOS
    # Busca somente integrantes PUBLICADOS e respeita a ordem definida
    # no Dashboard. Em caso de empate, o cadastro mais antigo vem primeiro.
    # ------------------------------------------------------------------
    with conectar_banco() as conexao:
        equipe = conexao.execute(
            "SELECT * FROM equipe_empresa WHERE publicado=1 ORDER BY ordem ASC, id ASC"
        ).fetchall()

    dados = {
        "nome_empresa": "CNB TECH SOLUTION",
        "equipe": equipe,  # <<<< [CARDS DOS INTEGRANTES EXIBIDOS NA PÁGINA EMPRESA]
        **visual  # <<<< [CORES / TEMA / TAMANHOS ENVIADOS PARA O HTML DA EMPRESA]
    }

    return render_template_string(LAYOUT_EMPRESA_HTML, **dados)



# ----------------------------------------------------------------------
# -------- [PYTHON: PÁGINAS DE APLICAÇÃO DA TECNOLOGIA] ----------------
# ----------------------------------------------------------------------
AREAS_SITE = {
    "industria": {"icone": "IND", "titulo": "industria_titulo", "subtitulo": "industria_subtitulo", "texto": "industria_texto", "aplicacoes": "industria_aplicacoes"},
    "educacao": {"icone": "EDU", "titulo": "educacao_titulo", "subtitulo": "educacao_subtitulo", "texto": "educacao_texto", "aplicacoes": "educacao_aplicacoes"},
    "treinamentos": {"icone": "TR", "titulo": "treinamentos_titulo", "subtitulo": "treinamentos_subtitulo", "texto": "treinamentos_texto", "aplicacoes": "treinamentos_aplicacoes"},
    "laboratorio": {"icone": "LAB", "titulo": "laboratorio_titulo", "subtitulo": "laboratorio_subtitulo", "texto": "laboratorio_texto", "aplicacoes": "laboratorio_aplicacoes"},
}


def renderizar_area(slug):
    cfg = AREAS_SITE.get(slug)
    if not cfg:
        abort(404)
    visual = configuracao_visual_atual()
    aplicacoes = [linha.strip() for linha in obter_config_site(cfg["aplicacoes"], "").splitlines() if linha.strip()]
    return render_template_string(
        LAYOUT_AREA_HTML,
        **visual,
        icone=cfg["icone"],
        titulo=obter_config_site(cfg["titulo"], slug.title()),
        subtitulo=obter_config_site(cfg["subtitulo"], ""),
        texto=obter_config_site(cfg["texto"], ""),
        aplicacoes=aplicacoes,
    )


@app.route('/industria')
def pagina_industria():
    return renderizar_area('industria')

@app.route('/educacao')
def pagina_educacao():
    return renderizar_area('educacao')

@app.route('/treinamentos')
def pagina_treinamentos():
    return renderizar_area('treinamentos')

@app.route('/laboratorio')
def pagina_laboratorio():
    return renderizar_area('laboratorio')


# ----------------------------------------------------------------------
# ---------------- [PYTHON: MÍDIAS DA GALERIA / NOTÍCIAS] --------------
# ----------------------------------------------------------------------
@app.route('/midia-galeria/<path:nome>')
def midia_galeria(nome):
    return send_from_directory(PASTA_GALERIA, Path(nome).name)

@app.route('/midia-noticias/<path:nome>')
def midia_noticias(nome):
    return send_from_directory(PASTA_NOTICIAS, Path(nome).name)

# ----------------------------------------------------------------------
# ------------------- [PYTHON: FOTOS DA EQUIPE] ------------------------
# ----------------------------------------------------------------------
# Entrega ao navegador somente o nome final do arquivo, evitando que
# caminhos externos sejam usados para acessar outros arquivos do sistema.
@app.route('/midia-equipe/<path:nome>')
def midia_equipe(nome):
    return send_from_directory(PASTA_EQUIPE, Path(nome).name)


# ----------------------------------------------------------------------
# ------------------- [PYTHON: PROJETOS & GALERIA] ---------------------
# ----------------------------------------------------------------------
@app.route('/galeria')
def galeria_publica():
    with conectar_banco() as conexao:
        itens = conexao.execute("SELECT * FROM galeria_publica WHERE publicado=1 ORDER BY destaque DESC, id DESC").fetchall()
    return render_template_string(LAYOUT_GALERIA_HTML, itens=itens, **configuracao_visual_atual())


# ----------------------------------------------------------------------
# ---------------------- [PYTHON: NOTÍCIAS] -----------------------------
# ----------------------------------------------------------------------
@app.route('/noticias')
def noticias_publicas():
    with conectar_banco() as conexao:
        itens = conexao.execute("SELECT * FROM noticias WHERE publicado=1 ORDER BY destaque DESC, id DESC").fetchall()
    return render_template_string(LAYOUT_NOTICIAS_HTML, itens=itens, **configuracao_visual_atual())

@app.route('/noticias/<int:noticia_id>')
def noticia_detalhe(noticia_id):
    with conectar_banco() as conexao:
        noticia = conexao.execute("SELECT * FROM noticias WHERE id=? AND publicado=1", (noticia_id,)).fetchone()
    if noticia is None:
        abort(404)
    # Se houver link externo, o acesso direto também pode seguir para a fonte.
    if noticia['link_externo']:
        return redirect(noticia['link_externo'])
    return render_template_string(LAYOUT_NOTICIA_DETALHE_HTML, noticia=noticia, **configuracao_visual_atual())


# ----------------------------------------------------------------------
# ------------- [INÍCIO: PAINEL ADMINISTRATIVO CNB TECH] ---------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# -------- [CSS DINÂMICO DO DASHBOARD / PAINEL ADMINISTRATIVO] ---------
# ----------------------------------------------------------------------
# Esta função pega as cores salvas no banco e monta o CSS do painel.
# Se "Sincronizar com o site" estiver ligado, o Dashboard usa a mesma
# paleta da Home. Se estiver desligado, usa as cores manuais do Admin.
def admin_css_atual():
    visual_admin = configuracao_admin_atual()["efetiva"]
    fundo = visual_admin["admin_cor_fundo"]
    topo = visual_admin["admin_cor_topo"]
    superficie = visual_admin["admin_cor_superficie"]
    borda = visual_admin["admin_cor_borda"]
    titulo = visual_admin["admin_cor_titulo"]
    texto = visual_admin["admin_cor_texto"]
    destaque = visual_admin["admin_cor_destaque"]

    return f"""
<style>
/* ================================================================ */
/* [CSS] VARIÁVEIS DE COR DO PAINEL ADMIN                          */
/* ================================================================ */
:root{{--admin-bg:{fundo};          /* <<<< [FUNDO GERAL DO DASHBOARD] */
       --admin-topo:{topo};        /* <<<< [BARRA SUPERIOR DO ADMIN] */
       --admin-surface:{superficie};/* <<<< [CARDS / FORMULÁRIOS / PAINÉIS] */
       --admin-border:{borda};     /* <<<< [BORDAS DO PAINEL] */
       --admin-title:{titulo};     /* <<<< [TÍTULOS E NÚMEROS] */
       --admin-text:{texto};       /* <<<< [TEXTOS SECUNDÁRIOS] */
       --admin-accent:{destaque}}} /* <<<< [BOTÕES, LINKS E DESTAQUES] */
*{{box-sizing:border-box}}
body{{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;background:var(--admin-bg);color:var(--admin-title);min-height:100vh}} /* <<<< [TELA INTEIRA DO ADMIN] */
a{{color:var(--admin-accent)}}
/* [ADMIN] BARRA SUPERIOR: logo, nome do painel, usuário e sair */
.topo{{background:linear-gradient(120deg,var(--admin-topo),var(--admin-surface));color:var(--admin-title);padding:14px 5%;display:flex;justify-content:space-between;align-items:center;gap:18px;border-bottom:1px solid var(--admin-border);box-shadow:0 8px 24px rgba(0,0,0,.18)}}
.admin-brand{{display:flex;align-items:center;gap:14px;min-width:0}}
/* [ADMIN] MESMA LOGO DA HOME, CARREGADA PELA ROTA /logo-cnb */
.admin-logo{{width:190px;max-width:42vw;max-height:70px;object-fit:contain;display:block;filter:drop-shadow(0 0 12px color-mix(in srgb,var(--admin-accent) 28%,transparent))}}
.admin-brand-text{{font-weight:800;letter-spacing:.04em;white-space:nowrap}}
.topo a{{color:var(--admin-accent);text-decoration:none;font-weight:700}}
.wrap{{max-width:1180px;margin:30px auto;padding:0 20px}}
/* [ADMIN] MENU PRINCIPAL: Dashboard, Editar Site, Empresas, etc. */
.menu{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}}
.menu a{{background:var(--admin-surface);border:1px solid var(--admin-border);padding:10px 14px;border-radius:8px;text-decoration:none;color:var(--admin-title);font-weight:600;transition:.2s ease}}
.menu a:hover{{border-color:var(--admin-accent);color:var(--admin-accent);transform:translateY(-1px)}}
/* [ADMIN] GRADE DOS INDICADORES NUMÉRICOS DO DASHBOARD */
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
/* [ADMIN] SUPERFÍCIES: cards, formulários, blocos e editor visual */
.card,.form-card,.bloco,.painel-editor{{background:var(--admin-surface)!important;border:1px solid var(--admin-border)!important;color:var(--admin-title)!important;box-shadow:0 8px 24px rgba(0,0,0,.16)!important}}
.card{{border-radius:12px;padding:20px}}
.numero{{font-size:2rem;font-weight:800;color:var(--admin-title)}}
.muted,.nota-admin,.help,.arquivo-atual{{color:var(--admin-text)!important}}
/* [ADMIN] TABELAS: orçamentos, empresas, projetos e administradores */
.tabela{{width:100%;border-collapse:collapse;background:var(--admin-surface);border-radius:10px;overflow:hidden;color:var(--admin-title)}}
.tabela th,.tabela td{{padding:12px;border-bottom:1px solid var(--admin-border);text-align:left;font-size:.9rem}}
.tabela th{{background:var(--admin-topo);color:var(--admin-title)}}
.tabela tr:hover td{{background:rgba(255,255,255,.025)}}
/* [ADMIN] BOTÃO PRINCIPAL: usa a cor de destaque da paleta */
.btn{{display:inline-block;background:var(--admin-accent);color:var(--admin-bg);padding:9px 13px;border:1px solid var(--admin-accent);border-radius:7px;text-decoration:none;font-weight:800;cursor:pointer}}
.btn:hover{{filter:brightness(1.08)}}
.danger{{background:#ef4444;color:white;border-color:#ef4444}}
/* [ADMIN] CAMPOS DE FORMULÁRIO E SELETORES */
.campo,.select-campo{{width:100%;padding:11px;border:1px solid var(--admin-border);border-radius:7px;margin:6px 0 12px;background:var(--admin-bg);color:var(--admin-title);outline:none}}
.campo:focus,.select-campo:focus{{border-color:var(--admin-accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--admin-accent) 22%,transparent)}}
.form-card{{max-width:650px;padding:25px;border-radius:12px}}
.alerta{{background:var(--admin-surface);border:1px solid var(--admin-accent);color:var(--admin-title);padding:12px;border-radius:8px;margin-bottom:15px}}
.separador{{border:0;border-top:1px solid var(--admin-border);margin:14px 0}}
.form-anexo{{margin-top:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.btn-anexo{{background:var(--admin-surface);color:var(--admin-accent);border:1px solid var(--admin-accent)}}
.lista-anexos{{margin:8px 0}}
.anexo-item{{margin:6px 0;padding:7px;background:var(--admin-bg);border:1px solid var(--admin-border);border-radius:6px}}
.anexo-item a{{color:var(--admin-accent);text-decoration:none;font-weight:600}}
.btn-mini{{padding:4px 7px;font-size:.72rem;margin-left:5px}}
.btn-sec{{background:var(--admin-topo);color:var(--admin-title);border-color:var(--admin-border)}}
.detalhe-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}
.bloco{{border-radius:12px;padding:20px;margin:16px 0}}
.descricao{{white-space:pre-wrap;background:var(--admin-bg);border:1px solid var(--admin-border);padding:14px;border-radius:8px;line-height:1.6;color:var(--admin-text)}}
.acoes{{display:flex;gap:8px;flex-wrap:wrap}}
.badge{{display:inline-block;padding:5px 9px;border-radius:999px;background:var(--admin-topo);border:1px solid var(--admin-border);color:var(--admin-accent);font-size:.78rem;font-weight:700}}
.preview-midia{{background:var(--admin-bg);border:1px solid var(--admin-border);border-radius:12px;padding:18px;margin:12px 0 20px;min-height:120px;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.preview-midia img{{max-width:100%;max-height:180px;object-fit:contain}}
.preview-midia video{{width:100%;max-height:320px;border-radius:8px}}
.editor-grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.btn-salvar{{margin-top:8px}}
/* [EDITAR SITE 2.0] DUAS COLUNAS: controles + prévia */
.editor-2-grid{{display:grid;grid-template-columns:minmax(0,1fr) minmax(360px,.82fr);gap:20px;align-items:start}}
.painel-editor{{border-radius:14px;padding:22px}}
.painel-editor h2{{margin-top:0}}
/* [EDITAR SITE 2.0] BOTÕES DOS TEMAS CNB TECH / DARK / CORPORATE */
.tema-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0 18px}}
.tema-btn{{border:1px solid var(--admin-border);background:var(--admin-bg);color:var(--admin-title);border-radius:10px;padding:12px;cursor:pointer;text-align:left;font-weight:700}}
.tema-btn small{{display:block;color:var(--admin-text);font-weight:500;margin-top:4px}}
.tema-btn.ativo{{border-color:var(--admin-accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--admin-accent) 18%,transparent)}}
.controle-linha{{display:grid;grid-template-columns:1fr 120px;gap:12px;align-items:center;margin:10px 0}}
.controle-linha input[type=color]{{width:100%;height:42px;border:1px solid var(--admin-border);border-radius:8px;padding:3px;background:var(--admin-bg)}}
.controle-range{{display:grid;grid-template-columns:1fr 64px;gap:10px;align-items:center}}
.controle-range output{{background:var(--admin-bg);border:1px solid var(--admin-border);color:var(--admin-title);border-radius:7px;padding:7px;text-align:center;font-weight:700;font-size:.82rem}}
/* [EDITAR SITE 2.0] MINIATURA / PRÉVIA DA HOME EM TEMPO REAL */
.preview-site{{position:sticky;top:18px;background:#020617;border-radius:14px;overflow:hidden;border:1px solid var(--admin-border);box-shadow:0 18px 40px rgba(0,0,0,.28)}}
.preview-top{{min-height:78px;padding:12px 18px;display:flex;align-items:center;border-bottom:1px solid rgba(148,163,184,.16)}}
.preview-logo{{object-fit:contain;max-height:72px;display:block}}
.preview-hero{{position:relative;min-height:390px;padding:34px 22px;background:linear-gradient(135deg,#06101d,#0b1b2b);overflow:hidden}}
.preview-hero:before{{content:'';position:absolute;inset:0;background:radial-gradient(circle at 70% 20%,rgba(56,189,248,.18),transparent 45%)}}
.preview-conteudo{{position:relative;z-index:1}}
.preview-status{{width:max-content;margin:0 auto 12px;border:1px solid rgba(148,163,184,.25);border-radius:999px;padding:5px 10px;color:#94a3b8;font-size:.7rem}}
.preview-titulo{{text-align:center;font-size:1.6rem;line-height:1.15;margin:0 auto 10px;max-width:520px}}
.preview-sub{{text-align:center;font-size:.78rem;line-height:1.55;max-width:500px;margin:0 auto 24px}}
.preview-cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}}
.preview-card{{min-height:118px;padding:13px;border:1px solid;border-radius:12px;transition:.25s ease}}
.preview-card strong{{display:block;font-size:.78rem;margin:8px 0 5px}}
.preview-card p{{font-size:.65rem;line-height:1.4;margin:0}}
.preview-icone{{font-size:.8rem}}
.grupo-titulo{{font-size:.76rem;text-transform:uppercase;letter-spacing:.08em;color:var(--admin-text);font-weight:800;margin:22px 0 8px}}
.acoes-editor{{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}}
.btn-outline{{background:var(--admin-bg);color:var(--admin-title);border:1px solid var(--admin-border)}}
/* [EDITAR SITE 2.0] CONTROLE DE SINCRONIZAÇÃO SITE ↔ DASHBOARD */
.switch-admin{{display:flex;align-items:center;gap:10px;padding:12px;border:1px solid var(--admin-border);background:var(--admin-bg);border-radius:10px;margin:10px 0}}
.switch-admin input{{width:18px;height:18px;accent-color:var(--admin-accent)}}
.admin-manual-box{{border:1px dashed var(--admin-border);border-radius:10px;padding:12px;margin-top:10px;transition:.2s ease}}
.admin-manual-box.sincronizado{{opacity:.55}}
@media(max-width:980px){{.editor-2-grid{{grid-template-columns:1fr}}.preview-site{{position:relative;top:auto}}}}
@media(max-width:800px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:760px){{.editor-grid{{grid-template-columns:1fr}}}}
@media(max-width:700px){{.detalhe-grid{{grid-template-columns:1fr}}}}
@media(max-width:620px){{.tema-grid{{grid-template-columns:1fr}}.preview-cards{{grid-template-columns:1fr}}.controle-linha{{grid-template-columns:1fr}}}}
@media(max-width:500px){{.grid{{grid-template-columns:1fr}}.topo{{align-items:flex-start;flex-direction:column}}.admin-logo{{width:165px;max-width:70vw}}.admin-brand-text{{font-size:.82rem}}}}
</style>
"""


def admin_shell(titulo, conteudo):
    # [PYTHON + JINJA] Estrutura-base usada por todas as páginas do painel Admin.
    # A variável {{css|safe}} injeta o CSS dinâmico criado em admin_css_atual().
    # A variável {{conteudo|safe}} recebe o conteúdo específico de cada tela.
    return render_template_string("""
<!doctype html>
<html lang='pt-BR'>
<head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>{{titulo}} | CNB TECH</title>
    {{css|safe}}
</head>
<body>
    <!-- [ADMIN] TOPO: mesma logo do site + usuário logado + botão Sair -->
    <header class='topo'>
        <div class='admin-brand'>
            <a href='/admin' aria-label='Dashboard CNB Tech Solution'>
                <img class='admin-logo' src='/logo-cnb' alt='CNB Tech Solution'>
            </a>
            <span class='admin-brand-text'>PAINEL ADMIN</span>
        </div>
        <div>{{email}} &nbsp; <a href='/admin/logout'>Sair</a></div>
    </header>

    <main class='wrap'>
        <!-- [ADMIN] MENU DE NAVEGAÇÃO PRINCIPAL -->
        <nav class='menu'>
            <a href='/admin'>Dashboard</a>
            <a href='/admin/editar-site'>Editar Site 2.0</a>
            <a href='/admin/contatos-redes'>Contatos & Redes</a>
            <a href='/admin/empresas'>Empresas</a>
            <a href='/admin/orcamentos'>Orçamentos</a>
            <a href='/admin/projetos'>Projetos</a>
            <a href='/admin/areas'>Conteúdo das Áreas</a>
            <a href='/admin/equipe'>Equipe / Quem Somos</a>
            <a href='/admin/galeria'>Galeria</a>
            <a href='/admin/noticias'>Notícias</a>
            <a href='/admin/administradores'>Administradores</a>
            <a href='/' target='_blank' rel='noopener noreferrer'>Ver site</a>
        </nav>

        <!-- [JINJA] MENSAGENS DE SUCESSO/ERRO GERADAS PELO FLASK -->
        {% with mensagens = get_flashed_messages() %}
            {% if mensagens %}
                {% for m in mensagens %}
                    <div class='alerta'>{{m}}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- [JINJA] CONTEÚDO DA TELA ATUAL DO PAINEL -->
        {{conteudo|safe}}
    </main>
</body>
</html>
""", titulo=titulo, css=admin_css_atual(), conteudo=conteudo, email=session.get("admin_email",""))

# ----------------------------------------------------------------------
# ----------- [PYTHON: SOLICITAÇÃO DE ORÇAMENTO + WHATSAPP] ------------
# ----------------------------------------------------------------------
WHATSAPP_CNB = "5591992316147"

# ----------------------------------------------------------------------
# ----------- [E-MAIL COMERCIAL: CNB TECH SOLUTION / GMAIL] ------------
# ----------------------------------------------------------------------
EMAIL_COMERCIAL_CNB = "cnbtvpara2019@gmail.com"
SMTP_SERVIDOR = "smtp.gmail.com"
SMTP_PORTA = 587

# Por segurança, a senha NÃO fica gravada no código.
# No Windows, crie a variável CNB_GMAIL_APP_PASSWORD com uma Senha de App do Google.
# Opcionalmente, CNB_EMAIL_REMETENTE pode definir outro remetente autorizado.

def enviar_email_orcamento(numero_pedido, tipo_cliente, nome, empresa, documento, email, telefone, cidade, servico, mensagem, caminho_anexo=None, nome_anexo=None):
    senha_app = os.environ.get("CNB_GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    remetente = os.environ.get("CNB_EMAIL_REMETENTE", EMAIL_COMERCIAL_CNB).strip()

    if not senha_app:
        print("[!] E-mail não enviado: configure CNB_GMAIL_APP_PASSWORD com a Senha de App do Gmail.")
        return False

    msg = EmailMessage()
    msg["Subject"] = f"Novo orçamento CNB Tech Solution #{numero_pedido} - {servico}"
    msg["From"] = remetente
    msg["To"] = EMAIL_COMERCIAL_CNB
    msg["Reply-To"] = email
    msg.set_content(
        f"NOVA SOLICITAÇÃO DE ORÇAMENTO - CNB TECH SOLUTION\n\n"
        f"Pedido: #{numero_pedido}\n"
        f"Serviço: {servico}\n"
        f"Tipo de cliente: {tipo_cliente or '-'}\n"
        f"Nome/Responsável: {nome}\n"
        f"Empresa: {empresa or '-'}\n"
        f"CPF/CNPJ: {documento or '-'}\n"
        f"E-mail do solicitante: {email}\n"
        f"Telefone/WhatsApp: {telefone}\n"
        f"Cidade: {cidade or '-'}\n\n"
        f"DESCRIÇÃO DO SERVIÇO\n{mensagem}\n\n"
        f"A solicitação também está registrada no painel administrativo."
    )

    # Se o cliente anexou um documento, envia a mesma cópia ao e-mail comercial.
    if caminho_anexo and nome_anexo:
        try:
            caminho = Path(caminho_anexo)
            if caminho.exists():
                extensao = caminho.suffix.lower()
                tipos = {
                    ".pdf": ("application", "pdf"),
                    ".docx": ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document"),
                    ".ppt": ("application", "vnd.ms-powerpoint"),
                    ".pptx": ("application", "vnd.openxmlformats-officedocument.presentationml.presentation"),
                }
                maintype, subtype = tipos.get(extensao, ("application", "octet-stream"))
                msg.add_attachment(caminho.read_bytes(), maintype=maintype, subtype=subtype, filename=nome_anexo)
        except Exception as erro_anexo:
            print(f"[!] Não foi possível anexar o documento ao e-mail: {erro_anexo}")

    try:
        with smtplib.SMTP(SMTP_SERVIDOR, SMTP_PORTA, timeout=20) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha_app)
            servidor.send_message(msg)
        print(f"[+] E-mail do orçamento #{numero_pedido} enviado para {EMAIL_COMERCIAL_CNB}")
        return True
    except Exception as erro:
        print(f"[!] Falha ao enviar e-mail do orçamento #{numero_pedido}: {erro}")
        return False


# ----------------------------------------------------------------------
# -------- [E-MAIL: RESPOSTA DO COMERCIAL PARA O SOLICITANTE] ----------
# ----------------------------------------------------------------------
def enviar_resposta_cliente(email_cliente, nome_cliente, numero_pedido, servico, resposta, caminho_anexo=None, nome_anexo=None):
    senha_app = os.environ.get("CNB_GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    remetente = os.environ.get("CNB_EMAIL_REMETENTE", EMAIL_COMERCIAL_CNB).strip()

    if not senha_app:
        return False, "A variável CNB_GMAIL_APP_PASSWORD não foi encontrada pelo Python/IDLE."

    msg = EmailMessage()
    msg["Subject"] = f"Resposta ao orçamento CNB Tech Solution #{numero_pedido} - {servico}"
    msg["From"] = remetente
    msg["To"] = email_cliente
    msg["Reply-To"] = EMAIL_COMERCIAL_CNB
    msg.set_content(
        f"Olá, {nome_cliente}.\n\n"
        f"Referente ao orçamento #{numero_pedido} - {servico}:\n\n"
        f"{resposta}\n\n"
        f"Atenciosamente,\nCNB Tech Solution\n"
        f"E-mail comercial: {EMAIL_COMERCIAL_CNB}\n"
        f"WhatsApp: (91) 99231-6147"
    )

    if caminho_anexo and nome_anexo:
        try:
            caminho = Path(caminho_anexo)
            if caminho.exists():
                extensao = caminho.suffix.lower()
                tipos = {
                    ".pdf": ("application", "pdf"),
                    ".docx": ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document"),
                    ".ppt": ("application", "vnd.ms-powerpoint"),
                    ".pptx": ("application", "vnd.openxmlformats-officedocument.presentationml.presentation"),
                }
                maintype, subtype = tipos.get(extensao, ("application", "octet-stream"))
                msg.add_attachment(caminho.read_bytes(), maintype=maintype, subtype=subtype, filename=nome_anexo)
        except Exception as erro_anexo:
            print(f"[!] Falha ao anexar arquivo na resposta: {erro_anexo}")

    try:
        with smtplib.SMTP(SMTP_SERVIDOR, SMTP_PORTA, timeout=30) as servidor:
            servidor.ehlo()
            servidor.starttls()
            servidor.ehlo()
            servidor.login(remetente, senha_app)
            servidor.send_message(msg)
        print(f"[+] Resposta do orçamento #{numero_pedido} enviada para {email_cliente}")
        return True, "E-mail enviado com sucesso."
    except smtplib.SMTPAuthenticationError:
        return False, "O Gmail recusou a autenticação. Confira a Senha de App e se ela pertence ao e-mail comercial."
    except smtplib.SMTPRecipientsRefused:
        return False, "O endereço de e-mail do cliente foi recusado pelo servidor."
    except Exception as erro:
        print(f"[!] Falha ao responder orçamento #{numero_pedido}: {erro}")
        return False, f"Falha no envio: {erro}"


LAYOUT_ORCAMENTO_HTML = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Solicitar Orçamento | CNB TECH SOLUTION</title>
<style>
/* ================================================================ */
/* [CSS] FORMULÁRIO DE ORÇAMENTO - CORES E ESTRUTURA               */
/* ================================================================ */
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Tahoma,sans-serif}
body{background:linear-gradient(135deg,#050c16,#0b1e32,#06101d);color:#e2e8f0;min-height:100vh} /* <<<< [FUNDO GERAL + TEXTO PADRÃO] */
.topo-orc{background:#07111f;border-bottom:1px solid rgba(56,189,248,.25);padding:20px 5%;display:flex;justify-content:space-between;align-items:center;gap:15px} /* <<<< [BARRA SUPERIOR DO ORÇAMENTO] */
.topo-orc a{color:#38bdf8;text-decoration:none;font-weight:700} /* <<<< [LINK VOLTAR] */
.orc-wrap{max-width:920px;margin:45px auto;padding:0 20px 60px} /* <<<< [ÁREA CENTRAL DO FORMULÁRIO] */
.orc-card{background:rgba(15,30,48,.96);border:1px solid rgba(56,189,248,.20);border-radius:14px;padding:28px;box-shadow:0 18px 45px rgba(0,0,0,.25)} /* <<<< [CARD PRINCIPAL] */
h1{color:#fff;margin-bottom:8px}.sub{color:#94a3b8;margin-bottom:25px;line-height:1.6}.servico-tag{display:inline-block;color:#38bdf8;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.20);padding:7px 12px;border-radius:20px;margin-bottom:18px;font-size:.82rem}
.grid-form{display:grid;grid-template-columns:1fr 1fr;gap:16px}.grupo{margin-bottom:15px}.grupo.full{grid-column:1/-1}label{display:block;color:#cbd5e1;font-size:.88rem;font-weight:600;margin-bottom:6px}input,select,textarea{width:100%;padding:12px;border-radius:8px;border:1px solid #334155;background:#07111f;color:#f8fafc;outline:none;font-size:1rem}input:focus,select:focus,textarea:focus{border-color:#38bdf8}textarea{min-height:150px;resize:vertical}.btn-enviar{width:100%;border:0;border-radius:8px;padding:14px;background:#38bdf8;color:#07111f;font-weight:800;font-size:1rem;cursor:pointer}.nota{color:#64748b;font-size:.82rem;margin-top:12px;line-height:1.5}@media(max-width:650px){.grid-form{grid-template-columns:1fr}.grupo.full{grid-column:auto}.topo-orc{align-items:flex-start;flex-direction:column}}
</style>
</head>
<body>
<header class="topo-orc"><strong>⚡ CNB TECH SOLUTION</strong><a href="{{ voltar }}">← Voltar ao serviço</a></header>
<main class="orc-wrap">
<div class="orc-card">
<div class="servico-tag">SOLICITAÇÃO • {{ servico }}</div>
<h1>Quero solicitar um orçamento</h1>
<p class="sub">Preencha seus dados e descreva a necessidade. A solicitação será registrada no setor comercial da CNB Tech Solution e, após o envio, você poderá encaminhar os mesmos dados pelo WhatsApp.</p>
<form method="post" enctype="multipart/form-data">
<input type="hidden" name="slug" value="{{ slug }}">
<div class="grid-form">
<div class="grupo"><label>Tipo de solicitante *</label><select name="tipo_cliente" id="tipo_cliente" required><option value="Empresa">Empresa / Pessoa Jurídica</option><option value="Pessoa Física">Pessoa Física</option></select></div>
<div class="grupo"><label>Nome do responsável / Nome completo *</label><input name="nome" required maxlength="120"></div>
<div class="grupo"><label>Empresa / Razão Social</label><input name="empresa" maxlength="160" placeholder="Deixe em branco se for pessoa física"></div>
<div class="grupo"><label>CPF ou CNPJ</label><input name="documento" maxlength="30"></div>
<div class="grupo"><label>E-mail *</label><input type="email" name="email" required maxlength="160"></div>
<div class="grupo"><label>Telefone / WhatsApp *</label><input name="telefone" required maxlength="30"></div>
<div class="grupo full"><label>Cidade / Município</label><input name="cidade" maxlength="120"></div>
<div class="grupo full"><label>Serviço selecionado</label><input value="{{ servico }}" readonly></div>
<div class="grupo full"><label>Descrição básica do serviço ou necessidade *</label><textarea name="mensagem" required maxlength="3000" placeholder="Faça um resumo. Se tiver projeto, memorial, especificação ou documento detalhado, anexe abaixo."></textarea></div>
<div class="grupo full"><label>Arquivo detalhado do serviço (opcional)</label><input type="file" name="arquivo" accept=".pdf,.docx,.ppt,.pptx"><p class="nota">Formatos permitidos: PDF, DOCX, PPT e PPTX. Tamanho máximo: 24 MB.</p></div>
<div class="grupo full"><button class="btn-enviar" type="submit">Enviar solicitação e continuar no WhatsApp</button><p class="nota">O pedido e o arquivo ficam registrados no painel administrativo. Se houver anexo, o alerta do WhatsApp informará que um documento foi enviado.</p></div>
</div>
</form>
</div>
</main>
</body>
</html>
"""

@app.route('/solicitar-orcamento/<slug>', methods=['GET','POST'])
def solicitar_orcamento(slug):
    servico = SERVICOS.get(slug)
    if servico is None:
        return "Serviço não encontrado.", 404

    if request.method == 'POST':
        tipo_cliente = request.form.get('tipo_cliente','').strip()
        nome = request.form.get('nome','').strip()
        empresa = request.form.get('empresa','').strip()
        documento = request.form.get('documento','').strip()
        email = request.form.get('email','').strip()
        telefone = request.form.get('telefone','').strip()
        cidade = request.form.get('cidade','').strip()
        mensagem = request.form.get('mensagem','').strip()
        criado_em = datetime.now().strftime('%d/%m/%Y %H:%M')
        arquivo = request.files.get('arquivo')

        if arquivo and arquivo.filename and not arquivo_permitido(arquivo.filename):
            return "Formato de arquivo não permitido. Envie PDF, DOCX, PPT ou PPTX.", 400

        if not nome or not email or not telefone or not mensagem:
            return "Preencha os campos obrigatórios.", 400

        with conectar_banco() as conexao:
            cursor = conexao.execute(
                """INSERT INTO orcamentos
                (nome,empresa,email,telefone,servico,mensagem,status,criado_em,tipo_cliente,documento,cidade)
                VALUES (?,?,?,?,?,?,'Novo',?,?,?,?)""",
                (nome, empresa, email, telefone, servico['titulo'], mensagem, criado_em, tipo_cliente, documento, cidade)
            )
            numero_pedido = cursor.lastrowid

            # Cria ou localiza automaticamente o cadastro comercial do solicitante.
            # Assim, a empresa/pessoa passa a ter uma ficha com todo o histórico de orçamentos.
            empresa_existente = None
            if documento:
                empresa_existente = conexao.execute(
                    "SELECT id FROM empresas WHERE documento=? OR cnpj=? LIMIT 1", (documento, documento)
                ).fetchone()
            if not empresa_existente and email:
                empresa_existente = conexao.execute(
                    "SELECT id FROM empresas WHERE lower(email)=lower(?) LIMIT 1", (email,)
                ).fetchone()

            if empresa_existente:
                empresa_id = empresa_existente["id"]
                conexao.execute(
                    """UPDATE empresas SET responsavel=?, telefone=?, cidade=?, tipo_cliente=?, documento=?
                       WHERE id=?""",
                    (nome, telefone, cidade, tipo_cliente, documento, empresa_id)
                )
            else:
                nome_cadastro = empresa if empresa else nome
                cursor_empresa = conexao.execute(
                    """INSERT INTO empresas
                    (nome,cnpj,responsavel,email,telefone,observacoes,criado_em,tipo_cliente,documento,cidade)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (nome_cadastro, documento if tipo_cliente.lower().startswith('empresa') else '', nome,
                     email, telefone, 'Cadastro automático originado pelo orçamento #' + str(numero_pedido),
                     criado_em, tipo_cliente, documento, cidade)
                )
                empresa_id = cursor_empresa.lastrowid

            conexao.execute("UPDATE orcamentos SET empresa_id=? WHERE id=?", (empresa_id, numero_pedido))

            # Salva o documento enviado pelo visitante e vincula ao orçamento.
            caminho_anexo = None
            nome_anexo = None
            if arquivo and arquivo.filename:
                nome_anexo = secure_filename(arquivo.filename)
                extensao = nome_anexo.rsplit(".", 1)[1].lower()
                nome_salvo = f"orcamento_{numero_pedido}_cliente_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{extensao}"
                caminho_anexo = PASTA_ANEXOS / nome_salvo
                arquivo.save(caminho_anexo)
                conexao.execute(
                    "INSERT INTO anexos_orcamentos (orcamento_id,nome_original,nome_salvo,criado_em) VALUES (?,?,?,?)",
                    (numero_pedido, nome_anexo, nome_salvo, criado_em)
                )

        # Envia uma cópia da solicitação para o e-mail comercial.
        # Se o Gmail ainda não estiver configurado, o orçamento continua salvo no Dashboard.
        enviar_email_orcamento(
            numero_pedido, tipo_cliente, nome, empresa, documento, email,
            telefone, cidade, servico['titulo'], mensagem,
            caminho_anexo=caminho_anexo, nome_anexo=nome_anexo
        )

        texto_whatsapp = (
            f"Olá, CNB Tech Solution! Solicitei um orçamento pelo site.\n\n"
            f"Pedido: #{numero_pedido}\n"
            f"Serviço: {servico['titulo']}\n"
            f"Tipo: {tipo_cliente}\n"
            f"Nome/Responsável: {nome}\n"
            f"Empresa: {empresa or '-'}\n"
            f"CPF/CNPJ: {documento or '-'}\n"
            f"E-mail: {email}\n"
            f"Telefone: {telefone}\n"
            f"Cidade: {cidade or '-'}\n\n"
            f"Descrição: {mensagem}\n\n"
            f"Arquivo anexado: {nome_anexo if nome_anexo else 'Nenhum arquivo anexado'}"
        )
        link_whatsapp = f"https://wa.me/{WHATSAPP_CNB}?text={quote(texto_whatsapp)}"
        return redirect(link_whatsapp)

    return render_template_string(
        LAYOUT_ORCAMENTO_HTML,
        slug=slug,
        servico=servico['titulo'],
        voltar=url_for('pagina_servico', slug=slug)
    )

# Compatibilidade com versões anteriores do formulário
@app.route('/orcamento', methods=['POST'])
def receber_orcamento():
    slug = request.form.get('slug','').strip()
    if slug in SERVICOS:
        return redirect(url_for('solicitar_orcamento', slug=slug))
    return redirect(url_for('home'))

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    erro=''
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); senha=request.form.get('senha','')
        with conectar_banco() as conexao: admin=conexao.execute("SELECT * FROM administradores WHERE email=? AND ativo=1",(email,)).fetchone()
        if admin and check_password_hash(admin['senha_hash'],senha):
            session['admin_id']=admin['id']; session['admin_email']=admin['email']; session['admin_perfil']=admin['perfil']; registrar_atividade('Login administrativo'); return redirect(url_for('admin_dashboard'))
        erro='E-mail ou senha inválidos.'
    return render_template_string("""<!doctype html><html><head><meta charset='utf-8'><title>Login CNB Tech</title>{{css|safe}}</head><body><main class='wrap'><div class='form-card' style='margin:80px auto'><h1>⚡ CNB TECH SOLUTION</h1><p class='muted'>Acesso administrativo</p>{% if erro %}<div class='alerta'>{{erro}}</div>{% endif %}<form method='post'><label>E-mail</label><input class='campo' type='email' name='email' required><label>Senha</label><input class='campo' type='password' name='senha' required><button class='btn'>Entrar</button></form><div style='margin-top:14px;text-align:center'><a class='btn btn-sec' href='/admin/esqueci-senha' style='display:inline-block;text-decoration:none'>Esqueci minha senha</a></div><p class='muted' style='margin-top:18px'>Use o e-mail administrativo configurado no ambiente do servidor.</p></div></main></body></html>""",css=admin_css_atual(),erro=erro)

# ----------------------------------------------------------------------
# -------- [V20 / BOTÃO "ESQUECI MINHA SENHA" DO LOGIN] ---------------
# ----------------------------------------------------------------------
# Esta tela NÃO expõe o RESET_ADMIN_TOKEN. O administrador informa a
# chave temporária configurada no Render e é encaminhado para a rota
# protegida que permite cadastrar uma nova senha.
@app.route('/admin/esqueci-senha', methods=['GET', 'POST'])
def admin_esqueci_senha():
    erro = ''

    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        token_esperado = os.environ.get('RESET_ADMIN_TOKEN', '').strip()

        if not token_esperado:
            erro = 'A recuperação ainda não foi habilitada no servidor. Configure RESET_ADMIN_TOKEN no Render.'
        elif not token or token != token_esperado:
            erro = 'Chave de recuperação inválida.'
        else:
            return redirect(url_for('admin_redefinir_senha', token=token))

    return render_template_string(
        '''
        <!doctype html>
        <html lang="pt-BR">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Esqueci minha senha | CNB Tech Solution</title>
            {{ css|safe }}
        </head>
        <body>
            <main class="wrap">
                <div class="form-card" style="margin:80px auto;max-width:520px">
                    <h1>⚡ CNB TECH SOLUTION</h1>
                    <h2>Recuperar acesso administrativo</h2>
                    <p class="muted">Informe a chave temporária de recuperação configurada no Render.</p>

                    {% if erro %}
                        <div class="alerta">{{ erro }}</div>
                    {% endif %}

                    <form method="post">
                        <label>Chave de recuperação</label>
                        <input class="campo" type="password" name="token" autocomplete="off" required>
                        <button class="btn" type="submit">Continuar</button>
                    </form>

                    <p style="margin-top:18px"><a href="/admin/login">← Voltar para o login</a></p>
                </div>
            </main>
        </body>
        </html>
        ''',
        css=admin_css_atual(),
        erro=erro
    )


# ----------------------------------------------------------------------
# -------- [V20 / RECUPERAÇÃO DE ACESSO ADMIN - TEMPORÁRIA] -----------
# ----------------------------------------------------------------------
# Segurança:
# - Configure RESET_ADMIN_TOKEN e ADMIN_EMAIL no Render.
# - A rota só funciona quando o token da URL coincide com o Environment.
# - Depois de recuperar o acesso, remova RESET_ADMIN_TOKEN do Render.
@app.route('/admin/redefinir-senha', methods=['GET', 'POST'])
def admin_redefinir_senha():
    token_recebido = request.args.get('token', '').strip()
    token_esperado = os.environ.get('RESET_ADMIN_TOKEN', '').strip()
    admin_email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    admin_name = os.environ.get('ADMIN_NAME', 'Administrador Master').strip() or 'Administrador Master'

    if not token_esperado or token_recebido != token_esperado:
        abort(403)

    mensagem = ''
    sucesso = False

    if not admin_email:
        mensagem = 'ADMIN_EMAIL não está configurado no Render.'
    elif request.method == 'POST':
        nova_senha = request.form.get('nova_senha', '')
        confirmar_senha = request.form.get('confirmar_senha', '')

        if len(nova_senha) < 8:
            mensagem = 'A nova senha precisa ter pelo menos 8 caracteres.'
        elif nova_senha != confirmar_senha:
            mensagem = 'As senhas digitadas não conferem.'
        else:
            try:
                iniciar_banco()
                novo_hash = generate_password_hash(nova_senha)
                with conectar_banco() as conexao:
                    admin = conexao.execute(
                        'SELECT id FROM administradores WHERE email=?',
                        (admin_email,)
                    ).fetchone()

                    if admin:
                        conexao.execute(
                            'UPDATE administradores SET senha_hash=?, ativo=1 WHERE email=?',
                            (novo_hash, admin_email)
                        )
                    else:
                        conexao.execute(
                            'INSERT INTO administradores (nome,email,senha_hash,perfil,ativo,criado_em) VALUES (?,?,?,?,?,?)',
                            (
                                admin_name,
                                admin_email,
                                novo_hash,
                                'master',
                                1,
                                datetime.now().strftime('%d/%m/%Y %H:%M')
                            )
                        )
                sucesso = True
                mensagem = 'Senha administrativa atualizada com sucesso. Já pode entrar em /admin/login.'
            except Exception as erro:
                print(f'[ERRO RESET ADMIN] {type(erro).__name__}: {erro}')
                mensagem = 'Não foi possível atualizar a senha. Consulte os Logs do Render.'

    cor = '#22c55e' if sucesso else '#f59e0b'
    return render_template_string(
        '''
        <!doctype html>
        <html lang="pt-BR">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Redefinir senha | CNB Tech Solution</title>
        </head>
        <body style="margin:0;background:#07111f;color:#e2e8f0;font-family:Arial,sans-serif">
            <main style="max-width:520px;margin:70px auto;padding:28px;background:#0f2238;border:1px solid #334155;border-radius:14px">
                <h1 style="margin-top:0">CNB Tech Solution</h1>
                <h2>Redefinir senha do administrador</h2>
                <p style="color:#94a3b8">Conta: {{ email }}</p>
                {% if mensagem %}
                    <div style="padding:12px;border-radius:8px;margin:16px 0;background:#111827;border-left:4px solid {{ cor }}">{{ mensagem }}</div>
                {% endif %}
                {% if not sucesso and email %}
                <form method="post">
                    <label>Nova senha</label>
                    <input type="password" name="nova_senha" minlength="8" required style="width:100%;box-sizing:border-box;padding:12px;margin:7px 0 14px;border-radius:8px;border:1px solid #475569">
                    <label>Confirmar nova senha</label>
                    <input type="password" name="confirmar_senha" minlength="8" required style="width:100%;box-sizing:border-box;padding:12px;margin:7px 0 18px;border-radius:8px;border:1px solid #475569">
                    <button type="submit" style="width:100%;padding:12px;border:0;border-radius:8px;background:#38bdf8;color:#07111f;font-weight:bold;cursor:pointer">Atualizar senha</button>
                </form>
                {% endif %}
            </main>
        </body>
        </html>
        ''',
        email=admin_email,
        mensagem=mensagem,
        sucesso=sucesso,
        cor=cor
    )

@app.route('/admin/logout')
def admin_logout(): session.clear(); return redirect(url_for('admin_login'))

@app.route('/admin')
@login_obrigatorio
def admin_dashboard():
    # [DASHBOARD] Busca no SQLite os totais exibidos nos cards numéricos.
    with conectar_banco() as c:
        totais={k:c.execute(q).fetchone()[0] for k,q in {'empresas':'SELECT COUNT(*) FROM empresas','orcamentos':'SELECT COUNT(*) FROM orcamentos','novos':"SELECT COUNT(*) FROM orcamentos WHERE status='Novo'",'projetos':'SELECT COUNT(*) FROM projetos','equipe':'SELECT COUNT(*) FROM equipe_empresa','galeria':'SELECT COUNT(*) FROM galeria_publica','noticias':'SELECT COUNT(*) FROM noticias','visitas':'SELECT COUNT(*) FROM visitas','admins':'SELECT COUNT(*) FROM administradores WHERE ativo=1'}.items()}
        # [DASHBOARD] Lista os 8 orçamentos mais recentes para a tabela inicial.
        recentes=c.execute('SELECT * FROM orcamentos ORDER BY id DESC LIMIT 8').fetchall()
    linhas=''.join(f"<tr><td>{r['nome']}</td><td>{r['empresa'] or '-'}</td><td>{r['servico']}</td><td>{r['status']}</td><td><a class='btn btn-sec btn-mini' href='/admin/orcamentos/{r['id']}'>Ver detalhes</a><br><small>{r['criado_em']}</small></td></tr>" for r in recentes) or "<tr><td colspan='5'>Nenhuma solicitação.</td></tr>"
    cards=''.join(f"<div class='card'><div class='muted'>{rot}</div><div class='numero'>{totais[ch]}</div></div>" for ch,rot in [('empresas','Empresas'),('orcamentos','Orçamentos'),('novos','Novos'),('projetos','Projetos'),('equipe','Equipe'),('galeria','Galeria'),('noticias','Notícias'),('visitas','Visitas'),('admins','Administradores')])
    return admin_shell('Dashboard',f"<h1>Dashboard</h1><p class='muted'>Central administrativa e comercial da CNB Tech Solution.</p><div class='grid' style='margin:22px 0'>{cards}</div><h2>Solicitações recentes</h2><table class='tabela'><tr><th>Contato</th><th>Empresa</th><th>Serviço</th><th>Status</th><th>Data</th></tr>{linhas}</table>")

# ----------------------------------------------------------------------
# -------- [V20 / ADMIN: CONTATOS E REDES SOCIAIS] ---------------------
# ----------------------------------------------------------------------
# Centraliza os links dos cards Facebook / YouTube / Instagram e os
# dados exibidos na área de Contato e no rodapé da Home.
@app.route('/admin/contatos-redes', methods=['GET', 'POST'])
@login_obrigatorio
def admin_contatos_redes():
    from html import escape

    if request.method == 'POST':
        email_original = request.form.get('contato_email', '').strip()
        telefone = request.form.get('contato_telefone', '').strip()

        email = normalizar_email_site(email_original)
        if not email:
            flash('Informe um e-mail válido para o contato do site.')
            return redirect(url_for('admin_contatos_redes'))

        if not somente_digitos(telefone):
            flash('Informe um telefone válido.')
            return redirect(url_for('admin_contatos_redes'))

        redes = {}
        for chave, nome_rede in (
            ('facebook_url', 'Facebook'),
            ('youtube_url', 'YouTube'),
            ('instagram_url', 'Instagram'),
        ):
            original = request.form.get(chave, '').strip()
            normalizada = normalizar_url_externa(original)
            if original and not normalizada:
                flash(f'O link do {nome_rede} deve começar com http:// ou https://.')
                return redirect(url_for('admin_contatos_redes'))
            redes[chave] = normalizada

        salvar_config_site('contato_email', email)
        salvar_config_site('contato_telefone', telefone)
        for chave, valor in redes.items():
            salvar_config_site(chave, valor)

        registrar_atividade('Contatos e links das redes sociais atualizados')
        flash('Contatos e redes sociais atualizados com sucesso.')
        return redirect(url_for('admin_contatos_redes'))

    valores = {
        chave: obter_config_site(chave, padrao)
        for chave, padrao in CONTATOS_REDES_PADRAO.items()
    }

    e_email = escape(valores['contato_email'])
    e_telefone = escape(valores['contato_telefone'])
    e_facebook = escape(valores['facebook_url'])
    e_youtube = escape(valores['youtube_url'])
    e_instagram = escape(valores['instagram_url'])

    conteudo = f"""
    <h1>Contatos & Redes Sociais</h1>
    <p class='muted'>Edite os contatos do rodapé e os links dos cards de Facebook, YouTube e Instagram sem alterar o código.</p>

    <div class='form-card' style='max-width:860px'>
        <form method='post'>
            <h2>Contatos da CNB Tech Solution</h2>
            <label>E-mail</label>
            <input class='campo' type='email' name='contato_email' required value='{e_email}'>

            <label>Telefone / WhatsApp</label>
            <input class='campo' name='contato_telefone' required value='{e_telefone}' placeholder='(91) 99231-6147'>
            <p class='nota-admin'>O mesmo número alimenta automaticamente os botões Ligar e WhatsApp da Home.</p>

            <h2 style='margin-top:26px'>Links das redes sociais</h2>
            <label>Facebook</label>
            <input class='campo' type='url' name='facebook_url' value='{e_facebook}' placeholder='https://facebook.com/...'>

            <label>YouTube</label>
            <input class='campo' type='url' name='youtube_url' value='{e_youtube}' placeholder='https://youtube.com/@...'>

            <label>Instagram</label>
            <input class='campo' type='url' name='instagram_url' value='{e_instagram}' placeholder='https://instagram.com/...'>
            <p class='nota-admin'>Deixe um campo vazio para manter o card visível como “não configurado”.</p>

            <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:18px'>
                <button class='btn' type='submit'>Salvar contatos e redes</button>
                <a class='btn btn-sec' href='/#redes-sociais' target='_blank' rel='noopener noreferrer'>Ver na Home</a>
            </div>
        </form>
    </div>
    """
    return admin_shell('Contatos & Redes', conteudo)


@app.route('/admin/editar-site', methods=['GET', 'POST'])
@login_obrigatorio
def admin_editar_site():
    from html import escape

    if request.method == 'POST':
        # --------------------------------------------------------------
        # EDITAR SITE 2.0: textos + identidade visual + mídias externas
        # --------------------------------------------------------------
        campos_texto = {
            'status_home': request.form.get('status_home', '').strip(),
            'titulo_home': request.form.get('titulo_home', '').strip(),
            'subtitulo_home': request.form.get('subtitulo_home', '').strip(),
            'rodape_home': request.form.get('rodape_home', '').strip(),
        }
        for chave, valor in campos_texto.items():
            if valor:
                salvar_config_site(chave, valor)

        # Restaura apenas o VISUAL para o padrão CNB Tech, sem apagar textos/mídias.
        if request.form.get('restaurar_visual') == '1':
            for chave, valor in CONFIG_VISUAL_PADRAO.items():
                salvar_config_site(chave, valor)
            for chave, valor in ADMIN_VISUAL_PADRAO.items():
                salvar_config_site(chave, valor)
            registrar_atividade('Identidade visual do site e do painel restaurada para o padrão CNB Tech')
        else:
            tema = normalizar_opcao(request.form.get('tema_site', 'cnb-tech'), set(TEMAS_VISUAIS), 'cnb-tech')
            # [EDITAR SITE 2.0] Valores abaixo controlam diretamente as cores da HOME.
            visual_recebido = {
                'tema_site': tema,
                'logo_largura': str(limitar_inteiro(request.form.get('logo_largura'), 140, 420, CONFIG_VISUAL_PADRAO['logo_largura'])),
                'cor_destaque': normalizar_cor_hex(request.form.get('cor_destaque'), CONFIG_VISUAL_PADRAO['cor_destaque']),
                'cor_fundo': normalizar_cor_hex(request.form.get('cor_fundo'), CONFIG_VISUAL_PADRAO['cor_fundo']),
                'cor_navbar': normalizar_cor_hex(request.form.get('cor_navbar'), CONFIG_VISUAL_PADRAO['cor_navbar']),
                'cor_card': normalizar_cor_hex(request.form.get('cor_card'), CONFIG_VISUAL_PADRAO['cor_card']),
                'cor_card_borda': normalizar_cor_hex(request.form.get('cor_card_borda'), CONFIG_VISUAL_PADRAO['cor_card_borda']),
                'cor_titulo': normalizar_cor_hex(request.form.get('cor_titulo'), CONFIG_VISUAL_PADRAO['cor_titulo']),
                'cor_texto': normalizar_cor_hex(request.form.get('cor_texto'), CONFIG_VISUAL_PADRAO['cor_texto']),
                'card_radius': str(limitar_inteiro(request.form.get('card_radius'), 0, 32, CONFIG_VISUAL_PADRAO['card_radius'])),
                'overlay_video': str(limitar_inteiro(request.form.get('overlay_video'), 0, 85, CONFIG_VISUAL_PADRAO['overlay_video'])),
                'animacao_cards': normalizar_opcao(request.form.get('animacao_cards'), {'desligada', 'leve', 'media'}, CONFIG_VISUAL_PADRAO['animacao_cards']),
            }
            for chave, valor in visual_recebido.items():
                salvar_config_site(chave, valor)

            # [EDITAR SITE 2.0] Valores abaixo controlam as cores do DASHBOARD ADMIN.
            admin_recebido = {
                'admin_sync_tema': '1' if request.form.get('admin_sync_tema') == '1' else '0',
                'admin_cor_fundo': normalizar_cor_hex(request.form.get('admin_cor_fundo'), ADMIN_VISUAL_PADRAO['admin_cor_fundo']),
                'admin_cor_topo': normalizar_cor_hex(request.form.get('admin_cor_topo'), ADMIN_VISUAL_PADRAO['admin_cor_topo']),
                'admin_cor_superficie': normalizar_cor_hex(request.form.get('admin_cor_superficie'), ADMIN_VISUAL_PADRAO['admin_cor_superficie']),
                'admin_cor_borda': normalizar_cor_hex(request.form.get('admin_cor_borda'), ADMIN_VISUAL_PADRAO['admin_cor_borda']),
                'admin_cor_titulo': normalizar_cor_hex(request.form.get('admin_cor_titulo'), ADMIN_VISUAL_PADRAO['admin_cor_titulo']),
                'admin_cor_texto': normalizar_cor_hex(request.form.get('admin_cor_texto'), ADMIN_VISUAL_PADRAO['admin_cor_texto']),
                'admin_cor_destaque': normalizar_cor_hex(request.form.get('admin_cor_destaque'), ADMIN_VISUAL_PADRAO['admin_cor_destaque']),
            }
            for chave, valor in admin_recebido.items():
                salvar_config_site(chave, valor)

        # Logo e vídeo continuam FORA do Python para evitar código pesado/travamento.
        logo = request.files.get('logo_site')
        if logo and logo.filename:
            nome_original = secure_filename(logo.filename)
            ext = extensao_arquivo(nome_original)
            if ext not in EXTENSOES_LOGO_SITE:
                flash('Logo não atualizada: use PNG, WEBP, JPG ou JPEG.')
                return redirect(url_for('admin_editar_site'))
            for antigo in PASTA_MIDIA_SITE.glob('logo-site.*'):
                try:
                    antigo.unlink()
                except OSError:
                    pass
            nome_salvo = f'logo-site.{ext}'
            logo.save(PASTA_MIDIA_SITE / nome_salvo)
            salvar_config_site('logo_arquivo', nome_salvo)
            registrar_atividade(f'Logo do site atualizada: {nome_salvo}')

        video = request.files.get('video_site')
        if video and video.filename:
            nome_original = secure_filename(video.filename)
            ext = extensao_arquivo(nome_original)
            if ext not in EXTENSOES_VIDEO_SITE:
                flash('Vídeo não atualizado: use arquivo MP4.')
                return redirect(url_for('admin_editar_site'))
            for antigo in PASTA_MIDIA_SITE.glob('video-home-site.*'):
                try:
                    antigo.unlink()
                except OSError:
                    pass
            nome_salvo = 'video-home-site.mp4'
            video.save(PASTA_MIDIA_SITE / nome_salvo)
            salvar_config_site('video_arquivo', nome_salvo)
            registrar_atividade(f'Vídeo da Home atualizado: {nome_salvo}')

        if request.form.get('restaurar_logo') == '1':
            salvar_config_site('logo_arquivo', '')
            registrar_atividade('Logo do site restaurada para o arquivo padrão')
        if request.form.get('restaurar_video') == '1':
            salvar_config_site('video_arquivo', '')
            registrar_atividade('Vídeo da Home restaurado para o arquivo padrão')

        registrar_atividade('Editar Site 2.0: conteúdo/identidade visual atualizados')
        flash('Editar Site 2.0: alterações publicadas com sucesso.')
        return redirect(url_for('admin_editar_site'))

    status_home = obter_config_site('status_home', 'Ecossistema de soluções digitais')
    titulo_home = obter_config_site('titulo_home', 'Tecnologia que conecta infraestrutura e inovação.')
    subtitulo_home = obter_config_site('subtitulo_home', 'Soluções integradas para conectividade, infraestrutura de TI, desenvolvimento de sistemas, educação digital e produção audiovisual.')
    rodape_home = obter_config_site('rodape_home', 'Tecnologia, infraestrutura e soluções digitais.')
    logo_atual = obter_config_site('logo_arquivo', '') or LOGO_CNB_NOME
    video_atual = obter_config_site('video_arquivo', '') or VIDEO_HOME_NOME
    visual = configuracao_visual_atual()
    admin_visual = configuracao_admin_atual()
    admin_manual = admin_visual['manual']
    admin_sync_checked = 'checked' if admin_visual['sync'] else ''
    admin_box_class = 'sincronizado' if admin_visual['sync'] else ''

    # Escape de dados textuais exibidos no HTML do painel.
    e_status = escape(status_home)
    e_titulo = escape(titulo_home)
    e_subtitulo = escape(subtitulo_home)
    e_rodape = escape(rodape_home)
    e_logo = escape(logo_atual)
    e_video = escape(video_atual)

    tema = visual['tema_site']
    tema_cnb = 'ativo' if tema == 'cnb-tech' else ''
    tema_dark = 'ativo' if tema == 'dark' else ''
    tema_corporate = 'ativo' if tema == 'corporate' else ''
    anim = visual['animacao_cards']
    opt_off = 'selected' if anim == 'desligada' else ''
    opt_leve = 'selected' if anim == 'leve' else ''
    opt_media = 'selected' if anim == 'media' else ''

    conteudo = f"""
    <h1>Editar Site 2.0</h1>
    <p class='muted'>Construtor visual da Home: escolha um tema, ajuste cores, cards, logo e animações, veja a prévia na hora e publique quando estiver pronto.</p>

    <form method='post' enctype='multipart/form-data' id='editorSiteForm'>
      <div class='editor-2-grid' style='margin-top:22px'>

        <div>
          <section class='painel-editor'>
            <h2>1. Temas rápidos</h2>
            <p class='nota-admin'>Os temas preenchem os controles abaixo. Você ainda pode personalizar cada detalhe antes de salvar.</p>
            <input type='hidden' name='tema_site' id='tema_site' value='{escape(tema)}'>
            <div class='tema-grid'>
              <button type='button' class='tema-btn {tema_cnb}' data-tema='cnb-tech'><span>CNB Tech</span><small>Azul tecnológico e contraste premium</small></button>
              <button type='button' class='tema-btn {tema_dark}' data-tema='dark'><span>Dark</span><small>Preto profundo, ciano e cards discretos</small></button>
              <button type='button' class='tema-btn {tema_corporate}' data-tema='corporate'><span>Corporate</span><small>Visual sóbrio para empresas e propostas</small></button>
            </div>

            <div class='grupo-titulo'>Logo e estrutura</div>
            <label>Tamanho da logo na Home</label>
            <div class='controle-range'>
              <input type='range' min='140' max='420' step='5' name='logo_largura' id='logo_largura' value='{visual['logo_largura']}'>
              <output id='logo_largura_out'>{visual['logo_largura']} px</output>
            </div>
            <div class='help'>Ajuste sem editar CSS. No celular o tamanho é limitado automaticamente.</div>

            <label>Arredondamento dos cards</label>
            <div class='controle-range'>
              <input type='range' min='0' max='32' step='1' name='card_radius' id='card_radius' value='{visual['card_radius']}'>
              <output id='card_radius_out'>{visual['card_radius']} px</output>
            </div>

            <label>Escurecimento do vídeo de fundo</label>
            <div class='controle-range'>
              <input type='range' min='0' max='85' step='1' name='overlay_video' id='overlay_video' value='{visual['overlay_video']}'>
              <output id='overlay_video_out'>{visual['overlay_video']}%</output>
            </div>

            <label>Animação dos cards</label>
            <select class='select-campo' name='animacao_cards' id='animacao_cards'>
              <option value='desligada' {opt_off}>Desligada</option>
              <option value='leve' {opt_leve}>Leve</option>
              <option value='media' {opt_media}>Média</option>
            </select>

            <div class='grupo-titulo'>Paleta de cores</div>
            <div class='controle-linha'><label>Cor de destaque</label><input type='color' name='cor_destaque' id='cor_destaque' value='{visual['cor_destaque']}'></div>
            <div class='controle-linha'><label>Fundo geral</label><input type='color' name='cor_fundo' id='cor_fundo' value='{visual['cor_fundo']}'></div>
            <div class='controle-linha'><label>Barra superior</label><input type='color' name='cor_navbar' id='cor_navbar' value='{visual['cor_navbar']}'></div>
            <div class='controle-linha'><label>Fundo dos cards</label><input type='color' name='cor_card' id='cor_card' value='{visual['cor_card']}'></div>
            <div class='controle-linha'><label>Borda dos cards</label><input type='color' name='cor_card_borda' id='cor_card_borda' value='{visual['cor_card_borda']}'></div>
            <div class='controle-linha'><label>Títulos</label><input type='color' name='cor_titulo' id='cor_titulo' value='{visual['cor_titulo']}'></div>
            <div class='controle-linha'><label>Textos secundários</label><input type='color' name='cor_texto' id='cor_texto' value='{visual['cor_texto']}'></div>

            <div class='grupo-titulo'>Painel administrativo</div>
            <label class='switch-admin'>
              <input type='checkbox' name='admin_sync_tema' id='admin_sync_tema' value='1' {admin_sync_checked}>
              <span><strong>Usar as cores do site no Dashboard</strong><br><small class='muted'>Quando ativado, o Admin acompanha automaticamente o tema e a paleta publicados acima.</small></span>
            </label>
            <div class='admin-manual-box {admin_box_class}' id='adminManualBox'>
              <p class='nota-admin' style='margin-top:0'>Desative a sincronização para usar estas cores apenas no painel administrativo.</p>
              <div class='controle-linha'><label>Fundo do painel</label><input type='color' name='admin_cor_fundo' id='admin_cor_fundo' value='{admin_manual['admin_cor_fundo']}'></div>
              <div class='controle-linha'><label>Barra superior</label><input type='color' name='admin_cor_topo' id='admin_cor_topo' value='{admin_manual['admin_cor_topo']}'></div>
              <div class='controle-linha'><label>Cards e blocos</label><input type='color' name='admin_cor_superficie' id='admin_cor_superficie' value='{admin_manual['admin_cor_superficie']}'></div>
              <div class='controle-linha'><label>Bordas</label><input type='color' name='admin_cor_borda' id='admin_cor_borda' value='{admin_manual['admin_cor_borda']}'></div>
              <div class='controle-linha'><label>Títulos do painel</label><input type='color' name='admin_cor_titulo' id='admin_cor_titulo' value='{admin_manual['admin_cor_titulo']}'></div>
              <div class='controle-linha'><label>Textos secundários</label><input type='color' name='admin_cor_texto' id='admin_cor_texto' value='{admin_manual['admin_cor_texto']}'></div>
              <div class='controle-linha'><label>Destaques e botões</label><input type='color' name='admin_cor_destaque' id='admin_cor_destaque' value='{admin_manual['admin_cor_destaque']}'></div>
            </div>
          </section>

          <section class='painel-editor' style='margin-top:18px'>
            <h2>2. Logo e vídeo</h2>
            <p class='nota-admin'>As mídias continuam fora do arquivo Python. Isso evita travamentos no IDLE e permite trocar a identidade pelo painel.</p>
            <div class='editor-grid'>
              <div>
                <div class='preview-midia'><img id='logoUploadPreview' src='/logo-cnb?t={datetime.now().timestamp()}' alt='Logo atual'></div>
                <div class='arquivo-atual'>Logo atual: {e_logo}</div>
                <label>Trocar logo</label>
                <input class='campo' id='logo_site_input' type='file' name='logo_site' accept='.png,.webp,.jpg,.jpeg,image/png,image/webp,image/jpeg'>
                <label style='display:flex;gap:8px;align-items:center'><input type='checkbox' name='restaurar_logo' value='1'> Restaurar logo padrão</label>
              </div>
              <div>
                <div class='preview-midia'><video id='videoUploadPreview' controls muted preload='metadata'><source src='/video-home?t={datetime.now().timestamp()}' type='video/mp4'></video></div>
                <div class='arquivo-atual'>Vídeo atual: {e_video}</div>
                <label>Trocar vídeo MP4</label>
                <input class='campo' id='video_site_input' type='file' name='video_site' accept='.mp4,video/mp4'>
                <label style='display:flex;gap:8px;align-items:center'><input type='checkbox' name='restaurar_video' value='1'> Restaurar vídeo padrão</label>
              </div>
            </div>
          </section>

          <section class='painel-editor' style='margin-top:18px'>
            <h2>3. Textos da Home</h2>
            <label>Indicador superior</label>
            <input class='campo preview-texto' id='status_home' name='status_home' maxlength='120' value='{e_status}'>
            <label>Título principal</label>
            <input class='campo preview-texto' id='titulo_home' name='titulo_home' maxlength='180' value='{e_titulo}'>
            <label>Descrição</label>
            <textarea class='campo preview-texto' id='subtitulo_home' name='subtitulo_home' rows='4' maxlength='600'>{e_subtitulo}</textarea>
            <label>Texto do rodapé</label>
            <input class='campo' name='rodape_home' maxlength='220' value='{e_rodape}'>
          </section>

          <div class='acoes-editor'>
            <button class='btn btn-salvar' type='submit'>Publicar alterações</button>
            <a class='btn btn-sec' href='/' target='_blank' rel='noopener noreferrer'>Abrir site</a>
            <button class='btn btn-outline' type='submit' name='restaurar_visual' value='1' onclick="return confirm('Restaurar somente o visual para o padrão CNB Tech?')">Restaurar visual padrão</button>
          </div>
        </div>

        <aside class='preview-site' id='previewSite'>
          <div class='preview-top' id='previewTop'>
            <img src='/logo-cnb?t={datetime.now().timestamp()}' class='preview-logo' id='previewLogo' alt='CNB Tech Solution'>
          </div>
          <div class='preview-hero' id='previewHero'>
            <div class='preview-conteudo'>
              <div class='preview-status' id='previewStatus'>{e_status}</div>
              <h3 class='preview-titulo' id='previewTitulo'>{e_titulo}</h3>
              <p class='preview-sub' id='previewSub'>{e_subtitulo}</p>
              <div class='preview-cards'>
                <div class='preview-card'><span class='preview-icone'>◉</span><strong>Redes e Conectividade</strong><p>Soluções de rede e integração.</p></div>
                <div class='preview-card'><span class='preview-icone'>▦</span><strong>Infraestrutura de TI</strong><p>Ambientes corporativos e tecnologia.</p></div>
                <div class='preview-card'><span class='preview-icone'>&lt;/&gt;</span><strong>Desenvolvimento</strong><p>Sistemas e plataformas digitais.</p></div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </form>

    <script>
    (() => {{
      const presets = {{
        'cnb-tech': {{accent:'#38bdf8', bg:'#050c15', nav:'#071426', card:'#0f1e30', border:'#334155', title:'#f1f5f9', text:'#94a3b8', radius:14, overlay:48, anim:'media'}},
        'dark': {{accent:'#22d3ee', bg:'#020617', nav:'#020617', card:'#111827', border:'#1f2937', title:'#f8fafc', text:'#9ca3af', radius:10, overlay:62, anim:'leve'}},
        'corporate': {{accent:'#2563eb', bg:'#0b1220', nav:'#0f172a', card:'#172033', border:'#334155', title:'#ffffff', text:'#cbd5e1', radius:8, overlay:56, anim:'leve'}}
      }};

      const $ = id => document.getElementById(id);
      const campos = ['cor_destaque','cor_fundo','cor_navbar','cor_card','cor_card_borda','cor_titulo','cor_texto','logo_largura','card_radius','overlay_video','animacao_cards','status_home','titulo_home','subtitulo_home'];

      function atualizarPreview() {{
        const accent = $('cor_destaque').value, bg = $('cor_fundo').value, nav = $('cor_navbar').value;
        const card = $('cor_card').value, border = $('cor_card_borda').value, title = $('cor_titulo').value, txt = $('cor_texto').value;
        const radius = $('card_radius').value, overlay = Number($('overlay_video').value)/100;
        const anim = $('animacao_cards').value;
        $('previewTop').style.background = nav;
        $('previewHero').style.background = `linear-gradient(rgba(5,12,21,${{overlay}}), rgba(5,12,21,${{Math.min(.95,overlay+.10)}})), radial-gradient(circle at 70% 20%, ${{accent}}33, transparent 45%), ${{bg}}`;
        $('previewLogo').style.width = Math.min(Number($('logo_largura').value), 330) + 'px';
        $('previewStatus').style.borderColor = accent;
        $('previewTitulo').style.color = title;
        $('previewSub').style.color = txt;
        document.querySelectorAll('.preview-card').forEach(el => {{
          el.style.background = card; el.style.borderColor = border; el.style.borderRadius = radius+'px'; el.style.color = txt;
          const st = el.querySelector('strong'); if(st) st.style.color = title;
          const ic = el.querySelector('.preview-icone'); if(ic) ic.style.color = accent;
          el.onmouseenter = () => {{ if(anim==='media') el.style.transform='translateY(-6px)'; else if(anim==='leve') el.style.transform='translateY(-2px)'; }};
          el.onmouseleave = () => el.style.transform='none';
        }});
        $('previewStatus').textContent = $('status_home').value;
        $('previewTitulo').textContent = $('titulo_home').value;
        $('previewSub').textContent = $('subtitulo_home').value;
        $('logo_largura_out').value = $('logo_largura').value + ' px';
        $('card_radius_out').value = $('card_radius').value + ' px';
        $('overlay_video_out').value = $('overlay_video').value + '%';
      }}

      document.querySelectorAll('.tema-btn').forEach(btn => btn.addEventListener('click', () => {{
        const key = btn.dataset.tema, p = presets[key];
        $('tema_site').value = key;
        $('cor_destaque').value=p.accent; $('cor_fundo').value=p.bg; $('cor_navbar').value=p.nav; $('cor_card').value=p.card;
        $('cor_card_borda').value=p.border; $('cor_titulo').value=p.title; $('cor_texto').value=p.text;
        $('card_radius').value=p.radius; $('overlay_video').value=p.overlay; $('animacao_cards').value=p.anim;
        document.querySelectorAll('.tema-btn').forEach(x => x.classList.toggle('ativo', x===btn));
        atualizarPreview();
      }}));

      campos.forEach(id => {{ const el=$(id); if(el) {{ el.addEventListener('input', atualizarPreview); el.addEventListener('change', atualizarPreview); }} }});

      const adminSync = $('admin_sync_tema');
      const adminManualBox = $('adminManualBox');
      function atualizarEstadoAdmin() {{
        if (!adminSync || !adminManualBox) return;
        adminManualBox.classList.toggle('sincronizado', adminSync.checked);
      }}
      if (adminSync) adminSync.addEventListener('change', atualizarEstadoAdmin);
      atualizarEstadoAdmin();

      // Prévia local da nova logo e do novo vídeo ANTES de publicar.
      const logoInput = $('logo_site_input');
      if (logoInput) logoInput.addEventListener('change', () => {{
        const arquivo = logoInput.files && logoInput.files[0];
        if (!arquivo) return;
        const url = URL.createObjectURL(arquivo);
        $('previewLogo').src = url;
        const mini = $('logoUploadPreview'); if (mini) mini.src = url;
      }});

      const videoInput = $('video_site_input');
      if (videoInput) videoInput.addEventListener('change', () => {{
        const arquivo = videoInput.files && videoInput.files[0];
        if (!arquivo) return;
        const url = URL.createObjectURL(arquivo);
        const video = $('videoUploadPreview');
        if (video) {{ video.src = url; video.load(); }}
      }});

      atualizarPreview();
    }})();
    </script>
    """
    return admin_shell('Editar Site 2.0', conteudo)

@app.route('/admin/orcamentos', methods=['GET','POST'])
@login_obrigatorio
def admin_orcamentos():
    if request.method == 'POST':
        oid = request.form.get('id')
        status = request.form.get('status')
        valor = request.form.get('valor') or None
        with conectar_banco() as c:
            c.execute('UPDATE orcamentos SET status=?, valor=? WHERE id=?', (status, valor, oid))
        registrar_atividade(f'Orçamento #{oid} atualizado para {status}')
        flash('Orçamento atualizado.')
        return redirect(url_for('admin_orcamentos'))

    with conectar_banco() as c:
        itens = c.execute('SELECT * FROM orcamentos ORDER BY id DESC').fetchall()
        anexos = c.execute('SELECT * FROM anexos_orcamentos ORDER BY id DESC').fetchall()

    anexos_por_orcamento = {}
    for anexo in anexos:
        anexos_por_orcamento.setdefault(anexo['orcamento_id'], []).append(anexo)

    # O HTML é montado por orçamento para manter o mesmo padrão do arquivo atual.
    linhas = ''
    from html import escape
    for r in itens:
        lista_anexos = anexos_por_orcamento.get(r['id'], [])
        html_anexos = ''
        for a in lista_anexos:
            nome = escape(a['nome_original'])
            html_anexos += (
                f"<div class='anexo-item'>📎 {nome} <a class='btn btn-sec btn-mini' href='/admin/orcamentos/anexo/{a['id']}?visualizar=1' target='_blank'>Visualizar</a> <a class='btn btn-mini' href='/admin/orcamentos/anexo/{a['id']}'>Baixar</a> "
                f"<form method='post' action='/admin/orcamentos/anexo/{a['id']}/excluir' style='display:inline' "
                f"onsubmit=\"return confirm('Excluir este anexo?');\">"
                f"<button class='btn danger btn-mini' type='submit'>Excluir</button></form></div>"
            )
        if not html_anexos:
            html_anexos = "<small class='muted'>Nenhum arquivo anexado.</small>"

        status_atual = escape(str(r['status'] or 'Novo'))
        opcoes = ['Novo', 'Em análise', 'Orçamento enviado', 'Negociação', 'Aprovado', 'Recusado']
        select_opcoes = ''.join(
            f"<option value='{escape(op)}' {'selected' if op == r['status'] else ''}>{escape(op)}</option>"
            for op in opcoes
        )

        linhas += f"""
        <tr>
            <td>#{r['id']}</td>
            <td>{escape(str(r['nome'] or '-'))}<br>
                <small>{escape(str(r['email'] or '-'))} • {escape(str(r['telefone'] or '-'))}</small><br>
                <small>{escape(str(r['tipo_cliente'] or '-'))} • {escape(str(r['documento'] or '-'))} • {escape(str(r['cidade'] or '-'))}</small>
            </td>
            <td>{escape(str(r['empresa'] or '-'))}</td>
            <td><strong>{escape(str(r['servico'] or '-'))}</strong><br><small>{escape(str(r['mensagem'] or '-'))}</small><br><br><a class='btn btn-sec btn-mini' href='/admin/orcamentos/{r['id']}'>Ver detalhes</a></td>
            <td>
                <form method='post'>
                    <input type='hidden' name='id' value='{r['id']}'>
                    <select name='status' class='campo'>{select_opcoes}</select>
                    <input class='campo' name='valor' type='number' step='0.01' value='{r['valor'] or ''}' placeholder='Valor R$'>
                    <button class='btn' type='submit'>Salvar</button>
                </form>
                <hr class='separador'>
                <strong>Arquivos do orçamento</strong>
                <div class='lista-anexos'>{html_anexos}</div>
                <form method='post' action='/admin/orcamentos/{r['id']}/anexar' enctype='multipart/form-data' class='form-anexo'>
                    <label class='btn btn-anexo'>📎 Anexar arquivo
                        <input type='file' name='arquivo' accept='.pdf,.docx,.ppt,.pptx' required hidden>
                    </label>
                    <button class='btn' type='submit'>Enviar</button>
                    <small class='muted'>PDF, DOCX, PPT ou PPTX • até 25 MB</small>
                </form>
            </td>
        </tr>"""

    return admin_shell(
        'Orçamentos',
        f"<h1>Orçamentos</h1><p class='muted'>Solicitações enviadas pelo site e documentos vinculados a cada orçamento.</p>"
        f"<table class='tabela'><tr><th>ID</th><th>Contato</th><th>Empresa</th><th>Serviço</th><th>Gestão e arquivos</th></tr>"
        f"{linhas or '<tr><td colspan=5>Nenhum orçamento.</td></tr>'}</table>"
    )


# ----------------------------------------------------------------------
# -------- [PYTHON: ANEXAR ARQUIVOS AOS ORÇAMENTOS NO ADMIN] -----------
# ----------------------------------------------------------------------
@app.route('/admin/orcamentos/<int:orcamento_id>/anexar', methods=['POST'])
@login_obrigatorio
def anexar_arquivo_orcamento(orcamento_id):
    arquivo = request.files.get('arquivo')

    if not arquivo or not arquivo.filename:
        flash('Selecione um arquivo para anexar.')
        return redirect(url_for('admin_orcamentos'))

    if not arquivo_permitido(arquivo.filename):
        flash('Formato não permitido. Use PDF, DOCX, PPT ou PPTX.')
        return redirect(url_for('admin_orcamentos'))

    with conectar_banco() as c:
        existe = c.execute('SELECT id FROM orcamentos WHERE id=?', (orcamento_id,)).fetchone()
    if not existe:
        abort(404)

    nome_original = secure_filename(arquivo.filename)
    extensao = nome_original.rsplit('.', 1)[1].lower()
    nome_salvo = f"orcamento_{orcamento_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{extensao}"
    arquivo.save(PASTA_ANEXOS / nome_salvo)

    with conectar_banco() as c:
        c.execute(
            'INSERT INTO anexos_orcamentos (orcamento_id,nome_original,nome_salvo,criado_em) VALUES (?,?,?,?)',
            (orcamento_id, nome_original, nome_salvo, datetime.now().strftime('%d/%m/%Y %H:%M'))
        )

    registrar_atividade(f'Arquivo anexado ao orçamento #{orcamento_id}: {nome_original}')
    flash('Arquivo anexado com sucesso.')
    return redirect(url_for('admin_orcamentos'))


@app.route('/admin/orcamentos/anexo/<int:anexo_id>')
@login_obrigatorio
def baixar_anexo_orcamento(anexo_id):
    with conectar_banco() as c:
        anexo = c.execute('SELECT * FROM anexos_orcamentos WHERE id=?', (anexo_id,)).fetchone()
    if not anexo:
        abort(404)
    visualizar = request.args.get('visualizar') == '1'
    extensao = anexo['nome_original'].rsplit('.', 1)[-1].lower() if '.' in anexo['nome_original'] else ''
    # PDF pode ser aberto diretamente no navegador. DOCX/PPT/PPTX dependem do programa instalado,
    # então o navegador poderá baixá-los mesmo quando o botão Visualizar for usado.
    return send_from_directory(
        PASTA_ANEXOS,
        anexo['nome_salvo'],
        as_attachment=not (visualizar and extensao == 'pdf'),
        download_name=anexo['nome_original']
    )


@app.route('/admin/orcamentos/anexo/<int:anexo_id>/excluir', methods=['POST'])
@login_obrigatorio
def excluir_anexo_orcamento(anexo_id):
    with conectar_banco() as c:
        anexo = c.execute('SELECT * FROM anexos_orcamentos WHERE id=?', (anexo_id,)).fetchone()
        if not anexo:
            abort(404)
        c.execute('DELETE FROM anexos_orcamentos WHERE id=?', (anexo_id,))

    caminho = PASTA_ANEXOS / anexo['nome_salvo']
    if caminho.exists():
        caminho.unlink()

    registrar_atividade(f"Arquivo excluído do orçamento #{anexo['orcamento_id']}: {anexo['nome_original']}")
    flash('Arquivo excluído.')
    return redirect(url_for('admin_orcamentos'))


@app.route('/admin/empresas', methods=['GET','POST'])
@login_obrigatorio
def admin_empresas():
    if request.method=='POST':
        vals=[request.form.get(x,'').strip() for x in ['nome','cnpj','responsavel','email','telefone','observacoes']]
        with conectar_banco() as c:
            c.execute('INSERT INTO empresas (nome,cnpj,responsavel,email,telefone,observacoes,criado_em,tipo_cliente,documento,cidade) VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (*vals,datetime.now().strftime('%d/%m/%Y %H:%M'),'Empresa',vals[1],''))
        registrar_atividade(f'Empresa cadastrada: {vals[0]}'); flash('Empresa cadastrada.'); return redirect(url_for('admin_empresas'))
    with conectar_banco() as c:
        itens=c.execute('SELECT * FROM empresas ORDER BY id DESC').fetchall()
        contagens={r['empresa_id']:r['total'] for r in c.execute('SELECT empresa_id, COUNT(*) total FROM orcamentos WHERE empresa_id IS NOT NULL GROUP BY empresa_id').fetchall()}
    from html import escape
    linhas=''.join(
        f"<tr><td><strong>{escape(str(r['nome']))}</strong><br><small>{escape(str(r['tipo_cliente'] or 'Empresa'))}</small></td>"
        f"<td>{escape(str(r['documento'] or r['cnpj'] or '-'))}</td><td>{escape(str(r['responsavel'] or '-'))}</td>"
        f"<td>{escape(str(r['email'] or '-'))}</td><td>{contagens.get(r['id'],0)}</td>"
        f"<td><a class='btn' href='/admin/empresas/{r['id']}'>Abrir ficha</a></td></tr>" for r in itens)
    form="<div class='form-card'><h2>Nova empresa</h2><form method='post'>"+''.join(f"<input class='campo' name='{n}' placeholder='{p}' {'required' if n=='nome' else ''}>" for n,p in [('nome','Nome da empresa'),('cnpj','CNPJ'),('responsavel','Responsável'),('email','E-mail'),('telefone','Telefone'),('observacoes','Observações')])+"<button class='btn'>Cadastrar</button></form></div>"
    return admin_shell('Empresas',f"<h1>Empresas e Clientes</h1><p class='muted'>Abra a ficha para consultar solicitações, descrições e arquivos de cada cliente.</p>{form}<h2 style='margin-top:25px'>Cadastrados</h2><table class='tabela'><tr><th>Cliente</th><th>CPF/CNPJ</th><th>Responsável</th><th>E-mail</th><th>Orçamentos</th><th>Ação</th></tr>{linhas or '<tr><td colspan=6>Nenhum cliente.</td></tr>'}</table>")


# ----------------------------------------------------------------------
# -------- [PYTHON: FICHA DA EMPRESA / HISTÓRICO COMERCIAL] ------------
# ----------------------------------------------------------------------
@app.route('/admin/empresas/<int:empresa_id>')
@login_obrigatorio
def admin_empresa_detalhe(empresa_id):
    from html import escape
    with conectar_banco() as c:
        empresa=c.execute('SELECT * FROM empresas WHERE id=?',(empresa_id,)).fetchone()
        if not empresa:
            abort(404)
        orcamentos=c.execute('SELECT * FROM orcamentos WHERE empresa_id=? ORDER BY id DESC',(empresa_id,)).fetchall()
        ids=[r['id'] for r in orcamentos]
        anexos=[]
        if ids:
            marcadores=','.join('?' for _ in ids)
            anexos=c.execute(f'SELECT * FROM anexos_orcamentos WHERE orcamento_id IN ({marcadores}) ORDER BY id DESC',ids).fetchall()

    anexos_por={}
    for a in anexos:
        anexos_por.setdefault(a['orcamento_id'],[]).append(a)

    historico=''
    for o in orcamentos:
        arquivos=anexos_por.get(o['id'],[])
        html_arquivos=''.join(
            f"<div class='anexo-item'>📎 {escape(a['nome_original'])} "
            f"<a class='btn btn-sec btn-mini' href='/admin/orcamentos/anexo/{a['id']}?visualizar=1' target='_blank'>Visualizar</a> "
            f"<a class='btn btn-mini' href='/admin/orcamentos/anexo/{a['id']}'>Baixar</a></div>" for a in arquivos
        ) or "<p class='muted'>Nenhum arquivo anexado a esta solicitação.</p>"
        valor = f"R$ {o['valor']:.2f}" if o['valor'] is not None else 'Não informado'
        historico += f"""
        <section class='bloco'>
            <div class='acoes' style='justify-content:space-between;align-items:center'>
                <div><strong>Orçamento #{o['id']} • {escape(str(o['servico']))}</strong><br><small class='muted'>{escape(str(o['criado_em']))}</small></div>
                <span class='badge'>{escape(str(o['status']))}</span>
            </div>
            <h3>Descrição enviada</h3><div class='descricao'>{escape(str(o['mensagem'] or '-'))}</div>
            <p><strong>Valor:</strong> {valor}</p>
            <h3>Arquivos</h3>{html_arquivos}
            <div class='acoes'><a class='btn' href='/admin/orcamentos/{o['id']}'>Abrir orçamento completo</a></div>
        </section>"""

    conteudo=f"""
    <div class='acoes'><a class='btn btn-sec' href='/admin/empresas'>← Voltar</a></div>
    <h1>{escape(str(empresa['nome']))}</h1><p class='muted'>Ficha comercial e histórico completo do cliente.</p>
    <section class='bloco detalhe-grid'>
        <div><strong>Tipo</strong><br>{escape(str(empresa['tipo_cliente'] or 'Empresa'))}</div>
        <div><strong>CPF/CNPJ</strong><br>{escape(str(empresa['documento'] or empresa['cnpj'] or '-'))}</div>
        <div><strong>Responsável</strong><br>{escape(str(empresa['responsavel'] or '-'))}</div>
        <div><strong>E-mail</strong><br>{escape(str(empresa['email'] or '-'))}</div>
        <div><strong>Telefone</strong><br>{escape(str(empresa['telefone'] or '-'))}</div>
        <div><strong>Cidade</strong><br>{escape(str(empresa['cidade'] or '-'))}</div>
    </section>
    <h2>Histórico de orçamentos</h2>
    {historico or "<div class='bloco'><p class='muted'>Este cliente ainda não possui orçamento vinculado.</p></div>"}
    """
    return admin_shell('Ficha do cliente',conteudo)


# ----------------------------------------------------------------------
# ------------- [PYTHON: DETALHE COMPLETO DO ORÇAMENTO] ----------------
# ----------------------------------------------------------------------
@app.route('/admin/orcamentos/<int:orcamento_id>')
@login_obrigatorio
def admin_orcamento_detalhe(orcamento_id):
    from html import escape
    with conectar_banco() as c:
        o=c.execute('SELECT * FROM orcamentos WHERE id=?',(orcamento_id,)).fetchone()
        if not o:
            abort(404)
        anexos=c.execute('SELECT * FROM anexos_orcamentos WHERE orcamento_id=? ORDER BY id DESC',(orcamento_id,)).fetchall()
    arquivos=''.join(
        f"<div class='anexo-item'>📎 {escape(a['nome_original'])} "
        f"<a class='btn btn-sec btn-mini' href='/admin/orcamentos/anexo/{a['id']}?visualizar=1' target='_blank'>Visualizar</a> "
        f"<a class='btn btn-mini' href='/admin/orcamentos/anexo/{a['id']}'>Baixar</a></div>" for a in anexos
    ) or "<p class='muted'>Nenhum arquivo anexado.</p>"
    valor=f"R$ {o['valor']:.2f}" if o['valor'] is not None else 'Não informado'
    empresa_link=f"<a class='btn btn-sec' href='/admin/empresas/{o['empresa_id']}'>Abrir ficha do cliente</a>" if o['empresa_id'] else ''
    conteudo=f"""
    <div class='acoes'><a class='btn btn-sec' href='/admin/orcamentos'>← Voltar aos orçamentos</a>{empresa_link}</div>
    <h1>Orçamento #{o['id']}</h1>
      <p><a class='btn' href='#responder-email'>✉ Responder cliente por e-mail</a></p><p class='muted'>{escape(str(o['servico']))} • {escape(str(o['criado_em']))}</p>
    <section class='bloco detalhe-grid'>
      <div><strong>Cliente</strong><br>{escape(str(o['nome'] or '-'))}</div><div><strong>Empresa</strong><br>{escape(str(o['empresa'] or '-'))}</div>
      <div><strong>Tipo</strong><br>{escape(str(o['tipo_cliente'] or '-'))}</div><div><strong>CPF/CNPJ</strong><br>{escape(str(o['documento'] or '-'))}</div>
      <div><strong>E-mail</strong><br>{escape(str(o['email'] or '-'))}</div><div><strong>Telefone</strong><br>{escape(str(o['telefone'] or '-'))}</div>
      <div><strong>Cidade</strong><br>{escape(str(o['cidade'] or '-'))}</div><div><strong>Status / Valor</strong><br>{escape(str(o['status']))} • {valor}</div>
    </section>
    <section class='bloco'><h2>Descrição da solicitação</h2><div class='descricao'>{escape(str(o['mensagem'] or '-'))}</div></section>
    <section class='bloco'><h2>Documentos vinculados</h2>{arquivos}
      <form method='post' action='/admin/orcamentos/{o['id']}/anexar' enctype='multipart/form-data' class='form-anexo'>
        <label class='btn btn-anexo'>📎 Anexar novo arquivo<input type='file' name='arquivo' accept='.pdf,.docx,.ppt,.pptx' required hidden></label>
        <button class='btn' type='submit'>Enviar arquivo</button>
      </form>
    </section>
    <section class='bloco' id='responder-email'>
      <h2>✉ Responder ao cliente por e-mail</h2>
      <p class='muted'>A resposta será enviada para {escape(str(o['email'] or '-'))}. Você também pode anexar PDF, DOCX ou PowerPoint.</p>
      <form method='post' action='/admin/orcamentos/{o['id']}/responder' enctype='multipart/form-data'>
        <textarea class='campo' name='resposta' rows='7' required placeholder='Digite aqui a resposta comercial, orientações, proposta ou retorno ao cliente...'></textarea>
        <input class='campo' type='file' name='arquivo_resposta' accept='.pdf,.docx,.ppt,.pptx'>
        <button class='btn' type='submit'>✉ Enviar resposta por e-mail</button>
      </form>
    </section>"""
    return admin_shell(f'Orçamento #{orcamento_id}',conteudo)



# ----------------------------------------------------------------------
# ----------- [ADMIN: RESPONDER ORÇAMENTO POR E-MAIL] ------------------
# ----------------------------------------------------------------------
@app.route('/admin/orcamentos/<int:orcamento_id>/responder', methods=['POST'])
@login_obrigatorio
def responder_orcamento_email(orcamento_id):
    resposta = request.form.get('resposta', '').strip()
    arquivo = request.files.get('arquivo_resposta')

    if not resposta:
        flash('Digite a resposta que será enviada ao cliente.')
        return redirect(url_for('admin_orcamento_detalhe', orcamento_id=orcamento_id))

    if arquivo and arquivo.filename and not arquivo_permitido(arquivo.filename):
        flash('Formato não permitido. Use PDF, DOCX, PPT ou PPTX.')
        return redirect(url_for('admin_orcamento_detalhe', orcamento_id=orcamento_id))

    with conectar_banco() as c:
        o = c.execute('SELECT * FROM orcamentos WHERE id=?', (orcamento_id,)).fetchone()
    if not o:
        abort(404)

    caminho_resposta = None
    nome_resposta = None
    if arquivo and arquivo.filename:
        nome_resposta = secure_filename(arquivo.filename)
        extensao = nome_resposta.rsplit('.', 1)[1].lower()
        nome_salvo = f"resposta_{orcamento_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{extensao}"
        caminho_resposta = PASTA_ANEXOS / nome_salvo
        arquivo.save(caminho_resposta)
        with conectar_banco() as c:
            c.execute(
                'INSERT INTO anexos_orcamentos (orcamento_id,nome_original,nome_salvo,criado_em) VALUES (?,?,?,?)',
                (orcamento_id, "RESPOSTA - " + nome_resposta, nome_salvo, datetime.now().strftime('%d/%m/%Y %H:%M'))
            )

    enviado, detalhe_envio = enviar_resposta_cliente(
        o['email'], o['nome'], o['id'], o['servico'], resposta,
        caminho_anexo=caminho_resposta, nome_anexo=nome_resposta
    )

    if enviado:
        with conectar_banco() as c:
            c.execute("UPDATE orcamentos SET status='Respondido' WHERE id=?", (orcamento_id,))
        registrar_atividade(f'Resposta por e-mail enviada ao orçamento #{orcamento_id} para {o["email"]}')
        flash('Resposta enviada ao e-mail do cliente e orçamento marcado como Respondido.')
    else:
        flash('A resposta não foi enviada. ' + detalhe_envio)

    return redirect(url_for('admin_orcamento_detalhe', orcamento_id=orcamento_id))


@app.route('/admin/projetos', methods=['GET','POST'])
@login_obrigatorio
def admin_projetos():
    if request.method=='POST':
        titulo=request.form.get('titulo','').strip(); empresa=request.form.get('empresa','').strip(); servico=request.form.get('servico','').strip(); valor=request.form.get('valor') or None
        with conectar_banco() as c: c.execute('INSERT INTO projetos (titulo,empresa,servico,valor,criado_em) VALUES (?,?,?,?,?)',(titulo,empresa,servico,valor,datetime.now().strftime('%d/%m/%Y %H:%M')))
        registrar_atividade(f'Projeto criado: {titulo}'); flash('Projeto cadastrado.'); return redirect(url_for('admin_projetos'))
    with conectar_banco() as c: itens=c.execute('SELECT * FROM projetos ORDER BY id DESC').fetchall()
    linhas=''.join(f"<tr><td>{r['titulo']}</td><td>{r['empresa'] or '-'}</td><td>{r['servico'] or '-'}</td><td>{r['status']}</td><td>{('R$ %.2f'%r['valor']) if r['valor'] else '-'}</td></tr>" for r in itens)
    form="<div class='form-card'><h2>Novo projeto</h2><form method='post'><input class='campo' name='titulo' placeholder='Nome do projeto' required><input class='campo' name='empresa' placeholder='Empresa'><input class='campo' name='servico' placeholder='Serviço'><input class='campo' name='valor' type='number' step='0.01' placeholder='Valor R$'><button class='btn'>Cadastrar</button></form></div>"
    return admin_shell('Projetos',f"<h1>Projetos e Pedidos</h1>{form}<h2 style='margin-top:25px'>Projetos</h2><table class='tabela'><tr><th>Projeto</th><th>Empresa</th><th>Serviço</th><th>Status</th><th>Valor</th></tr>{linhas or '<tr><td colspan=5>Nenhum projeto.</td></tr>'}</table>")

# ----------------------------------------------------------------------
# -------- [ADMIN: CONTEÚDO DAS ÁREAS DO SITE] -------------------------
# ----------------------------------------------------------------------
@app.route('/admin/areas', methods=['GET','POST'])
@login_obrigatorio
def admin_areas():
    from html import escape
    campos = []
    for slug in ("industria", "educacao", "treinamentos", "laboratorio"):
        for sufixo in ("titulo", "subtitulo", "texto", "aplicacoes"):
            campos.append(f"{slug}_{sufixo}")

    if request.method == 'POST':
        for chave in campos:
            salvar_config_site(chave, request.form.get(chave, '').strip())
        registrar_atividade('Conteúdo das áreas do site atualizado')
        flash('Conteúdo das áreas atualizado com sucesso.')
        return redirect(url_for('admin_areas'))

    blocos = []
    nomes = {"industria":"Indústria", "educacao":"Educação", "treinamentos":"Treinamentos", "laboratorio":"Laboratório"}
    for slug, nome in nomes.items():
        titulo = escape(obter_config_site(f'{slug}_titulo', ''))
        subtitulo = escape(obter_config_site(f'{slug}_subtitulo', ''))
        corpo = escape(obter_config_site(f'{slug}_texto', ''))
        aplicacoes = escape(obter_config_site(f'{slug}_aplicacoes', ''))
        blocos.append(f"""
        <section class='form-card'>
          <h2>{nome}</h2>
          <label>Título</label><input class='campo' name='{slug}_titulo' value='{titulo}'>
          <label>Subtítulo</label><textarea class='campo' name='{slug}_subtitulo' rows='2'>{subtitulo}</textarea>
          <label>Apresentação</label><textarea class='campo' name='{slug}_texto' rows='5'>{corpo}</textarea>
          <label>Aplicações <small class='muted'>(uma por linha)</small></label><textarea class='campo' name='{slug}_aplicacoes' rows='7'>{aplicacoes}</textarea>
          <a class='btn btn-sec' href='/{slug}' target='_blank' rel='noopener noreferrer'>Visualizar página</a>
        </section>""")
    conteudo = "<h1>Conteúdo das Áreas</h1><p class='muted'>Edite onde a tecnologia da CNB Tech Solution se aplica. As páginas usam automaticamente a paleta ativa do site.</p><form method='post'>" + ''.join(blocos) + "<button class='btn' style='margin-top:18px'>Salvar todas as áreas</button></form>"
    return admin_shell('Conteúdo das Áreas', conteudo)


# ----------------------------------------------------------------------
# -------- [ADMIN: EQUIPE / QUEM SOMOS] --------------------------------
# ----------------------------------------------------------------------
# Nesta área o administrador pode:
#   - adicionar integrante;
#   - enviar ou trocar a foto;
#   - editar nome, cargo e descrição;
#   - definir a ordem dos cards;
#   - publicar/despublicar;
#   - excluir integrante.
# ----------------------------------------------------------------------
@app.route('/admin/equipe', methods=['GET','POST'])
@login_obrigatorio
def admin_equipe():
    from html import escape

    # --------------------------------------------------------------
    # [POST] CADASTRAR NOVO INTEGRANTE
    # --------------------------------------------------------------
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        cargo = request.form.get('cargo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        publicado = 1 if request.form.get('publicado') else 0

        try:
            ordem = int(request.form.get('ordem', '0') or 0)
        except ValueError:
            ordem = 0

        foto_upload = request.files.get('foto')
        foto_recortada = request.form.get('foto_recortada', '').strip()

        # [V20] Prioriza o recorte confirmado no Canvas; se não houver,
        # mantém compatibilidade com o upload normal da V19.
        foto = salvar_imagem_recortada_base64(
            foto_recortada, PASTA_EQUIPE, 'equipe'
        ) if foto_recortada else (
            salvar_midia_publica(
                foto_upload,
                PASTA_EQUIPE,
                EXTENSOES_IMAGEM_PUBLICA,
                'equipe'
            )
            if foto_upload and foto_upload.filename else ''
        )

        if not nome:
            flash('Informe o nome do integrante.')
            return redirect(url_for('admin_equipe'))

        if not cargo:
            flash('Informe o cargo ou função do integrante.')
            return redirect(url_for('admin_equipe'))

        if (foto_recortada or (foto_upload and foto_upload.filename)) and not foto:
            flash('Não foi possível processar a foto. Tente selecionar e enquadrar novamente.')
            return redirect(url_for('admin_equipe'))

        with conectar_banco() as c:
            c.execute(
                """INSERT INTO equipe_empresa
                   (nome,cargo,descricao,foto,ordem,publicado,criado_em)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    nome,
                    cargo,
                    descricao,
                    foto,
                    ordem,
                    publicado,
                    datetime.now().strftime('%d/%m/%Y %H:%M')
                )
            )

        registrar_atividade(f'Integrante adicionado à equipe: {nome}')
        flash('Integrante adicionado à seção Nossa Equipe.')
        return redirect(url_for('admin_equipe'))

    # --------------------------------------------------------------
    # [GET] LISTAR INTEGRANTES
    # --------------------------------------------------------------
    with conectar_banco() as c:
        itens = c.execute(
            'SELECT * FROM equipe_empresa ORDER BY ordem ASC, id ASC'
        ).fetchall()

    linhas = ''.join(
        f"""
        <tr>
            <td>{escape(r['nome'])}</td>
            <td>{escape(r['cargo'])}</td>
            <td>{r['ordem']}</td>
            <td>{'Sim' if r['publicado'] else 'Não'}</td>
            <td>{'Sim' if r['foto'] else 'Não'}</td>
            <td>
                <div style='display:flex;gap:7px;flex-wrap:wrap'>
                    <a class='btn btn-sec btn-mini' href='/admin/equipe/{r["id"]}/editar'>Editar</a>
                    <form method='post' action='/admin/equipe/{r["id"]}/excluir'
                          onsubmit="return confirm('Excluir este integrante?')">
                        <button class='btn btn-sec btn-mini' type='submit'>Excluir</button>
                    </form>
                </div>
            </td>
        </tr>
        """
        for r in itens
    ) or "<tr><td colspan='6'>Nenhum integrante cadastrado.</td></tr>"

    recorte_novo_integrante = html_recorte_imagem(
        input_name='foto',
        input_id='foto_equipe_nova',
        hidden_name='foto_recortada',
        bloco_id='crop_equipe_nova',
        titulo='Foto do integrante',
        proporcao_largura=4,
        proporcao_altura=3,
    )

    form = f"""
    <div class='form-card'>
        <h2>Novo integrante</h2>
        <form method='post' enctype='multipart/form-data'>
            <label>Nome</label>
            <input class='campo' name='nome' required placeholder='Nome do integrante'>

            <label>Cargo / função</label>
            <input class='campo' name='cargo' required placeholder='Ex.: Diretor de Tecnologia'>

            <label>Descrição</label>
            <textarea class='campo' name='descricao' rows='4'
                      placeholder='Breve apresentação, experiência ou função na empresa.'></textarea>

            {recorte_novo_integrante}

            <label>Ordem do card</label>
            <input class='campo' type='number' name='ordem' value='0' step='1'>
            <p class='nota-admin'>Números menores aparecem primeiro na página Empresa.</p>

            <label class='switch-admin'>
                <input type='checkbox' name='publicado' value='1' checked>
                Publicado no site
            </label>

            <button class='btn' type='submit'>Adicionar integrante</button>
        </form>
    </div>
    """

    conteudo = f"""
    <h1>Equipe / Quem Somos</h1>
    <p class='muted'>Gerencie os cards dos integrantes exibidos na página Empresa.</p>
    {form}
    <h2 style='margin-top:26px'>Integrantes cadastrados</h2>
    <table class='tabela'>
        <tr>
            <th>Nome</th>
            <th>Cargo</th>
            <th>Ordem</th>
            <th>Publicado</th>
            <th>Foto</th>
            <th>Ações</th>
        </tr>
        {linhas}
    </table>
    """

    return admin_shell('Equipe / Quem Somos', conteudo)


@app.route('/admin/equipe/<int:membro_id>/editar', methods=['GET','POST'])
@login_obrigatorio
def admin_equipe_editar(membro_id):
    from html import escape

    with conectar_banco() as c:
        membro = c.execute(
            'SELECT * FROM equipe_empresa WHERE id=?',
            (membro_id,)
        ).fetchone()

    if membro is None:
        abort(404)

    # --------------------------------------------------------------
    # [POST] SALVAR ALTERAÇÕES DO INTEGRANTE
    # --------------------------------------------------------------
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        cargo = request.form.get('cargo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        publicado = 1 if request.form.get('publicado') else 0
        remover_foto = bool(request.form.get('remover_foto'))

        try:
            ordem = int(request.form.get('ordem', '0') or 0)
        except ValueError:
            ordem = 0

        if not nome or not cargo:
            flash('Nome e cargo são obrigatórios.')
            return redirect(url_for('admin_equipe_editar', membro_id=membro_id))

        foto_antiga = membro['foto'] or ''
        foto_final = foto_antiga
        foto_upload = request.files.get('foto')
        foto_recortada = request.form.get('foto_recortada', '').strip()

        # [ADMIN] REMOVER FOTO ATUAL
        if remover_foto and foto_antiga:
            apagar_midia_publica(PASTA_EQUIPE, foto_antiga)
            foto_final = ''

        # [ADMIN / V20] TROCAR FOTO COM RECORTE OPCIONAL
        if foto_recortada or (foto_upload and foto_upload.filename):
            nova_foto = salvar_imagem_recortada_base64(
                foto_recortada, PASTA_EQUIPE, 'equipe'
            ) if foto_recortada else salvar_midia_publica(
                foto_upload,
                PASTA_EQUIPE,
                EXTENSOES_IMAGEM_PUBLICA,
                'equipe'
            )
            if not nova_foto:
                flash('Não foi possível processar a nova foto.')
                return redirect(url_for('admin_equipe_editar', membro_id=membro_id))

            if foto_antiga and foto_antiga != foto_final:
                pass
            elif foto_antiga:
                apagar_midia_publica(PASTA_EQUIPE, foto_antiga)

            foto_final = nova_foto

        with conectar_banco() as c:
            c.execute(
                """UPDATE equipe_empresa
                   SET nome=?, cargo=?, descricao=?, foto=?, ordem=?, publicado=?
                   WHERE id=?""",
                (nome, cargo, descricao, foto_final, ordem, publicado, membro_id)
            )

        registrar_atividade(f'Integrante da equipe atualizado: {nome}')
        flash('Integrante atualizado com sucesso.')
        return redirect(url_for('admin_equipe'))

    foto_preview = (
        f"<img src='/midia-equipe/{escape(membro['foto'])}' "
        f"alt='{escape(membro['nome'])}' "
        "style='width:180px;max-width:100%;aspect-ratio:4/3;object-fit:cover;"
        "border-radius:12px;border:1px solid var(--admin-border);margin-bottom:12px'>"
        if membro['foto']
        else "<div class='muted' style='margin-bottom:12px'>Este integrante ainda não possui foto.</div>"
    )

    checked = 'checked' if membro['publicado'] else ''

    recorte_edicao_integrante = html_recorte_imagem(
        input_name='foto',
        input_id='foto_equipe_editar',
        hidden_name='foto_recortada',
        bloco_id='crop_equipe_editar',
        titulo='Trocar e enquadrar foto',
        proporcao_largura=4,
        proporcao_altura=3,
    )

    conteudo = f"""
    <h1>Editar integrante</h1>
    <p class='muted'>Atualize foto, nome, cargo, descrição, ordem e publicação.</p>

    <div class='form-card'>
        {foto_preview}

        <form method='post' enctype='multipart/form-data'>
            <label>Nome</label>
            <input class='campo' name='nome' required value='{escape(membro["nome"])}'>

            <label>Cargo / função</label>
            <input class='campo' name='cargo' required value='{escape(membro["cargo"])}'>

            <label>Descrição</label>
            <textarea class='campo' name='descricao' rows='5'>{escape(membro["descricao"] or "")}</textarea>

            {recorte_edicao_integrante}

            <label class='switch-admin'>
                <input type='checkbox' name='remover_foto' value='1'>
                Remover foto atual
            </label>

            <label>Ordem do card</label>
            <input class='campo' type='number' name='ordem'
                   value='{membro["ordem"]}' step='1'>

            <label class='switch-admin'>
                <input type='checkbox' name='publicado' value='1' {checked}>
                Publicado no site
            </label>

            <div style='display:flex;gap:10px;flex-wrap:wrap'>
                <button class='btn' type='submit'>Salvar alterações</button>
                <a class='btn btn-sec' href='/admin/equipe'>Cancelar</a>
                <a class='btn btn-sec' href='/empresa#nossa-equipe'
                   target='_blank' rel='noopener noreferrer'>Ver no site</a>
            </div>
        </form>
    </div>
    """

    return admin_shell('Editar integrante', conteudo)


@app.route('/admin/equipe/<int:membro_id>/excluir', methods=['POST'])
@login_obrigatorio
def admin_equipe_excluir(membro_id):
    with conectar_banco() as c:
        membro = c.execute(
            'SELECT * FROM equipe_empresa WHERE id=?',
            (membro_id,)
        ).fetchone()

        if membro:
            c.execute(
                'DELETE FROM equipe_empresa WHERE id=?',
                (membro_id,)
            )

    if membro:
        apagar_midia_publica(PASTA_EQUIPE, membro['foto'])
        registrar_atividade(f'Integrante removido da equipe: {membro["nome"]}')

    flash('Integrante removido da seção Nossa Equipe.')
    return redirect(url_for('admin_equipe'))


# ----------------------------------------------------------------------
# -------- [ADMIN: PROJETOS & GALERIA] ---------------------------------
# ----------------------------------------------------------------------
@app.route('/admin/galeria', methods=['GET','POST'])
@login_obrigatorio
def admin_galeria():
    from html import escape
    if request.method == 'POST':
        titulo = request.form.get('titulo','').strip()
        descricao = request.form.get('descricao','').strip()
        categoria = request.form.get('categoria','').strip()
        cliente = request.form.get('cliente_origem','').strip()
        tipo = request.form.get('tipo_midia','imagem')
        tipo = tipo if tipo in {'imagem','video'} else 'imagem'
        url_externa = normalizar_url_externa(request.form.get('url_externa',''))
        destaque = 1 if request.form.get('destaque') else 0
        publicado = 1 if request.form.get('publicado') else 0
        arquivo = request.files.get('arquivo')
        arquivo_recortado = request.form.get('arquivo_recortado', '').strip()
        permitidas = EXTENSOES_VIDEO_PUBLICO if tipo == 'video' else EXTENSOES_IMAGEM_PUBLICA

        # [V20] Imagem da galeria pode ser enquadrada em 16:9.
        # Vídeos continuam seguindo o upload normal.
        if tipo == 'imagem' and arquivo_recortado:
            nome_arquivo = salvar_imagem_recortada_base64(
                arquivo_recortado, PASTA_GALERIA, 'galeria'
            )
        else:
            nome_arquivo = salvar_midia_publica(
                arquivo, PASTA_GALERIA, permitidas, 'galeria'
            ) if arquivo and arquivo.filename else ''
        if not titulo:
            flash('Informe o título do item da galeria.')
            return redirect(url_for('admin_galeria'))
        if arquivo and arquivo.filename and not nome_arquivo:
            flash('Formato de arquivo não permitido para o tipo selecionado.')
            return redirect(url_for('admin_galeria'))
        with conectar_banco() as c:
            c.execute("INSERT INTO galeria_publica (titulo,descricao,categoria,cliente_origem,tipo_midia,arquivo,url_externa,destaque,publicado,criado_em) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (titulo,descricao,categoria,cliente,tipo,nome_arquivo,url_externa,destaque,publicado,datetime.now().strftime('%d/%m/%Y %H:%M')))
        registrar_atividade(f'Item publicado na galeria: {titulo}')
        flash('Item adicionado à galeria.')
        return redirect(url_for('admin_galeria'))

    with conectar_banco() as c:
        itens = c.execute('SELECT * FROM galeria_publica ORDER BY id DESC').fetchall()
    linhas = ''.join(
        f"<tr><td>{escape(r['titulo'])}</td><td>{escape(r['categoria'] or '-')}</td><td>{escape(r['tipo_midia'])}</td><td>{'Sim' if r['publicado'] else 'Não'}</td><td>{'Sim' if r['destaque'] else 'Não'}</td><td><form method='post' action='/admin/galeria/{r['id']}/excluir' onsubmit=\"return confirm('Excluir este item?')\"><button class='btn btn-sec btn-mini'>Excluir</button></form></td></tr>" for r in itens
    ) or "<tr><td colspan='6'>Nenhum item cadastrado.</td></tr>"
    recorte_galeria = html_recorte_imagem(
        input_name='arquivo',
        input_id='arquivo_galeria',
        hidden_name='arquivo_recortado',
        bloco_id='crop_galeria',
        titulo='Arquivo da galeria',
        proporcao_largura=16,
        proporcao_altura=9,
        aceitar_video=True,
    )

    form = f"""
    <div class='form-card'><h2>Novo item da galeria</h2><form method='post' enctype='multipart/form-data'>
    <label>Título</label><input class='campo' name='titulo' required>
    <label>Descrição</label><textarea class='campo' name='descricao' rows='4'></textarea>
    <label>Categoria</label><input class='campo' name='categoria' placeholder='Ex.: Infraestrutura, Audiovisual, Projeto'>
    <label>Cliente / origem</label><input class='campo' name='cliente_origem' placeholder='Nome do cliente ou CNB Tech Solution'>
    <label>Tipo de mídia</label><select class='campo' name='tipo_midia'><option value='imagem'>Imagem</option><option value='video'>Vídeo</option></select>
    {recorte_galeria}
    <label>Link externo opcional</label><input class='campo' type='url' name='url_externa' placeholder='https://...'>
    <label class='switch-admin'><input type='checkbox' name='destaque' value='1'> Destacar na Home</label>
    <label class='switch-admin'><input type='checkbox' name='publicado' value='1' checked> Publicado</label>
    <button class='btn'>Adicionar à galeria</button></form></div>"""
    conteudo = f"<h1>Projetos & Galeria</h1><p class='muted'>Publique fotos e vídeos de clientes, projetos e atividades da CNB Tech Solution.</p>{form}<h2 style='margin-top:26px'>Itens cadastrados</h2><table class='tabela'><tr><th>Título</th><th>Categoria</th><th>Tipo</th><th>Publicado</th><th>Destaque</th><th>Ação</th></tr>{linhas}</table>"
    return admin_shell('Galeria', conteudo)

@app.route('/admin/galeria/<int:item_id>/excluir', methods=['POST'])
@login_obrigatorio
def admin_galeria_excluir(item_id):
    with conectar_banco() as c:
        item = c.execute('SELECT * FROM galeria_publica WHERE id=?',(item_id,)).fetchone()
        if item:
            c.execute('DELETE FROM galeria_publica WHERE id=?',(item_id,))
    if item:
        apagar_midia_publica(PASTA_GALERIA, item['arquivo'])
        registrar_atividade(f'Item excluído da galeria: {item["titulo"]}')
    flash('Item removido da galeria.')
    return redirect(url_for('admin_galeria'))


# ----------------------------------------------------------------------
# -------- [ADMIN: NOTÍCIAS E LINKS EXTERNOS] --------------------------
# ----------------------------------------------------------------------
@app.route('/admin/noticias', methods=['GET','POST'])
@login_obrigatorio
def admin_noticias():
    from html import escape
    if request.method == 'POST':
        titulo = request.form.get('titulo','').strip()
        resumo = request.form.get('resumo','').strip()
        conteudo_noticia = request.form.get('conteudo','').strip()
        categoria = request.form.get('categoria','').strip()
        link_externo_original = request.form.get('link_externo','').strip()
        link_externo = normalizar_url_externa(link_externo_original)
        destaque = 1 if request.form.get('destaque') else 0
        publicado = 1 if request.form.get('publicado') else 0
        imagem_upload = request.files.get('imagem')
        imagem_recortada = request.form.get('imagem_recortada', '').strip()
        imagem = salvar_imagem_recortada_base64(
            imagem_recortada, PASTA_NOTICIAS, 'noticia'
        ) if imagem_recortada else (
            salvar_midia_publica(
                imagem_upload, PASTA_NOTICIAS, EXTENSOES_IMAGEM_PUBLICA, 'noticia'
            ) if imagem_upload and imagem_upload.filename else ''
        )
        if not titulo:
            flash('Informe o título da notícia.')
            return redirect(url_for('admin_noticias'))
        if link_externo_original and not link_externo:
            flash('O link externo deve começar com http:// ou https://.')
            return redirect(url_for('admin_noticias'))
        if imagem_upload and imagem_upload.filename and not imagem:
            flash('Formato da imagem de capa não permitido.')
            return redirect(url_for('admin_noticias'))
        with conectar_banco() as c:
            c.execute("INSERT INTO noticias (titulo,resumo,conteudo,categoria,imagem,link_externo,destaque,publicado,criado_em) VALUES (?,?,?,?,?,?,?,?,?)",
                      (titulo,resumo,conteudo_noticia,categoria,imagem,link_externo,destaque,publicado,datetime.now().strftime('%d/%m/%Y %H:%M')))
        registrar_atividade(f'Notícia cadastrada: {titulo}')
        flash('Notícia cadastrada com sucesso.')
        return redirect(url_for('admin_noticias'))

    with conectar_banco() as c:
        itens = c.execute('SELECT * FROM noticias ORDER BY id DESC').fetchall()
    linhas = ''.join(
        f"<tr><td>{escape(r['titulo'])}</td><td>{escape(r['categoria'] or '-')}</td><td>{'Externo' if r['link_externo'] else 'Interno'}</td><td>{'Sim' if r['publicado'] else 'Não'}</td><td>{'Sim' if r['destaque'] else 'Não'}</td><td><form method='post' action='/admin/noticias/{r['id']}/excluir' onsubmit=\"return confirm('Excluir esta notícia?')\"><button class='btn btn-sec btn-mini'>Excluir</button></form></td></tr>" for r in itens
    ) or "<tr><td colspan='6'>Nenhuma notícia cadastrada.</td></tr>"
    recorte_noticia = html_recorte_imagem(
        input_name='imagem',
        input_id='imagem_noticia',
        hidden_name='imagem_recortada',
        bloco_id='crop_noticia',
        titulo='Imagem de capa',
        proporcao_largura=16,
        proporcao_altura=9,
    )

    form = f"""
    <div class='form-card'><h2>Nova notícia</h2><form method='post' enctype='multipart/form-data'>
    <label>Título</label><input class='campo' name='titulo' required>
    <label>Resumo para o card</label><textarea class='campo' name='resumo' rows='3'></textarea>
    <label>Conteúdo interno <small class='muted'>(usado quando não houver link externo)</small></label><textarea class='campo' name='conteudo' rows='8'></textarea>
    <label>Categoria</label><input class='campo' name='categoria' placeholder='Ex.: Tecnologia, Redes, Educação'>
    {recorte_noticia}
    <label>Link externo opcional</label><input class='campo' type='url' name='link_externo' placeholder='https://site-da-noticia.com/...'>
    <p class='nota-admin'>Se o link externo for preenchido, o visitante será levado diretamente para a fonte ao clicar no card.</p>
    <label class='switch-admin'><input type='checkbox' name='destaque' value='1'> Destacar na Home</label>
    <label class='switch-admin'><input type='checkbox' name='publicado' value='1' checked> Publicado</label>
    <button class='btn'>Publicar notícia</button></form></div>"""
    conteudo = f"<h1>Notícias</h1><p class='muted'>Cadastre notícias próprias ou links externos sobre tecnologia. Os itens publicados aparecem na página Notícias e os mais recentes na Home.</p>{form}<h2 style='margin-top:26px'>Notícias cadastradas</h2><table class='tabela'><tr><th>Título</th><th>Categoria</th><th>Destino</th><th>Publicado</th><th>Destaque</th><th>Ação</th></tr>{linhas}</table>"
    return admin_shell('Notícias', conteudo)

@app.route('/admin/noticias/<int:noticia_id>/excluir', methods=['POST'])
@login_obrigatorio
def admin_noticia_excluir(noticia_id):
    with conectar_banco() as c:
        item = c.execute('SELECT * FROM noticias WHERE id=?',(noticia_id,)).fetchone()
        if item:
            c.execute('DELETE FROM noticias WHERE id=?',(noticia_id,))
    if item:
        apagar_midia_publica(PASTA_NOTICIAS, item['imagem'])
        registrar_atividade(f'Notícia excluída: {item["titulo"]}')
    flash('Notícia removida.')
    return redirect(url_for('admin_noticias'))


@app.route('/admin/administradores', methods=['GET','POST'])
@login_obrigatorio
def admin_administradores():
    if session.get('admin_perfil')!='master': return admin_shell('Administradores',"<h1>Acesso restrito</h1><p>Somente o Administrador Master pode gerenciar administradores.</p>")
    if request.method=='POST':
        nome=request.form.get('nome','').strip(); email=request.form.get('email','').strip().lower(); senha=request.form.get('senha',''); perfil=request.form.get('perfil','administrador')
        try:
            with conectar_banco() as c: c.execute('INSERT INTO administradores (nome,email,senha_hash,perfil,ativo,criado_em) VALUES (?,?,?,?,1,?)',(nome,email,generate_password_hash(senha),perfil,datetime.now().strftime('%d/%m/%Y %H:%M')))
            registrar_atividade(f'Administrador criado: {email}'); flash('Administrador criado.')
        except sqlite3.IntegrityError: flash('Esse e-mail já está cadastrado.')
        return redirect(url_for('admin_administradores'))
    with conectar_banco() as c: itens=c.execute('SELECT id,nome,email,perfil,ativo,criado_em FROM administradores ORDER BY id').fetchall()
    linhas=''.join(f"<tr><td>{r['nome']}</td><td>{r['email']}</td><td>{r['perfil']}</td><td>{'Ativo' if r['ativo'] else 'Inativo'}</td><td>{r['criado_em']}</td></tr>" for r in itens)
    form="<div class='form-card'><h2>Novo administrador</h2><form method='post'><input class='campo' name='nome' placeholder='Nome' required><input class='campo' type='email' name='email' placeholder='E-mail' required><input class='campo' type='password' name='senha' placeholder='Senha' required><select class='campo' name='perfil'><option value='administrador'>Administrador</option><option value='comercial'>Comercial</option><option value='financeiro'>Financeiro</option></select><button class='btn'>Criar administrador</button></form></div>"
    return admin_shell('Administradores',f"<h1>Administradores</h1>{form}<h2 style='margin-top:25px'>Usuários administrativos</h2><table class='tabela'><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Status</th><th>Criado em</th></tr>{linhas}</table>")

# ----------------------------------------------------------------------
# --------------- [FIM: PAINEL ADMINISTRATIVO CNB TECH] ----------------
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# ------------ [PYTHON: ABRIR NAVEGADOR AUTOMATICAMENTE] --------------
# ----------------------------------------------------------------------
def abrir_navegador(porta):
    webbrowser.open(f"http://127.0.0.1:{porta}")


# ----------------------------------------------------------------------
# ---------------- [PYTHON: EXECUÇÃO DO SERVIDOR] ----------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # [V20 / EXECUÇÃO LOCAL]
    # O Render usa Gunicorn e importa app:app; localmente este bloco permite F5/IDLE.
    iniciar_banco()

    IP_LOCAL = os.environ.get("HOST", "127.0.0.1")
    PORTA_ACESSO = int(os.environ.get("PORT", "5000"))
    DEBUG_LOCAL = os.environ.get("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    ABRIR_NAVEGADOR = os.environ.get("ABRIR_NAVEGADOR", "1").strip().lower() not in {"0", "false", "no", "off"}

    if ABRIR_NAVEGADOR and IP_LOCAL in {"127.0.0.1", "localhost"}:
        Timer(1.5, abrir_navegador, args=[PORTA_ACESSO]).start()

    print(f"\n[+] Servidor iniciado com sucesso!")

    if VIDEO_HOME_ARQUIVO.exists():
        tamanho_mb = VIDEO_HOME_ARQUIVO.stat().st_size / (1024 * 1024)
        print(f"[+] Vídeo da Home encontrado: {VIDEO_HOME_NOME} ({tamanho_mb:.1f} MB)")
        print(f"[+] Teste direto do vídeo: http://{IP_LOCAL}:{PORTA_ACESSO}/video-home")
    else:
        print(f"[!] ATENÇÃO: coloque {VIDEO_HOME_NOME} na mesma pasta deste arquivo Python.")

    print(f"[+] Editar Site 2.0: http://{IP_LOCAL}:{PORTA_ACESSO}/admin/editar-site")
    print(f"[+] Contatos & Redes: http://{IP_LOCAL}:{PORTA_ACESSO}/admin/contatos-redes")
    print(f"[+] Acesse a Home Page: http://{IP_LOCAL}:{PORTA_ACESSO}/")
    print(f"[+] Acesse direto a Empresa: http://{IP_LOCAL}:{PORTA_ACESSO}/empresa")
    print(f"[+] Projetos & Galeria: http://{IP_LOCAL}:{PORTA_ACESSO}/galeria")
    print(f"[+] Notícias: http://{IP_LOCAL}:{PORTA_ACESSO}/noticias\n")

    app.run(host=IP_LOCAL, port=PORTA_ACESSO, debug=DEBUG_LOCAL, use_reloader=False)
