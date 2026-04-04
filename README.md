# Cognix API

Backend FastAPI da plataforma Cognix. A API centraliza autenticação com Firebase, leitura da base de questões, registro de tentativas, persistência de sessões de treino, score de perfil com ritmo recente, economia com moedas e avatares, e geração de resumos personalizados com IA.

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

O script copia `./backups/cognix.backup` para o container `cognix_db`, executa `pg_restore --clean --if-exists` e valida a presença da tabela `questions`.

7. Confira as tabelas no banco:

```powershell
docker compose exec db psql -U postgres -d cognix -c "\dt"
```

Saída esperada:

```text
                    List of tables
 Schema |           Name           | Type  |  Owner
--------+--------------------------+-------+----------
 public | question_attempt_history | table | postgres
 public | question_attempts        | table | postgres
 public | questions                | table | postgres
 public | training_session_history | table | postgres
 public | training_sessions        | table | postgres
 public | training_summaries       | table | postgres
 public | training_summaries_user  | table | postgres
 public | user_avatar_inventory    | table | postgres
 public | user_coin_ledger         | table | postgres
 public | users                    | table | postgres
(10 rows)
```

8. Valide a API:

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
GEMINI_MODEL=gemini-3-flash-preview
```

Observações:

- o `DATABASE_URL` é montado automaticamente pelo `docker compose` para o container da API
- `POSTGRES_PORT` controla a porta exposta na sua máquina
- dentro da rede Docker, a API sempre acessa o banco por `db:5432`
- as tabelas internas são criadas no startup, mas a tabela `questions` precisa vir do backup da base
- as pastas `backups/` e `secrets/` podem ir para o repositório vazias com `.gitkeep`, mas o conteúdo real não deve subir

## Stack

- Python 3.10+ no código
- imagem Docker `python:3.13-slim`
- FastAPI
- SQLAlchemy 2
- PostgreSQL
- Firebase Admin SDK
- Gemini API via HTTP

## Principais recursos

- validação de `Firebase ID Token` em rotas protegidas
- sincronização automática do usuário Firebase para a tabela interna `users`
- listagem e filtro de questões por disciplina, subcategoria, ano e busca textual
- remoção automática do campo sensível `gabarito` nas respostas de questões
- registro de tentativas com snapshot da última resposta e histórico completo append-only
- recompensa em moedas apenas na primeira resposta de cada `usuário + questão`
- inventário de avatares e seleção de avatar equipado no perfil
- score de perfil com breakdown, nível, consistência e `recent_index`
- sessões de treino persistidas por `usuário + disciplina + subcategoria`
- histórico de simulados concluídos para score, overview e reabertura de resultados
- resumos base por subcategoria e resumos personalizados por usuário
- geração opcional de mapas mentais personalizados com Gemini
- persistência e serialização de datas em UTC

## Estrutura de dados interna

No startup, a API garante a criação das tabelas internas abaixo:

- `users`
- `question_attempts`
- `question_attempt_history`
- `training_sessions`
- `training_session_history`
- `training_summaries`
- `training_summaries_user`
- `user_coin_ledger`
- `user_avatar_inventory`

Os nomes reais podem ser alterados por variáveis de ambiente.

### `users`

Tabela de usuários internos sincronizada a partir do token do Firebase.

Campos relevantes:

- `firebase_uid`
- `email`
- `display_name`
- `provider`
- `coins_half_units`
- `equipped_avatar_seed`
- `created_at`
- `updated_at`

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
- cálculo de `score` e `recent_index`

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

Observação:

- um registro em `training_session_history` só é criado quando `state.completed == true` no payload salvo em `/sessions`

### `training_summaries`

Tabela de resumo base por `discipline + subcategory`.

Campos principais:

- `discipline`
- `subcategory`
- `payload_json`
- `created_at`
- `updated_at`

### `training_summaries_user`

Tabela de resumo personalizado por `user_id + discipline + subcategory`.

Campos principais:

- `user_id`
- `firebase_uid`
- `discipline`
- `subcategory`
- `payload_json`
- `created_at`
- `updated_at`

### `user_coin_ledger`

Tabela append-only do extrato de moedas do usuário.

Campos principais:

- `user_id`
- `firebase_uid`
- `reason`
- `delta_half_units`
- `balance_after_half_units`
- `question_id`
- `avatar_seed`
- `created_at`

Hoje os motivos gravados pelo backend incluem:

- `question_answer_reward`
- `avatar_purchase`

### `user_avatar_inventory`

Tabela de inventário de avatares desbloqueados ou comprados.

Campos principais:

- `user_id`
- `firebase_uid`
- `avatar_seed`
- `acquired_via`
- `cost_half_units`
- `created_at`
- `updated_at`

Existe unicidade por:

- `user_id + avatar_seed`

## Variáveis principais

O `.env.example` mantém as variáveis mínimas para subir o ambiente Docker:

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
- `USER_COIN_LEDGER_TABLE`
- `USER_AVATAR_INVENTORY_TABLE`
- `ALLOWED_ORIGINS`
- `FIREBASE_CREDENTIALS`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

Defaults atuais no código:

- tabela de questões: `questions`
- usuários internos: `users`
- snapshot de tentativas: `question_attempts`
- histórico de tentativas: `question_attempt_history`
- sessões atuais: `training_sessions`
- histórico de sessões concluídas: `training_session_history`
- resumos globais: `training_summaries`
- resumos por usuário: `training_summaries_user`
- extrato de moedas: `user_coin_ledger`
- inventário de avatares: `user_avatar_inventory`
- CORS: `["*"]`
- `GEMINI_MODEL`: `gemini-3-flash-preview`

Exemplo de `ALLOWED_ORIGINS`:

```env
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8080"]
```

## Autenticação

Todas as rotas da API exigem autenticação, exceto `GET /health`.

Rotas protegidas esperam:

```http
Authorization: Bearer <firebase_id_token>
```

Fluxo:

- a API valida o token do Firebase
- extrai `uid`, `email`, `name` e `provider`
- sincroniza o usuário na tabela interna
- usa o `user_id` interno nas tabelas relacionais

Observação:

- hoje não existe checagem adicional de papel/perfil por rota; o controle atual é apenas por token válido

## Rotas principais

### `users`

- `POST /users/sync`: valida o token e devolve o usuário interno sincronizado
- `GET /users/profile`: retorna score, breakdowns, progresso geral, moedas, avatar equipado, avatares possuídos e catálogo da loja
- `POST /users/avatar/select`: equipa um avatar já possuído ou compra/equipa um novo avatar com base em `avatar_seed`

### `questions`

- `GET /questions`: lista questões com `limit`, `offset`, `subject`, `subcategory`, `year`, `search` e `include_total`
- `GET /questions/disciplines`: lista disciplinas distintas da base
- `GET /questions/subcategories`: lista subcategorias e total por subcategoria, com filtro opcional por disciplina
- `GET /questions/by_ids`: busca por ids em ordem preservada via `ids=1,2,3`
- `GET /questions/{question_id}`: retorna uma questão específica

Observação:

- o backend remove o campo `gabarito` de todas as respostas de questões

### `attempts`

- `POST /attempts`: registra a tentativa no histórico, atualiza o snapshot da última resposta e retorna `is_correct`, `correct_letter` e estado de moedas

Observação:

- moedas são concedidas apenas quando a questão ainda não possui tentativa anterior para aquele usuário

### `sessions`

- `POST /sessions`: salva ou atualiza o estado do treino para `discipline + subcategory`
- `GET /sessions`: recupera o estado salvo de uma sessão
- `GET /sessions/overview`: combina sessões em andamento com histórico de concluídas
- `DELETE /sessions`: remove o snapshot atual da sessão

### `summaries`

- `GET /summaries`: retorna o resumo base da subcategoria e cria um fallback padrão se ele não existir
- `GET /summaries/personal`: retorna resumo personalizado do usuário; se não houver sessão concluída, devolve um payload bloqueado
- `GET /summaries/progress`: retorna progresso da subcategoria com base em tentativas e total de questões
- `POST /summaries/auto_generate`: força a geração do resumo personalizado via Gemini
- `POST /summaries`: cria ou atualiza manualmente o resumo base
- `POST /summaries/bootstrap`: cria resumos base padrão para todos os pares distintos de `discipline + subcategory`

Observações:

- `GET /summaries/personal` só tenta gerar com IA quando `auto_generate=true` e `GEMINI_API_KEY` está configurada
- `POST /summaries/auto_generate` retorna `409` se o usuário ainda não concluiu um simulado da subcategoria
- se o Gemini não estiver configurado, `GET /summaries/personal` faz fallback para o resumo base, mas `POST /summaries/auto_generate` falha com `500`

## Datas e timezone

A API usa utilitários centralizados em [`app/core/datetime_utils.py`](app/core/datetime_utils.py).

Padrão atual:

- persistência em UTC
- colunas internas com `DateTime(timezone=True)`
- normalização com `ensure_utc(...)` antes de comparações sensíveis
- serialização consistente para respostas JSON com `isoformat()`

Isso evita deslocamentos de horário entre banco, backend e app Flutter.

## Documentação da API

Para detalhes das rotas, payloads e respostas, use o Swagger da aplicação:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Desenvolvimento

Comandos úteis:

```bash
docker compose up --build
docker compose logs -f api
docker compose logs -f db
docker compose down
docker compose down -v
python -m unittest discover -s tests
```

Cobertura atual de testes unitários incluída no repositório:

- helpers da economia (`coins_from_half_units` e composição da loja de avatares)
- cálculo de `recent_index`
- estabilidade do score quando apenas o índice recente varia
