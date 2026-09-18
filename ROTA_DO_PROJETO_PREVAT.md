# ROTA DO PROJETO — PREVAT TECH

## Objetivo
Construir e publicar uma aplicação web de teste da PREVAT TECH com cadastro de empresas, autenticação e painel individual, mantendo o projeto organizado para evoluções futuras.

## ETAPA 1 — Homepage
Status: IMPLEMENTADA
- Identidade PREVAT TECH.
- Menu principal.
- Botão "Cadastrar Empresa".
- Botão "Login".
- Área de apresentação e serviços.

Rotas:
- `/` — Homepage.

## ETAPA 2 — Cadastro de Empresa
Status: IMPLEMENTADA
Campos atuais:
- Nome da empresa.
- CNPJ.
- E-mail.
- Senha.
- Confirmação de senha.

Regras:
- Senha mínima de 8 caracteres no formulário.
- Senha e confirmação precisam ser iguais.
- E-mail não pode ser repetido.
- CNPJ não pode ser repetido.
- Senha é armazenada como hash, não em texto puro.

Rota:
- `/cadastro`

## ETAPA 3 — Login
Status: IMPLEMENTADA
- Login por e-mail e senha.
- Verificação do hash da senha.
- Criação de sessão após autenticação.

Rota:
- `/login`

## ETAPA 4 — Painel individual da empresa
Status: IMPLEMENTADA — versão inicial
- Acesso somente com sessão.
- Exibe nome, CNPJ e e-mail da empresa autenticada.

Rota:
- `/painel`

## ETAPA 5 — Logout
Status: IMPLEMENTADA
- Encerra a sessão.
- Redireciona para login.

Rota:
- `/logout`

## ETAPA 6 — Banco de dados
Status: IMPLEMENTADA — estrutura inicial
Desenvolvimento local:
- Se `DATABASE_URL` não existir, usa SQLite para facilitar os testes.

Render:
- Usa PostgreSQL através da variável `DATABASE_URL`.
- Tabela atual: `empresas`.

Campos:
- id
- nome
- cnpj
- email
- senha_hash

## ETAPA 7 — Publicação no Render
Status: PREPARADA
Arquivos:
- `app.py`
- `requirements.txt`
- `render.yaml`
- `.gitignore`

Comando de build:
`pip install -r requirements.txt`

Comando de inicialização:
`gunicorn app:app`

Rota de saúde:
- `/health`

## ETAPA 8 — Segurança para evolução
Status: PRÓXIMA ETAPA
Antes de transformar o protótipo em produção:
- CSRF nos formulários.
- Validação e normalização real de CNPJ.
- Recuperação de senha por e-mail.
- Confirmação de e-mail.
- Rate limiting contra tentativas repetidas de login.
- Cookies seguros em HTTPS.
- Migrações de banco de dados.
- Política de privacidade/LGPD e gestão de consentimento.
- Perfis e permissões de utilizadores.
- Auditoria de ações administrativas.

## ETAPA 9 — Evoluções planejadas
Status: NÃO IMPLEMENTADAS
- Área administrativa PREVAT TECH.
- Gestão de empresas cadastradas.
- Cadastro de utilizadores por empresa.
- Perfis e permissões.
- Recuperação de senha.
- E-mail transacional.
- Planos/assinaturas.
- Módulos de serviços PREVAT TECH.
- Dashboard com indicadores.
- Upload de documentos.
- Logs e histórico.
- Domínio personalizado.

## MAPA DO FLUXO ATUAL

HOME `/`
  ↓
CADASTRO `/cadastro`
  ↓
LOGIN `/login`
  ↓
PAINEL `/painel`
  ↓
LOGOUT `/logout`
  ↓
LOGIN `/login`

## REGRA DE ORGANIZAÇÃO DO PROJETO
Toda nova funcionalidade deverá ser:
1. registrada neste arquivo;
2. marcada como planejada, em desenvolvimento ou implementada;
3. associada às suas rotas;
4. identificada no código por comentários;
5. revisada quanto à segurança antes de produção.
