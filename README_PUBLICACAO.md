# CNB Tech Solution — V20 COMPLETA

Pacote consolidado da última V20 completa, preparado para GitHub + Render.

## O que esta versão contém
- Home completa CNB Tech Solution
- Área Empresa / Quem Somos
- Dashboard administrativo
- Editar Site 2.0
- Upload de logo e vídeo da Home
- Contatos & Redes Sociais
- Empresas e fichas de clientes
- Orçamentos e anexos
- Projetos
- Conteúdo das Áreas
- Equipe / Quem Somos com upload de fotos
- Projetos & Galeria com upload de imagens/vídeos
- Notícias
- Administradores
- Login e logout
- Botão "Esqueci minha senha"
- Recuperação por RESET_ADMIN_TOKEN
- Redefinição/criação do administrador via ADMIN_EMAIL

## Arquivo principal no Render
O arquivo principal é `app.py`.

Build Command:
`pip install -r requirements.txt`

Start Command:
`gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`

## Variáveis mínimas já usadas no fluxo de acesso
- SECRET_KEY
- ADMIN_EMAIL
- RESET_ADMIN_TOKEN

ADMIN_NAME é opcional. Caso não exista, o sistema usa "Administrador Master".

Para envio de e-mail pelo Gmail, configure também:
- CNB_EMAIL_REMETENTE
- CNB_GMAIL_APP_PASSWORD

## GitHub
Extraia este ZIP no computador e envie os arquivos extraídos para a raiz do repositório `CNB-Tech-Solution`, substituindo o `app.py` anterior.
Não envie apenas o ZIP esperando que o Render o descompacte.

## Persistência
Banco SQLite, uploads do Dashboard e anexos são gravados no armazenamento do serviço. Em serviço Render sem disco persistente, esses dados podem ser perdidos em reinicializações/redeploys. O código aceita `DATA_DIR` para uso com armazenamento persistente quando disponível.
