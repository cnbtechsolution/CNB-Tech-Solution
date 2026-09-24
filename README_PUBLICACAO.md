# CNB Tech Solution V20 — GitHub + Render

Versão preparada para publicação, mantendo a estrutura e as funções da V20.

## Arquivo principal
`app.py`

## GitHub
Crie um repositório (de preferência privado no primeiro deploy) e envie
**o conteúdo desta pasta**, não o ZIP.

O `.gitignore` bloqueia:
- `.env`
- banco SQLite local
- uploads de clientes/equipe/galeria/notícias
- anexos enviados pelo Dashboard

## Render — Build Command
```bash
pip install -r requirements.txt
```

## Render — Start Command
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

## Variáveis obrigatórias no Render
- `SECRET_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `ADMIN_NAME` (opcional)

Para envio de e-mail pelo Gmail:
- `CNB_EMAIL_REMETENTE=cnbtvpara2019@gmail.com`
- `CNB_GMAIL_APP_PASSWORD`

Nunca coloque senhas reais no GitHub.

## Banco e uploads
A V20 usa SQLite e grava arquivos em disco.

Sem armazenamento persistente, banco e uploads podem ser perdidos após
recriação/redeploy da instância.

Quando você configurar um Persistent Disk, monte em:
`/var/data`

Depois configure no Render:
`DATA_DIR=/var/data`

A aplicação passa automaticamente a gravar banco, mídias e anexos ali.

## Primeiro acesso
Após o deploy:
- Home: `/`
- Admin: `/admin`
- Galeria: `/galeria`
- Notícias: `/noticias`

Se o banco estiver vazio, o primeiro administrador será criado usando
`ADMIN_EMAIL` e `ADMIN_PASSWORD`.

## Segurança aplicada
- senha padrão removida do código;
- `SECRET_KEY` removida do código;
- segredos preparados para variáveis de ambiente;
- banco e uploads protegidos pelo `.gitignore`;
- suporte a `DATA_DIR` para Persistent Disk;
- Gunicorn preparado para o Render com 1 worker, adequado ao SQLite atual.
