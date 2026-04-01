# Cognix API

Backend FastAPI da plataforma Cognix. Esta API concentra autenticacao com Firebase, leitura da base de questoes, registro de tentativas, persistencia de sessoes de treino e geracao de resumos personalizados com IA.

## Stack

- Python 3.10+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Firebase Authentication
- Gemini API

## Principais recursos

- validacao de `Firebase ID Token` em rotas protegidas
- sincronizacao de usuario Firebase para tabela interna
- listagem e filtro de questoes por disciplina, subcategoria, ano e busca textual
- registro de tentativas do usuario
- sessoes de treino persistidas por `usuario + disciplina + subcategoria`
- restauracao de simulados em andamento em varios dispositivos
- armazenamento de simulados concluidos para reabrir a tela de resultados
- overview de sessoes para cards e agregados no app
- resumos e mapas mentais personalizados com base em desempenho real e contexto da subcategoria
- padronizacao de datas em UTC com serializacao consistente para a API

## Estrutura de dados interna

No startup, a API garante a criacao das tabelas internas abaixo:

- `users`
- `question_attempts`
- `training_sessions`
- `training_summaries`
- `training_summaries_user`

Os nomes reais podem ser alterados por variaveis de ambiente.

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
- marcar um simulado como concluido
- compartilhar esse estado entre dispositivos com a mesma conta

## Docker

Fluxo recomendado apos clonar o projeto:

1. Copie `.env.example` para `.env`
2. Ajuste a `.env` para o ambiente Docker
3. Se usar Firebase, coloque o arquivo de credenciais em `./secrets/firebase-service-account.json`
4. Se a base de questoes nao existir no banco Docker, coloque o backup em `./backups/cognix.backup`
5. Suba os containers:

```bash
docker compose up -d --build
```

6. Restaure a base:

```powershell
.\scripts\restore_db.ps1
```

7. Valide a API:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

Configuracao recomendada da `.env` para Docker:

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

Observacoes:

- no `DATABASE_URL`, use `db:5432`, nao `localhost`
- `POSTGRES_PORT` controla a porta exposta na sua maquina
- dentro da rede Docker, a API sempre acessa o banco por `db:5432`
- o backend ignora variaveis extras do `compose`, como `POSTGRES_DB` e `API_PORT`
- as tabelas internas sao criadas no startup, mas a tabela `questions` precisa vir do backup da base
- as pastas `backups/` e `secrets/` podem ir para o repositório vazias com `.gitkeep`, mas o conteudo real nao deve subir

Comandos uteis:

```bash
docker compose up --build
docker compose logs -f api
docker compose logs -f db
docker compose down
docker compose down -v
```

## Variaveis principais

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

- tabela de questoes: `questions`
- usuarios internos: `users`
- tentativas: `question_attempts`
- sessoes: `training_sessions`
- resumos globais: `training_summaries`
- resumos por usuario: `training_summaries_user`

## Autenticacao

Rotas protegidas esperam:

```http
Authorization: Bearer <firebase_id_token>
```

Fluxo:

- a API valida o token do Firebase
- extrai `uid`, `email`, `name` e `provider`
- sincroniza o usuario na tabela interna
- usa o `user_id` interno nas tabelas relacionais

## Datas e timezone

A API usa utilitarios centralizados em [`app/core/datetime_utils.py`](C:/Users/Nogueira/Desktop/cognix_api/app/core/datetime_utils.py).

Padrao atual:

- persistencia em UTC
- colunas internas com `DateTime(timezone=True)`
- serializacao consistente para respostas JSON

Isso foi feito para evitar deslocamentos de horario entre banco, backend e app Flutter.

## Documentacao da API

Para detalhes das rotas, payloads e respostas, use o Swagger da aplicacao:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Observacoes importantes

- nenhuma tabela nova foi criada para o agregado de sessoes; o overview usa a tabela `training_sessions` que ja existia
- a contagem de simulados concluidos depende do campo `completed` salvo dentro de `state_json`
- sessoes sao separadas por `disciplina + subcategoria`, evitando mistura entre simulados diferentes do mesmo usuario
- o backend foi ajustado para suportar restauracao e reabertura de resultados em multiplos dispositivos com a mesma conta

## Desenvolvimento

Comando util para validar rapidamente um arquivo Python alterado:

```bash
python -m py_compile app/api/endpoints/sessions.py
```

## Status atual do projeto

O backend ja atende bem um produto profissional em evolucao, com:

- autenticacao real
- dados persistidos por usuario
- sessoes de treino multi-dispositivo
- agregados para a interface
- resumos personalizados orientados por desempenho

Os proximos passos naturais sao:

- testes automatizados de endpoints
- observabilidade de erros e latencia
- agregados pedagÃ³gicos mais ricos por area e disciplina
- endurecimento de contratos de resposta da IA


