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
import smtplib
from email.message import EmailMessage

# 1. Inicializa o servidor web Flask
app = Flask(__name__)
app.secret_key = "troque-esta-chave-secreta-cnb-tech"

# Banco local SQLite: criado automaticamente na primeira execução
BASE_DIR = Path(__file__).resolve().parent
BANCO_DADOS = BASE_DIR / "cnb_tech_solution.db"

# ----------------------------------------------------------------------
# -------- [VÍDEO DA HOME: ARQUIVO JUNTO COM O PYTHON] -----------------
# ----------------------------------------------------------------------
# Para evitar falhas de caminho no IDLE, o MP4 fica na MESMA pasta
# deste arquivo Python. O Flask entrega o vídeo pela rota /video-home.
VIDEO_HOME_NOME = "cnb-tech-home.mp4"
VIDEO_HOME_ARQUIVO = BASE_DIR / VIDEO_HOME_NOME

# ----------------------------------------------------------------------
# ---- [V18: LOGO CNB TECH SOLUTION TRANSPARENTE EM ARQUIVO EXTERNO] ---
# ----------------------------------------------------------------------
# Esta versão mantém a BASE DA V12, que já roda normalmente no IDLE.
# A única mudança importante é a logo: ela NÃO fica mais em Base64.
# Coloque o PNG transparente abaixo na MESMA pasta deste arquivo Python.
# Isso deixa o .py leve e evita travamentos do editor do IDLE.
LOGO_CNB_NOME = "cnb-tech-logo-transparente.png"
LOGO_CNB_ARQUIVO = BASE_DIR / LOGO_CNB_NOME

# ----------------------------------------------------------------------
# -------- [V19: MÍDIAS EDITÁVEIS PELO PAINEL ADMINISTRATIVO] ---------
# ----------------------------------------------------------------------
# Logo e vídeo atualizados pelo Dashboard ficam nesta pasta.
# O código Python não precisa ser editado quando a identidade visual muda.
PASTA_MIDIA_SITE = BASE_DIR / "midia_site"
PASTA_MIDIA_SITE.mkdir(exist_ok=True)
EXTENSOES_LOGO_SITE = {"png", "webp", "jpg", "jpeg"}
EXTENSOES_VIDEO_SITE = {"mp4"}

# Permite upload de vídeo pelo painel. O limite vale para qualquer POST com arquivo.
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024  # 250 MB

# ----------------------------------------------------------------------
# -------- [ARQUIVOS DOS ORÇAMENTOS: PDF / DOCX / POWERPOINT] ----------
# ----------------------------------------------------------------------
PASTA_ANEXOS = BASE_DIR / "anexos_orcamentos"
PASTA_ANEXOS.mkdir(exist_ok=True)
EXTENSOES_PERMITIDAS = {"pdf", "docx", "ppt", "pptx"}
app.config["MAX_CONTENT_LENGTH"] = 24 * 1024 * 1024  # Limite de 24 MB por envio

def arquivo_permitido(nome_arquivo):
    return "." in nome_arquivo and nome_arquivo.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS

def conectar_banco():
    conexao = sqlite3.connect(BANCO_DADOS)
    conexao.row_factory = sqlite3.Row
    return conexao

def obter_config_site(chave, padrao=""):
    try:
        with conectar_banco() as conexao:
            linha = conexao.execute("SELECT valor FROM site_config WHERE chave=?", (chave,)).fetchone()
            if linha is not None and linha["valor"] is not None:
                return linha["valor"]
    except sqlite3.Error:
        pass
    return padrao

def salvar_config_site(chave, valor):
    with conectar_banco() as conexao:
        conexao.execute(
            "INSERT INTO site_config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor)
        )

def extensao_arquivo(nome):
    return nome.rsplit(".", 1)[1].lower() if "." in nome else ""

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
            "video_arquivo": ""
        }
        for chave, valor in configuracoes_padrao.items():
            conexao.execute("INSERT OR IGNORE INTO site_config (chave, valor) VALUES (?, ?)", (chave, valor))

        existe = conexao.execute("SELECT id FROM administradores LIMIT 1").fetchone()
        if not existe:
            conexao.execute(
                "INSERT INTO administradores (nome,email,senha_hash,perfil,ativo,criado_em) VALUES (?,?,?,?,?,?)",
                ("Administrador Master", "admin@cnbtech.local", generate_password_hash("CNBTech@2026"), "master", 1, datetime.now().strftime("%d/%m/%Y %H:%M"))
            )

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
LAYOUT_EMPRESA_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sobre a {{ nome_empresa }}</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background-color: #f1f5f9;
            color: #1e293b;
            line-height: 1.6;
        }

        /* BARRA SUPERIOR */
        .navbar {
            background: linear-gradient(120deg, #07111f, #0d2238, #07111f);
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 40px;
            color: #ffffff;
            border-bottom: 1px solid rgba(56, 189, 248, 0.20);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
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
            background-color: #38bdf8;
            color: #0f172a;
            text-decoration: none;
            padding: 9px 17px;
            border-radius: 7px;
            font-weight: bold;
            font-size: 0.9rem;
            transition: transform 0.2s ease, background 0.2s ease;
        }

        .btn-voltar:hover {
            background-color: #7dd3fc;
            transform: translateY(-2px);
        }

        /* CONTEÚDO INSTITUCIONAL */
        .container {
            max-width: 950px;
            margin: 55px auto;
            padding: 0 20px;
        }

        .header-secao {
            text-align: center;
            margin-bottom: 42px;
        }

        .header-secao h1 {
            font-size: 2.2rem;
            color: #0f172a;
            margin-bottom: 10px;
        }

        .header-secao p {
            font-size: 1.05rem;
            color: #64748b;
        }

        /* BLOCOS DE INFORMAÇÕES TECH */
        .bloco-info {
            background-color: #ffffff;
            border-radius: 10px;
            padding: 28px;
            margin-bottom: 22px;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #38bdf8;
            box-shadow: 0 5px 18px rgba(15, 23, 42, 0.05);
            transition: transform 0.25s ease, box-shadow 0.25s ease;
        }

        .bloco-info:hover {
            transform: translateY(-3px);
            box-shadow: 0 12px 25px rgba(15, 23, 42, 0.09);
        }

        .bloco-info h2 {
            font-size: 1.3rem;
            color: #0f172a;
            margin-bottom: 12px;
        }

        .bloco-info p {
            color: #475569;
            font-size: 0.98rem;
        }

        .bloco-info ul {
            margin-left: 20px;
            margin-top: 12px;
            color: #475569;
        }

        .bloco-info li {
            margin-bottom: 7px;
        }

        @media (max-width: 600px) {
            .navbar {
                padding: 18px 20px;
            }

            .header-secao h1 {
                font-size: 1.8rem;
            }
        }
    </style>
</head>
<body>

    <!-- Barra de Navegação -->
    <header class="navbar">
        <a href="/" class="logo" aria-label="{{ nome_empresa }} - Página inicial">
            <img src="/logo-cnb?v=12" class="logo-img" alt="{{ nome_empresa }}">
        </a>
        <a href="/" class="btn-voltar">← Voltar ao Início</a>
    </header>

    <!-- Conteúdo Institucional -->
    <main class="container">

        <div class="header-secao">
            <h1>Engenharia & Soluções em Tecnologia</h1>
            <p>Infraestrutura, inovação e soluções digitais integradas para empresas e instituições.</p>
        </div>

        <section class="bloco-info">
            <h2>🏢 Quem Somos</h2>
            <p>A <strong>{{ nome_empresa }}</strong> é uma integradora de soluções digitais especializada em automação, arquitetura de servidores de alta disponibilidade e computação em nuvem. Nascemos com a missão de transformar rotinas industriais e operacionais através de softwares de alto desempenho e telemetria em tempo real.</p>
        </section>

        <section class="bloco-info">
            <h2>⚙️ O Que Fazemos</h2>
            <p>Desenvolvemos ecossistemas tecnológicos integrados para empresas que exigem confiabilidade, desempenho e segurança:</p>
            <ul>
                <li><strong>Monitoramento de Servidores:</strong> Rastreamento contínuo de recursos e diagnósticos de latência.</li>
                <li><strong>Desenvolvimento de Software:</strong> Aplicações web modernas e APIs robustas de backend.</li>
                <li><strong>Laboratório de P&D:</strong> Pesquisa, testes e validação de novas tecnologias.</li>
            </ul>
        </section>

        <section class="bloco-info">
            <h2>🛡️ Políticas da Empresa</h2>
            <p>Nossas diretrizes corporativas são baseadas em segurança, disponibilidade e evolução tecnológica:</p>
            <ul>
                <li><strong>Segurança & Privacidade:</strong> Proteção de sistemas, redes e dados.</li>
                <li><strong>Disponibilidade Contínua:</strong> Infraestrutura resiliente para serviços digitais.</li>
                <li><strong>Inovação Sustentável:</strong> Otimização constante de hardware, software e processamento.</li>
            </ul>
        </section>

    </main>

</body>
</html>
"""

# ----------------------------------------------------------------------
# ------------------ [FIM DA PÁGINA: EMPRESA TECH] ---------------------
# ----------------------------------------------------------------------


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
            background-color: #050c15;
            color: #e2e8f0;
        }

        /* ============================================================ */
        /* 2. BARRA SUPERIOR (NAVBAR)                                 */
        /* ============================================================ */
        .navbar {
            position: relative;
            overflow: hidden;
            min-height: 108px;
            background-color: #071426;
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
            width: 205px;
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
            color: #cbd5e1;
            text-decoration: none;
            font-size: 0.90rem;
            font-weight: 500;
            display: inline-block;
            padding: 8px 0;
            transition: transform 0.25s ease, color 0.25s ease;
        }

        .nav-links a::after {
            content: "";
            position: absolute;
            left: 50%;
            bottom: 0;
            width: 0;
            height: 2px;
            background: #38bdf8;
            transform: translateX(-50%);
            transition: width 0.25s ease;
        }

        .nav-links a:hover {
            transform: translateY(-2px) scale(1.08);
            color: #ffffff;
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
            background: rgba(15, 23, 42, 0.72);
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
            background: #38bdf8;
            border: none;
            color: #07111f;
            font-weight: bold;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
        }

        /* ============================================================ */
        /* 6. ÁREA PRINCIPAL - FUNDO TECNOLÓGICO COM VÍDEO             */
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
            background-color: #050c15;
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
            color: #94a3b8;
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
            color: #f8fafc;
            margin-bottom: 17px;
        }

        .hero-cabecalho h1 span {
            color: #38bdf8;
        }

        .hero-cabecalho p {
            max-width: 680px;
            margin: 0 auto;
            font-size: 1rem;
            line-height: 1.7;
            color: #94a3b8;
        }

        /* 9. GRADE DOS CARTÕES */
        .grid-servicos {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 18px;
        }

        /* 10. CARTÕES DE SERVIÇOS */
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
            border: 1px solid rgba(148, 163, 184, 0.12);
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

        /* 11. ÍCONE DOS SERVIÇOS */
        .card-icone {
            width: 42px;
            height: 42px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 18px;
            border-radius: 9px;
            background: rgba(56, 189, 248, 0.09);
            border: 1px solid rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            font-size: 1.05rem;
            font-weight: bold;
        }

        /* 12. TÍTULO DOS SERVIÇOS */
        .card-servico h3 {
            font-size: 1.05rem;
            color: #f1f5f9;
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
            color: #94a3b8;
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
            background: #38bdf8;
            color: #07111f;
        }

        /* 13. RODAPÉ */
        .footer {
            background: #040a11;
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
    </style>
</head>


<!-- ================================================================ -->
<!-- ============================ [HTML] ============================= -->
<!-- HTML = ESTRUTURA VISÍVEL DA HOME                                -->
<!-- ================================================================ -->

<body>

    <!-- Barra Superior / Menu -->
    <header class="navbar">

        <!-- Logo da Empresa -->
        <a href="/" class="logo" aria-label="CNB Tech Solution - Página inicial">
            <img src="/logo-cnb?v=12" class="logo-img" alt="CNB Tech Solution">
        </a>

        <!-- Títulos da Home Page -->
        <ul class="nav-links">
            <li><a href="/empresa">Empresa</a></li>
            <li><a href="#servicos">Soluções</a></li>
            <li><a href="#industria">Indústria</a></li>
            <li><a href="#educacao">Educação</a></li>
            <li><a href="#treinamentos">Treinamentos</a></li>
            <li><a href="#laboratorio">Laboratório</a></li>
            <li><a href="#contato">Contato</a></li>
        </ul>

        <!-- Campo de Busca -->
        <div class="search-container">
            <input type="text" placeholder="Buscar...">
            <button type="button">Buscar</button>
        </div>
    </header>


    <!-- Conteúdo Principal -->
    <main class="hero">

        <!-- ========================================================== -->
        <!-- =============== [VÍDEO DE FUNDO DA HOME] ================= -->
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

        <!-- Camada de contraste entre o vídeo e o conteúdo -->
        <div class="hero-video-overlay" aria-hidden="true"></div>

        <!-- Conteúdo textual e cartões ficam acima do vídeo -->
        <div class="hero-conteudo">

            <!-- Indicador Visual -->
            <div class="status-tech">
                <span class="status-ponto"></span>
                {{ status_home }}
            </div>

            <!-- Título Principal -->
            <div class="hero-cabecalho">
                <h1>{{ titulo_home }}</h1>
                <p>{{ subtitulo_home }}</p>
            </div>


            <!-- ====================================================== -->
            <!-- ======================= [JINJA] ====================== -->
            <!-- JINJA = FAZ A LIGAÇÃO ENTRE O PYTHON E O HTML        -->
            <!-- ====================================================== -->

            <!-- Grade com links ativos -->
            <div class="grid-servicos" id="servicos">

                {% for item in lista_servicos %}

                <article class="card-servico">

                    <!-- Ícone do Serviço -->
                    <div class="card-icone">{{ item.icone }}</div>

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


    <!-- Rodapé -->
    <footer class="footer">
        <strong>CNB TECH SOLUTION</strong> • {{ rodape_home }}
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

        body {
            background-color: #050c15;
            background-image:
                radial-gradient(circle at 15% 20%,
                    rgba(14, 165, 233, 0.16),
                    transparent 350px),
                radial-gradient(circle at 85% 50%,
                    rgba(37, 99, 235, 0.12),
                    transparent 400px),
                linear-gradient(135deg, #050c16, #0b1e32, #06101d);
            color: #e2e8f0;
            min-height: 100vh;
        }

        /* 1. BARRA SUPERIOR */
        .navbar {
            background: rgba(7, 17, 31, 0.96);
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
            color: #38bdf8;
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
            color: #ffffff;
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
            background: rgba(15, 30, 48, 0.88);
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
            background: #38bdf8;
            color: #07111f;
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

    <!-- Barra Superior -->
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
    dados = {
        "nome_empresa": "CNB TECH SOLUTION",
        "status_home": obter_config_site("status_home", "Ecossistema de soluções digitais"),
        "titulo_home": obter_config_site("titulo_home", "Tecnologia que conecta infraestrutura e inovação."),
        "subtitulo_home": obter_config_site("subtitulo_home", "Soluções integradas para conectividade, infraestrutura de TI, desenvolvimento de sistemas, educação digital e produção audiovisual."),
        "rodape_home": obter_config_site("rodape_home", "Tecnologia, infraestrutura e soluções digitais."),

        "lista_servicos": [
            {
                "icone": "◉",
                "titulo": "Redes e Conectividade",
                "descricao": "Projetos e soluções de redes, conectividade e comunicação entre equipamentos e sistemas.",
                "link": "/servico/redes-conectividade",
                "slug": "redes-conectividade"
            },

            {
                "icone": "▦",
                "titulo": "Infraestrutura de TI",
                "descricao": "Implantação e organização de infraestrutura tecnológica para empresas e ambientes corporativos.",
                "link": "/servico/infraestrutura-ti",
                "slug": "infraestrutura-ti"
            },

            {
                "icone": "</>",
                "titulo": "Desenvolvimento de Sistemas",
                "descricao": "Desenvolvimento de sistemas web, plataformas digitais e soluções personalizadas para empresas.",
                "link": "/servico/desenvolvimento-sistemas",
                "slug": "desenvolvimento-sistemas"
            },

            {
                "icone": "◇",
                "titulo": "Soluções para Educação",
                "descricao": "Plataformas de ensino, ambientes EAD e ferramentas digitais para instituições educacionais.",
                "link": "/servico/educacao",
                "slug": "educacao"
            },

            {
                "icone": "▶",
                "titulo": "Soluções Audiovisuais",
                "descricao": "Estrutura para produção audiovisual, transmissões ao vivo e integração de áudio e vídeo.",
                "link": "/servico/audiovisual",
                "slug": "audiovisual"
            },

            {
                "icone": "⚙",
                "titulo": "Serviços de Informática & Suporte",
                "descricao": "Manutenção e acompanhamento técnico de equipamentos, serviços de rede e sistemas.",
                "link": "/servico/suporte",
                "slug": "suporte"
            }
        ]
    }

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
    dados = {
        "nome_empresa": "CNB TECH SOLUTION"
    }

    return render_template_string(LAYOUT_EMPRESA_HTML, **dados)



# ----------------------------------------------------------------------
# ------------- [INÍCIO: PAINEL ADMINISTRATIVO CNB TECH] ---------------
# ----------------------------------------------------------------------
ADMIN_BASE_CSS = """
<style>
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;background:#f1f5f9;color:#0f172a}.topo{background:linear-gradient(120deg,#07111f,#0d2238);color:white;padding:18px 5%;display:flex;justify-content:space-between;align-items:center}.topo a{color:#38bdf8;text-decoration:none;font-weight:700}.wrap{max-width:1180px;margin:30px auto;padding:0 20px}.menu{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}.menu a{background:white;border:1px solid #dbe3ec;padding:10px 14px;border-radius:8px;text-decoration:none;color:#334155;font-weight:600}.menu a:hover{border-color:#38bdf8;color:#0284c7}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.card{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:20px;box-shadow:0 5px 18px rgba(15,23,42,.05)}.numero{font-size:2rem;font-weight:800;color:#0f172a}.muted{color:#64748b}.tabela{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden}.tabela th,.tabela td{padding:12px;border-bottom:1px solid #e2e8f0;text-align:left;font-size:.9rem}.tabela th{background:#e2e8f0}.btn{display:inline-block;background:#0ea5e9;color:#07111f;padding:9px 13px;border:none;border-radius:7px;text-decoration:none;font-weight:700;cursor:pointer}.danger{background:#ef4444;color:white}.campo{width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:7px;margin:6px 0 12px}.form-card{max-width:650px;background:white;padding:25px;border-radius:12px;border:1px solid #e2e8f0}.alerta{background:#e0f2fe;border:1px solid #7dd3fc;padding:12px;border-radius:8px;margin-bottom:15px}@media(max-width:800px){.grid{grid-template-columns:repeat(2,1fr)}}.separador{border:0;border-top:1px solid #e2e8f0;margin:14px 0}.form-anexo{margin-top:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.btn-anexo{background:#e0f2fe;color:#0369a1;border:1px solid #7dd3fc}.lista-anexos{margin:8px 0}.anexo-item{margin:6px 0;padding:7px;background:#f8fafc;border-radius:6px}.anexo-item a{color:#0369a1;text-decoration:none;font-weight:600}.btn-mini{padding:4px 7px;font-size:.72rem;margin-left:5px}.btn-sec{background:#e2e8f0;color:#334155}.detalhe-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.bloco{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin:16px 0}.descricao{white-space:pre-wrap;background:#f8fafc;border:1px solid #e2e8f0;padding:14px;border-radius:8px;line-height:1.6}.acoes{display:flex;gap:8px;flex-wrap:wrap}.badge{display:inline-block;padding:5px 9px;border-radius:999px;background:#e0f2fe;color:#0369a1;font-size:.78rem;font-weight:700}@media(max-width:700px){.detalhe-grid{grid-template-columns:1fr}}.preview-midia{background:#07111f;border-radius:12px;padding:18px;margin:12px 0 20px;min-height:120px;display:flex;align-items:center;justify-content:center;overflow:hidden}.preview-midia img{max-width:100%;max-height:180px;object-fit:contain}.preview-midia video{width:100%;max-height:320px;border-radius:8px}.editor-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.nota-admin{font-size:.86rem;color:#64748b;line-height:1.5}.btn-salvar{margin-top:8px}.arquivo-atual{font-size:.82rem;color:#475569;word-break:break-all}@media(max-width:760px){.editor-grid{grid-template-columns:1fr}}@media(max-width:500px){.grid{grid-template-columns:1fr}}
</style>
"""

def admin_shell(titulo, conteudo):
    return render_template_string("""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{{titulo}} | CNB TECH</title>{{css|safe}}</head><body><header class='topo'><strong>⚡ CNB TECH SOLUTION • ADMIN</strong><div>{{email}} &nbsp; <a href='/admin/logout'>Sair</a></div></header><main class='wrap'><nav class='menu'><a href='/admin'>Dashboard</a><a href='/admin/editar-site'>Editar Site</a><a href='/admin/empresas'>Empresas</a><a href='/admin/orcamentos'>Orçamentos</a><a href='/admin/projetos'>Projetos</a><a href='/admin/administradores'>Administradores</a><a href='/' target='_blank' rel='noopener noreferrer'>Ver site</a></nav>{% with mensagens = get_flashed_messages() %}{% if mensagens %}{% for m in mensagens %}<div class='alerta'>{{m}}</div>{% endfor %}{% endif %}{% endwith %}{{conteudo|safe}}</main></body></html>""", titulo=titulo, css=ADMIN_BASE_CSS, conteudo=conteudo, email=session.get("admin_email",""))

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
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Tahoma,sans-serif}
body{background:linear-gradient(135deg,#050c16,#0b1e32,#06101d);color:#e2e8f0;min-height:100vh}
.topo-orc{background:#07111f;border-bottom:1px solid rgba(56,189,248,.25);padding:20px 5%;display:flex;justify-content:space-between;align-items:center;gap:15px}
.topo-orc a{color:#38bdf8;text-decoration:none;font-weight:700}
.orc-wrap{max-width:920px;margin:45px auto;padding:0 20px 60px}
.orc-card{background:rgba(15,30,48,.96);border:1px solid rgba(56,189,248,.20);border-radius:14px;padding:28px;box-shadow:0 18px 45px rgba(0,0,0,.25)}
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
    return render_template_string("""<!doctype html><html><head><meta charset='utf-8'><title>Login CNB Tech</title>{{css|safe}}</head><body><main class='wrap'><div class='form-card' style='margin:80px auto'><h1>⚡ CNB TECH SOLUTION</h1><p class='muted'>Acesso administrativo</p>{% if erro %}<div class='alerta'>{{erro}}</div>{% endif %}<form method='post'><label>E-mail</label><input class='campo' type='email' name='email' required><label>Senha</label><input class='campo' type='password' name='senha' required><button class='btn'>Entrar</button></form><p class='muted' style='margin-top:18px'>Primeiro acesso local: admin@cnbtech.local / CNBTech@2026</p></div></main></body></html>""",css=ADMIN_BASE_CSS,erro=erro)


# ----------------------------------------------------------------------
# -------- [ROTA TEMPORÁRIA DE DIAGNÓSTICO - PROTEGIDA POR TOKEN] -------
# ----------------------------------------------------------------------
@app.route('/admin/diagnostico')
def admin_diagnostico():
    token_recebido = request.args.get('token', '').strip()
    token_esperado = os.environ.get('DIAG_TOKEN', '').strip()

    if not token_esperado:
        return "DIAG_TOKEN não configurado no Render.", 500

    if token_recebido != token_esperado:
        return "Token de diagnóstico inválido.", 403

    banco_ok = False
    banco_erro = ""
    try:
        with conectar_banco() as conexao:
            conexao.execute("SELECT 1").fetchone()
        banco_ok = True
    except Exception as erro:
        banco_erro = f"{type(erro).__name__}: {erro}"

    dados = {
        "status": "OK",
        "rota": "/admin/diagnostico",
        "aplicacao": "CNB Tech Solution",
        "banco_sqlite": str(BANCO_DADOS),
        "arquivo_banco_existe": BANCO_DADOS.exists(),
        "conexao_banco_ok": banco_ok,
        "erro_banco": banco_erro or "nenhum",
        "database_url_configurada": bool(os.environ.get("DATABASE_URL")),
        "diag_token_configurado": bool(token_esperado),
        "ambiente_render": bool(os.environ.get("RENDER")),
        "hora_servidor": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }

    linhas = "".join(
        f"<tr><td style='padding:8px;border:1px solid #334155'><strong>{chave}</strong></td>"
        f"<td style='padding:8px;border:1px solid #334155'>{valor}</td></tr>"
        for chave, valor in dados.items()
    )

    return f"""
    <!doctype html>
    <html lang='pt-BR'>
    <head>
        <meta charset='utf-8'>
        <meta name='viewport' content='width=device-width,initial-scale=1'>
        <title>Diagnóstico | CNB Tech Solution</title>
    </head>
    <body style='font-family:Arial,sans-serif;background:#07111f;color:#e2e8f0;padding:30px'>
        <main style='max-width:900px;margin:auto'>
            <h1>Diagnóstico CNB Tech Solution</h1>
            <p>Se esta página abriu, a rota de diagnóstico está registrada corretamente.</p>
            <table style='width:100%;border-collapse:collapse;background:#0f2238'>
                {linhas}
            </table>
        </main>
    </body>
    </html>
    """


# ----------------------------------------------------------------------
# -------- [RECUPERAÇÃO DE ACESSO ADMIN - ROTA TEMPORÁRIA SEGURA] ------
# ----------------------------------------------------------------------
# Uso no Render:
# 1) Crie RESET_ADMIN_TOKEN nas Environment Variables com uma chave longa.
# 2) Confirme ADMIN_EMAIL com o e-mail do administrador.
# 3) Abra /admin/redefinir-senha?token=SUA_CHAVE
# 4) Defina a nova senha. Depois, remova esta rota e o RESET_ADMIN_TOKEN.
@app.route('/admin/redefinir-senha', methods=['GET', 'POST'])
def admin_redefinir_senha():
    token_recebido = request.args.get('token', '').strip()
    token_esperado = os.environ.get('RESET_ADMIN_TOKEN', '').strip()
    admin_email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    admin_name = os.environ.get('ADMIN_NAME', 'Administrador Master').strip() or 'Administrador Master'

    # Bloqueia a rota se a chave não estiver configurada ou estiver incorreta.
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
    with conectar_banco() as c:
        totais={k:c.execute(q).fetchone()[0] for k,q in {'empresas':'SELECT COUNT(*) FROM empresas','orcamentos':'SELECT COUNT(*) FROM orcamentos','novos':"SELECT COUNT(*) FROM orcamentos WHERE status='Novo'",'projetos':'SELECT COUNT(*) FROM projetos','visitas':'SELECT COUNT(*) FROM visitas','admins':'SELECT COUNT(*) FROM administradores WHERE ativo=1'}.items()}
        recentes=c.execute('SELECT * FROM orcamentos ORDER BY id DESC LIMIT 8').fetchall()
    linhas=''.join(f"<tr><td>{r['nome']}</td><td>{r['empresa'] or '-'}</td><td>{r['servico']}</td><td>{r['status']}</td><td><a class='btn btn-sec btn-mini' href='/admin/orcamentos/{r['id']}'>Ver detalhes</a><br><small>{r['criado_em']}</small></td></tr>" for r in recentes) or "<tr><td colspan='5'>Nenhuma solicitação.</td></tr>"
    cards=''.join(f"<div class='card'><div class='muted'>{rot}</div><div class='numero'>{totais[ch]}</div></div>" for ch,rot in [('empresas','Empresas'),('orcamentos','Orçamentos'),('novos','Novos'),('projetos','Projetos'),('visitas','Visitas'),('admins','Administradores')])
    return admin_shell('Dashboard',f"<h1>Dashboard</h1><p class='muted'>Central administrativa e comercial da CNB Tech Solution.</p><div class='grid' style='margin:22px 0'>{cards}</div><h2>Solicitações recentes</h2><table class='tabela'><tr><th>Contato</th><th>Empresa</th><th>Serviço</th><th>Status</th><th>Data</th></tr>{linhas}</table>")

@app.route('/admin/editar-site', methods=['GET', 'POST'])
@login_obrigatorio
def admin_editar_site():
    from html import escape

    if request.method == 'POST':
        # Textos principais da Home
        campos_texto = {
            'status_home': request.form.get('status_home', '').strip(),
            'titulo_home': request.form.get('titulo_home', '').strip(),
            'subtitulo_home': request.form.get('subtitulo_home', '').strip(),
            'rodape_home': request.form.get('rodape_home', '').strip(),
        }
        for chave, valor in campos_texto.items():
            if valor:
                salvar_config_site(chave, valor)

        # Nova logo: fica fora do .py para evitar travamento do IDLE.
        logo = request.files.get('logo_site')
        if logo and logo.filename:
            nome_original = secure_filename(logo.filename)
            ext = extensao_arquivo(nome_original)
            if ext not in EXTENSOES_LOGO_SITE:
                flash('Logo não atualizada: use PNG, WEBP, JPG ou JPEG.')
                return redirect(url_for('admin_editar_site'))

            # Remove somente versões antigas administradas por este módulo.
            for antigo in PASTA_MIDIA_SITE.glob('logo-site.*'):
                try:
                    antigo.unlink()
                except OSError:
                    pass
            nome_salvo = f'logo-site.{ext}'
            logo.save(PASTA_MIDIA_SITE / nome_salvo)
            salvar_config_site('logo_arquivo', nome_salvo)
            registrar_atividade(f'Logo do site atualizada: {nome_salvo}')

        # Novo vídeo de fundo: MP4, também fora do código Python.
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

        # Botões de restauração: voltam para os arquivos que acompanham o projeto.
        if request.form.get('restaurar_logo') == '1':
            salvar_config_site('logo_arquivo', '')
            registrar_atividade('Logo do site restaurada para o arquivo padrão')

        if request.form.get('restaurar_video') == '1':
            salvar_config_site('video_arquivo', '')
            registrar_atividade('Vídeo da Home restaurado para o arquivo padrão')

        registrar_atividade('Conteúdo da Home atualizado pelo módulo Editar Site')
        flash('Site atualizado com sucesso. Abra “Ver site” para conferir.')
        return redirect(url_for('admin_editar_site'))

    status_home = obter_config_site('status_home', 'Ecossistema de soluções digitais')
    titulo_home = obter_config_site('titulo_home', 'Tecnologia que conecta infraestrutura e inovação.')
    subtitulo_home = obter_config_site('subtitulo_home', 'Soluções integradas para conectividade, infraestrutura de TI, desenvolvimento de sistemas, educação digital e produção audiovisual.')
    rodape_home = obter_config_site('rodape_home', 'Tecnologia, infraestrutura e soluções digitais.')
    logo_atual = obter_config_site('logo_arquivo', '') or LOGO_CNB_NOME
    video_atual = obter_config_site('video_arquivo', '') or VIDEO_HOME_NOME

    conteudo = f"""
    <h1>Editar Site</h1>
    <p class='muted'>Atualize a logo, o vídeo da Home e os textos principais sem abrir ou alterar o código Python.</p>

    <form method='post' enctype='multipart/form-data'>
      <div class='editor-grid' style='margin-top:22px'>
        <section class='form-card' style='max-width:none'>
          <h2>Identidade visual</h2>
          <p class='nota-admin'>A nova logo é salva na pasta <strong>midia_site</strong>. O arquivo não entra dentro do código, evitando o travamento que ocorreu nas versões anteriores.</p>
          <div class='preview-midia'><img src='/logo-cnb?t={datetime.now().timestamp()}' alt='Logo atual'></div>
          <div class='arquivo-atual'>Arquivo atual: {escape(logo_atual)}</div>
          <label>Trocar logo</label>
          <input class='campo' type='file' name='logo_site' accept='.png,.webp,.jpg,.jpeg,image/png,image/webp,image/jpeg'>
          <label style='display:flex;gap:8px;align-items:center'><input type='checkbox' name='restaurar_logo' value='1'> Restaurar logo padrão do projeto</label>
        </section>

        <section class='form-card' style='max-width:none'>
          <h2>Vídeo da Home</h2>
          <p class='nota-admin'>Envie um arquivo MP4. O vídeo também fica fora do Python, na pasta <strong>midia_site</strong>.</p>
          <div class='preview-midia'><video controls muted preload='metadata'><source src='/video-home?t={datetime.now().timestamp()}' type='video/mp4'></video></div>
          <div class='arquivo-atual'>Arquivo atual: {escape(video_atual)}</div>
          <label>Trocar vídeo</label>
          <input class='campo' type='file' name='video_site' accept='.mp4,video/mp4'>
          <label style='display:flex;gap:8px;align-items:center'><input type='checkbox' name='restaurar_video' value='1'> Restaurar vídeo padrão do projeto</label>
        </section>
      </div>

      <div class='form-card' style='max-width:none;margin-top:18px'>
        <h2>Textos principais da Home</h2>
        <label>Indicador superior</label>
        <input class='campo' name='status_home' maxlength='120' value='{escape(status_home)}'>
        <label>Título principal</label>
        <input class='campo' name='titulo_home' maxlength='180' value='{escape(titulo_home)}'>
        <label>Descrição</label>
        <textarea class='campo' name='subtitulo_home' rows='4' maxlength='600'>{escape(subtitulo_home)}</textarea>
        <label>Texto do rodapé</label>
        <input class='campo' name='rodape_home' maxlength='220' value='{escape(rodape_home)}'>
        <button class='btn btn-salvar' type='submit'>Salvar alterações do site</button>
        <a class='btn btn-sec' href='/' target='_blank' rel='noopener noreferrer' style='margin-left:8px'>Abrir site</a>
      </div>
    </form>
    """
    return admin_shell('Editar Site', conteudo)

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
    iniciar_banco()

    IP_LOCAL = "127.0.0.1"
    PORTA_ACESSO = 5000

    # Abre o navegador 1.5 segundo após ligar o servidor
    Timer(1.5, abrir_navegador, args=[PORTA_ACESSO]).start()

    print(f"\n[+] Servidor iniciado com sucesso!")

    # Diagnóstico do vídeo: aparece no Shell do IDLE ao pressionar F5.
    if VIDEO_HOME_ARQUIVO.exists():
        tamanho_mb = VIDEO_HOME_ARQUIVO.stat().st_size / (1024 * 1024)
        print(f"[+] Vídeo da Home encontrado: {VIDEO_HOME_NOME} ({tamanho_mb:.1f} MB)")
        print(f"[+] Teste direto do vídeo: http://{IP_LOCAL}:{PORTA_ACESSO}/video-home")
    else:
        print(f"[!] ATENÇÃO: coloque {VIDEO_HOME_NOME} na mesma pasta deste arquivo Python.")

    print(f"[+] Módulo Editar Site: http://{IP_LOCAL}:{PORTA_ACESSO}/admin/editar-site")
    print(f"[+] Acesse a Home Page: http://{IP_LOCAL}:{PORTA_ACESSO}/")
    print(f"[+] Acesse direto a Empresa: http://{IP_LOCAL}:{PORTA_ACESSO}/empresa\n")

    # Inicia o Flask
    app.run(host=IP_LOCAL, port=PORTA_ACESSO, debug=True, use_reloader=False)







