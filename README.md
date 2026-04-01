# Cognix API

Backend FastAPI da plataforma Cognix. Esta API concentra autenticação com Firebase, leitura da base de questões, registro de tentativas, persistência de sessões de treino e geração de resumos personalizados com IA.

## Docker

Fluxo recomendado após clonar o projeto:

1. Copie `.env.example` para `.env`
2. Ajuste a `.env` para o ambiente Docker
3. Se usar Firebase, coloque o arquivo de credenciais em `./secrets/firebase-service-account.json`
4. Se a base de questões não existir no banco Docker, coloque o backup em `./backups/cognix.backup`
5. Suba os containers:

```bash
docker compose up -d --build
```

6. Restaure a base:

```powershell
.\scripts\restore_db.ps1
```

Depois, verifique se a tabela `questions` apareceu:

```powershell
docker compose exec db psql -U postgres -d cognix -c "\dt"
```

Saída esperada:

```text
                 List of tables
 Schema |          Name           | Type  |  Owner
--------+-------------------------+-------+----------
 public | question_attempts       | table | postgres
 public | questions               | table | postgres
 public | training_sessions       | table | postgres
 public | training_summaries      | table | postgres
 public | training_summaries_user | table | postgres
 public | users                   | table | postgres
(6 rows)
```

7. Valide a API:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

Configuração recomendada da `.env` para Docker:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/cognix
POSTGRES_DB=cognix
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5432
API_PORT=8000
QUESTION_TABLE=questions
USERS_TABLE=users
ALLOWED_ORIGINS=["*"]
FIREBASE_CREDENTIALS=/app/secrets/firebase-service-account.json
GEMINI_API_KEY=coloque_sua_chave_aqui
GEMINI_MODEL=gemini-3-flash-preview
```

Observações:

- no `DATABASE_URL`, use `db:5432`, não `localhost`
- `POSTGRES_PORT` controla a porta exposta na sua máquina
- dentro da rede Docker, a API sempre acessa o banco por `db:5432`
- o backend ignora variáveis extras do `compose`, como `POSTGRES_DB` e `API_PORT`
- as tabelas internas são criadas no startup, mas a tabela `questions` precisa vir do backup da base
- as pastas `backups/` e `secrets/` podem ir para o repositório vazias com `.gitkeep`, mas o conteúdo real não deve subir

## Stack

- Python 3.10+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Firebase Authentication
- Gemini API

## Principais recursos

- validação de `Firebase ID Token` em rotas protegidas
- sincronização de usuário Firebase para tabela interna
- listagem e filtro de questões por disciplina, subcategoria, ano e busca textual
- registro de tentativas do usuário
- sessões de treino persistidas por `usuário + disciplina + subcategoria`
- restauração de simulados em andamento em vários dispositivos
- armazenamento de simulados concluídos para reabrir a tela de resultados
- overview de sessões para cards e agregados no app
- resumos e mapas mentais personalizados com base em desempenho real e contexto da subcategoria
- padronização de datas em UTC com serialização consistente para a API

## Estrutura de dados interna

No startup, a API garante a criação das tabelas internas abaixo:

- `users`
- `question_attempts`
- `training_sessions`
- `training_summaries`
- `training_summaries_user`

Os nomes reais podem ser alterados por variáveis de ambiente.

### `training_sessions`

Tabela usada para persistir o estado do simulado.

Campos principais:

- `user_id`
- `firebase_uid`
- `discipline`
- `subcategory`
- `state_json`
- `created_at`
- `updated_at`

Existe unicidade por:

- `user_id + discipline + subcategory`

Isso permite:

- continuar um simulado em andamento
- marcar um simulado como concluído
- compartilhar esse estado entre dispositivos com a mesma conta

Comandos úteis:

```bash
docker compose up --build
docker compose logs -f api
docker compose logs -f db
docker compose down
docker compose down -v
```

## Variáveis principais

Configuradas em [`app/core/config.py`](C:/Users/Nogueira/Desktop/cognix_api/app/core/config.py):

- `DATABASE_URL`
- `QUESTION_TABLE`
- `USERS_TABLE`
- `ATTEMPTS_TABLE`
- `SESSIONS_TABLE`
- `SUMMARIES_TABLE`
- `USER_SUMMARIES_TABLE`
- `ALLOWED_ORIGINS`
- `FIREBASE_CREDENTIALS`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

Defaults atuais:

- tabela de questões: `questions`
- usuários internos: `users`
- tentativas: `question_attempts`
- sessões: `training_sessions`
- resumos globais: `training_summaries`
- resumos por usuário: `training_summaries_user`

## Autenticação

Rotas protegidas esperam:

```http
Authorization: Bearer <firebase_id_token>
```

Fluxo:

- a API valida o token do Firebase
- extrai `uid`, `email`, `name` e `provider`
- sincroniza o usuário na tabela interna
- usa o `user_id` interno nas tabelas relacionais

## Datas e timezone

A API usa utilitários centralizados em [`app/core/datetime_utils.py`](C:/Users/Nogueira/Desktop/cognix_api/app/core/datetime_utils.py).

Padrão atual:

- persistência em UTC
- colunas internas com `DateTime(timezone=True)`
- serialização consistente para respostas JSON

Isso foi feito para evitar deslocamentos de horário entre banco, backend e app Flutter.

## Documentação da API

Para detalhes das rotas, payloads e respostas, use o Swagger da aplicação:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Observações importantes

- nenhuma tabela nova foi criada para o agregado de sessões; o overview usa a tabela `training_sessions` que já existia
- a contagem de simulados concluídos depende do campo `completed` salvo dentro de `state_json`
- sessões são separadas por `disciplina + subcategoria`, evitando mistura entre simulados diferentes do mesmo usuário
- o backend foi ajustado para suportar restauração e reabertura de resultados em múltiplos dispositivos com a mesma conta

## Desenvolvimento

Comando útil para validar rapidamente um arquivo Python alterado:

```bash
python -m py_compile app/api/endpoints/sessions.py
```

## Status atual do projeto

O backend já atende bem um produto profissional em evolução, com:

- autenticação real
- dados persistidos por usuário
- sessões de treino multi-dispositivo
- agregados para a interface
- resumos personalizados orientados por desempenho

Os próximos passos naturais são:

- testes automatizados de endpoints
- observabilidade de erros e latência
- agregados pedagógicos mais ricos por área e disciplina
- endurecimento de contratos de resposta da IA


