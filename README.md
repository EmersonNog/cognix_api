# Cognix API

Backend FastAPI da plataforma Cognix. Esta API concentra autenticação com Firebase, leitura da base de questões, registro de tentativas, persistência de sessões de treino e geração de resumos personalizados com IA.

## Docker

Fluxo recomendado após clonar o projeto:

1. Copie `.env.example` para `.env`
2. Ajuste a `.env` para o seu ambiente
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
 Schema |           Name            | Type  |  Owner
--------+---------------------------+-------+----------
 public | question_attempt_history  | table | postgres
 public | question_attempts         | table | postgres
 public | questions                 | table | postgres
 public | training_session_history  | table | postgres
 public | training_sessions         | table | postgres
 public | training_summaries        | table | postgres
 public | training_summaries_user   | table | postgres
 public | users                     | table | postgres
(8 rows)
```

7. Valide a API:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

Configuração recomendada da `.env` para Docker:

```env
POSTGRES_DB=cognix
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5432
API_PORT=8000
FIREBASE_CREDENTIALS=./secrets/firebase-service-account.json
GEMINI_API_KEY=coloque_sua_chave_aqui
GEMINI_MODEL=gemini-2.5-flash
```

Observações:

- o `DATABASE_URL` é montado automaticamente pelo `docker compose` para o container da API
- `POSTGRES_PORT` controla a porta exposta na sua máquina
- dentro da rede Docker, a API sempre acessa o banco por `db:5432`
- as tabelas internas usam os defaults definidos em `app/core/config.py`; só declare nomes customizados se quiser sobrescrever esses valores
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
- snapshot da última tentativa por `usuário + questão`
- histórico completo de tentativas para métricas e personalização
- sessões de treino persistidas por `usuário + disciplina + subcategoria`
- histórico de simulados concluídos para score, overview e reabertura de resultados
- restauração de simulados em andamento em vários dispositivos
- resumos e mapas mentais personalizados com base em desempenho real e contexto da subcategoria
- padronização de datas em UTC com serialização consistente para a API

## Estrutura de dados interna

No startup, a API garante a criação das tabelas internas abaixo:

- `users`
- `question_attempts`
- `question_attempt_history`
- `training_sessions`
- `training_session_history`
- `training_summaries`
- `training_summaries_user`

Os nomes reais podem ser alterados por variáveis de ambiente.

### `question_attempts`

Tabela snapshot usada para manter a última tentativa conhecida por `user_id + question_id`.

Campos principais:

- `user_id`
- `firebase_uid`
- `question_id`
- `selected_letter`
- `is_correct`
- `discipline`
- `subcategory`
- `answered_at`

Existe unicidade por:

- `user_id + question_id`

### `question_attempt_history`

Tabela append-only usada para registrar todas as respostas do usuário ao longo do tempo.

Campos principais:

- `user_id`
- `firebase_uid`
- `question_id`
- `selected_letter`
- `is_correct`
- `discipline`
- `subcategory`
- `answered_at`

Essa tabela é a base para:

- `active_days_last_30`
- contagem real de tentativas
- precisão histórica
- insights por subcategoria
- estatísticas dos resumos personalizados

### `training_sessions`

Tabela usada para persistir o estado atual do simulado.

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
- compartilhar esse estado entre dispositivos com a mesma conta
- manter um snapshot único por subcategoria para cada usuário

### `training_session_history`

Tabela append-only usada para registrar cada simulado concluído.

Campos principais:

- `user_id`
- `firebase_uid`
- `discipline`
- `subcategory`
- `session_key`
- `total_questions`
- `answered_questions`
- `correct_answers`
- `wrong_answers`
- `elapsed_seconds`
- `completed_at`

Essa tabela é a base para:

- `completed_sessions`
- cards e overview de ritmo do treino
- reabertura consistente da tela de resultados
- métricas do score ligadas a simulados concluídos

## Variáveis principais

O `.env.example` mantém só as variáveis essenciais para subir o ambiente Docker:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`
- `API_PORT`
- `FIREBASE_CREDENTIALS`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

Além disso, o backend expõe opções avançadas em [`app/core/config.py`](app/core/config.py), caso você queira sobrescrever nomes de tabelas ou outros defaults:

- `DATABASE_URL`
- `QUESTION_TABLE`
- `USERS_TABLE`
- `ATTEMPTS_TABLE`
- `ATTEMPT_HISTORY_TABLE`
- `SESSIONS_TABLE`
- `SESSION_HISTORY_TABLE`
- `SUMMARIES_TABLE`
- `USER_SUMMARIES_TABLE`
- `ALLOWED_ORIGINS`
- `FIREBASE_CREDENTIALS`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

Defaults atuais:

- tabela de questões: `questions`
- usuários internos: `users`
- snapshot de tentativas: `question_attempts`
- histórico de tentativas: `question_attempt_history`
- sessões atuais: `training_sessions`
- histórico de sessões concluídas: `training_session_history`
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

A API usa utilitários centralizados em [`app/core/datetime_utils.py`](app/core/datetime_utils.py).

Padrão atual:

- persistência em UTC
- colunas internas com `DateTime(timezone=True)`
- normalização com `ensure_utc(...)` antes de comparações sensíveis
- serialização consistente para respostas JSON

Isso foi feito para evitar deslocamentos de horário entre banco, backend e app Flutter.

## Documentação da API

Para detalhes das rotas, payloads e respostas, use o Swagger da aplicação:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Observações importantes

- o overview de sessões combina `training_sessions` (estado atual) com `training_session_history` (simulados concluídos)
- a contagem de simulados concluídos vem de `training_session_history`
- sessões são separadas por `disciplina + subcategoria`, evitando mistura entre simulados diferentes do mesmo usuário
- o backend persiste o histórico completo de tentativas para corrigir métricas de consistência, precisão e insights
- score e ritmo recente usam histórico real e podem regredir com inatividade
- o backend foi ajustado para suportar restauração e reabertura de resultados em múltiplos dispositivos com a mesma conta

## Desenvolvimento

Comandos úteis:

```bash
docker compose up --build
docker compose logs -f api
docker compose logs -f db
docker compose down
docker compose down -v
```
