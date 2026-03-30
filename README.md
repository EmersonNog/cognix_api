# Cognix API (FastAPI)

## Requisitos

- Python 3.10+
- Postgres

## Configuração

1. Copie `.env.example` para `.env` e ajuste as vari�veis.
2. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Execute:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

## Autenticação

A API valida **Firebase ID Token** via header:

```
Authorization: Bearer <token>
```

## Endpoints

- `GET /health`
- `GET /questions`
  - query params: `limit`, `offset`, `subject`, `year`, `search`, `include_total`
- `GET /questions/disciplinas`
- `GET /questions/subcategorias`
  - query params: `disciplina`
- `GET /questions/{question_id}`

## Observações

- A tabela padrão é `questoes` (configurável em `QUESTION_TABLE`).
- Campos sensíveis como `gabarito` não são retornados nas respostas.
