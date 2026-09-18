# ================================================================
# PREVAT TECH — FLASK + POSTGRESQL — PREPARADO PARA RENDER
# Homepage + Cadastro + Login + Painel + Logout
# ================================================================

import os
from flask import Flask, render_template_string, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# [PYTHON] SEGREDOS / CONFIGURAÇÃO
app.secret_key = os.environ.get("SECRET_KEY", "chave-local-apenas-para-estudo")

database_url = os.environ.get("DATABASE_URL", "sqlite:///prevat_local.db")
# Compatibilidade com URLs antigas do PostgreSQL:
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ================================================================
# [PYTHON + BANCO] MODELO DA EMPRESA
# ================================================================
class Empresa(db.Model):
    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    cnpj = db.Column(db.String(30), unique=True, nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)

with app.app_context():
    db.create_all()

# ================================================================
# [HTML + CSS + JINJA] HOMEPAGE
# ================================================================
HOME_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PREVAT TECH</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Arial,sans-serif;background:#f1f5f9;color:#1e293b}
.navbar{background:#0f172a;display:flex;justify-content:space-between;align-items:center;padding:18px 40px}
.logo{font-size:24px;font-weight:700;color:#38bdf8;text-decoration:none}
.menu{display:flex;gap:18px;align-items:center}.menu a{color:#fff;text-decoration:none}
.btn{padding:10px 18px;border-radius:7px}.outline{border:1px solid #38bdf8}.primary{background:#0284c7}
.hero{min-height:440px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:40px 20px;background:linear-gradient(135deg,#0f172a,#1e3a8a);color:#fff}
.hero h1{font-size:48px;margin-bottom:15px}.hero h1 span{color:#38bdf8}
.hero p{font-size:19px;max-width:720px;color:#cbd5e1;margin-bottom:28px}
.actions{display:flex;gap:14px}.actions a{text-decoration:none;padding:13px 24px;border-radius:7px;font-weight:700}
.actions .cad{background:#38bdf8;color:#0f172a}.actions .log{border:1px solid #38bdf8;color:#fff}
.servicos{max-width:1100px;margin:50px auto;padding:20px}.servicos h2{text-align:center;margin-bottom:28px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px}
.card{background:#fff;padding:24px;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,.08)}
.card h3{color:#0284c7;margin-bottom:10px}
footer{background:#0f172a;color:#94a3b8;text-align:center;padding:24px}
@media(max-width:700px){.navbar{flex-direction:column;gap:16px}.menu{flex-wrap:wrap;justify-content:center}.hero h1{font-size:35px}.actions{flex-direction:column}}
</style>
</head>
<body>
<header class="navbar">
<a href="/" class="logo">⚡ PREVAT TECH</a>
<nav class="menu">
<a href="/">Início</a>
<a href="#servicos">Serviços</a>
<a href="/login" class="btn outline">Login</a>
<a href="/cadastro" class="btn primary">Cadastrar Empresa</a>
</nav>
</header>
<section class="hero">
<h1>Soluções Digitais <span>PREVAT TECH</span></h1>
<p>Tecnologia, desenvolvimento de sistemas, infraestrutura digital e soluções inteligentes para empresas.</p>
<div class="actions">
<a href="/cadastro" class="cad">Cadastrar minha empresa</a>
<a href="/login" class="log">Acessar sistema</a>
</div>
</section>
<section class="servicos" id="servicos">
<h2>Soluções PREVAT TECH</h2>
<div class="grid">
<div class="card"><h3>Empresa TECH</h3><p>Soluções digitais para gestão e transformação tecnológica.</p></div>
<div class="card"><h3>Serviços em Nuvem</h3><p>Infraestrutura e serviços digitais integrados.</p></div>
<div class="card"><h3>Laboratório Digital</h3><p>Ambiente para desenvolvimento, testes e inovação.</p></div>
<div class="card"><h3>Suporte</h3><p>Atendimento e suporte para empresas.</p></div>
</div>
</section>
<footer>PREVAT TECH © 2026</footer>
</body>
</html>
"""

# ================================================================
# [HTML + CSS + JINJA] CADASTRO
# ================================================================
CADASTRO_HTML = """
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Cadastro | PREVAT TECH</title>
<style>
*{box-sizing:border-box}body{font-family:Arial;background:linear-gradient(135deg,#0f172a,#1e3a8a);margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{width:440px;max-width:92%;background:#fff;padding:34px;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.3)}
.logo{text-align:center;color:#0284c7;font-size:27px;font-weight:700}h2{text-align:center;color:#0f172a}
label{font-weight:700;font-size:14px}input{width:100%;padding:12px;margin:6px 0 14px;border:1px solid #cbd5e1;border-radius:6px}
button{width:100%;padding:13px;background:#0284c7;color:#fff;border:0;border-radius:6px;font-weight:700;cursor:pointer}
.erro{background:#fee2e2;color:#b91c1c;padding:10px;border-radius:6px}.links{text-align:center;margin-top:18px}a{color:#0284c7;text-decoration:none}
</style></head><body><div class="box">
<div class="logo">⚡ PREVAT TECH</div><h2>Cadastro de Empresa</h2>
{% if mensagem %}<p class="erro">{{ mensagem }}</p>{% endif %}
<form method="POST">
<label>Nome da Empresa</label><input type="text" name="empresa" required>
<label>CNPJ</label><input type="text" name="cnpj" required>
<label>E-mail</label><input type="email" name="email" required>
<label>Senha</label><input type="password" name="senha" minlength="8" required>
<label>Confirmar Senha</label><input type="password" name="confirmar_senha" minlength="8" required>
<button type="submit">Cadastrar Empresa</button>
</form>
<div class="links"><p>Já possui cadastro? <a href="/login">Entrar</a></p><p><a href="/">← Voltar para Home</a></p></div>
</div></body></html>
"""

# ================================================================
# [HTML + CSS + JINJA] LOGIN
# ================================================================
LOGIN_HTML = """
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Login | PREVAT TECH</title>
<style>
*{box-sizing:border-box}body{font-family:Arial;background:#0f172a;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{width:400px;max-width:92%;background:#fff;padding:34px;border-radius:12px}.logo{text-align:center;color:#0284c7;font-size:28px;font-weight:700}
h2{text-align:center}input{width:100%;padding:12px;margin:7px 0 15px;border:1px solid #cbd5e1;border-radius:6px}
button{width:100%;padding:13px;background:#0284c7;color:#fff;border:0;border-radius:6px;font-weight:700}
.erro{background:#fee2e2;color:#b91c1c;padding:10px;border-radius:6px}.links{text-align:center;margin-top:18px}a{color:#0284c7;text-decoration:none}
</style></head><body><div class="box"><div class="logo">⚡ PREVAT TECH</div><h2>Acesso da Empresa</h2>
{% if mensagem %}<p class="erro">{{ mensagem }}</p>{% endif %}
<form method="POST"><label>E-mail</label><input type="email" name="email" required>
<label>Senha</label><input type="password" name="senha" required>
<button type="submit">Entrar</button></form>
<div class="links"><p>Não possui cadastro? <a href="/cadastro">Cadastrar Empresa</a></p><p><a href="/">← Voltar para Home</a></p></div>
</div></body></html>
"""

# ================================================================
# [PYTHON] ROTAS
# ================================================================
@app.route("/")
def home():
    return render_template_string(HOME_HTML)

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    mensagem = ""
    if request.method == "POST":
        nome = request.form["empresa"].strip()
        cnpj = request.form["cnpj"].strip()
        email = request.form["email"].lower().strip()
        senha = request.form["senha"]
        confirmar = request.form["confirmar_senha"]

        if senha != confirmar:
            mensagem = "As senhas não são iguais."
        elif Empresa.query.filter_by(email=email).first():
            mensagem = "Este e-mail já está cadastrado."
        elif Empresa.query.filter_by(cnpj=cnpj).first():
            mensagem = "Este CNPJ já está cadastrado."
        else:
            nova = Empresa(
                nome=nome,
                cnpj=cnpj,
                email=email,
                senha_hash=generate_password_hash(senha)
            )
            db.session.add(nova)
            db.session.commit()
            return redirect(url_for("login"))

    return render_template_string(CADASTRO_HTML, mensagem=mensagem)

@app.route("/login", methods=["GET", "POST"])
def login():
    mensagem = ""
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        senha = request.form["senha"]
        empresa = Empresa.query.filter_by(email=email).first()

        if empresa and check_password_hash(empresa.senha_hash, senha):
            session.clear()
            session["empresa_id"] = empresa.id
            return redirect(url_for("painel"))
        mensagem = "E-mail ou senha incorretos."

    return render_template_string(LOGIN_HTML, mensagem=mensagem)

@app.route("/painel")
def painel():
    empresa_id = session.get("empresa_id")
    if not empresa_id:
        return redirect(url_for("login"))

    empresa = db.session.get(Empresa, empresa_id)
    if not empresa:
        session.clear()
        return redirect(url_for("login"))

    return render_template_string("""
    <!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Painel | PREVAT TECH</title>
    <style>
    body{font-family:Arial;margin:0;background:#f1f5f9}.nav{background:#0f172a;color:#fff;padding:20px 40px;display:flex;justify-content:space-between}
    .logo{color:#38bdf8;font-weight:700}.nav a{color:#fff;text-decoration:none}.container{max-width:900px;margin:50px auto;background:#fff;padding:35px;border-radius:10px}
    .card{background:#f8fafc;padding:20px;border-radius:8px;margin-top:20px}a{color:#0284c7}
    </style></head><body>
    <header class="nav"><div class="logo">⚡ PREVAT TECH</div><a href="/logout">Sair</a></header>
    <main class="container"><h1>Painel da Empresa</h1><h2>Bem-vindo, {{ empresa.nome }}</h2>
    <div class="card"><p><strong>Empresa:</strong> {{ empresa.nome }}</p>
    <p><strong>CNPJ:</strong> {{ empresa.cnpj }}</p><p><strong>E-mail:</strong> {{ empresa.email }}</p></div>
    <p><a href="/">← Voltar para Home</a></p></main></body></html>
    """, empresa=empresa)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/health")
def health():
    return {"status": "ok"}, 200

# Execução local. No Render, o Gunicorn inicia app:app.
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
