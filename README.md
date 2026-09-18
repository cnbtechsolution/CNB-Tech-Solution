# PREVAT TECH — versão de teste para Render

Arquivos principais:
- `app.py`: aplicação Flask.
- `requirements.txt`: dependências Python.
- `render.yaml`: infraestrutura para Render.
- `ROTA_DO_PROJETO_PREVAT.md`: mapa em português do projeto.
- `.gitignore`: arquivos que não devem ir ao Git.

## Teste local
1. Instale: `pip install -r requirements.txt`
2. Execute: `python app.py`
3. Abra: `http://127.0.0.1:5000`

Sem `DATABASE_URL`, o projeto usa SQLite local apenas para desenvolvimento.

## Render
O Blueprint em `render.yaml` prepara um Web Service e um PostgreSQL.
No Render, a aplicação é iniciada por:
`gunicorn app:app`

A `SECRET_KEY` é gerada como variável de ambiente e a conexão do banco entra por `DATABASE_URL`.

## Aviso
Esta é uma base de teste/estudo. Antes de produção, implemente as medidas descritas em `ROTA_DO_PROJETO_PREVAT.md`.
