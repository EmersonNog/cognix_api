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

## ProduÃ§Ã£o na VPS

Na VPS, o fluxo de produÃ§Ã£o usa estes arquivos:

- `.env.production`
- `docker-compose.prod.yml`
- `Dockerfile.prod`
- `deploy.sh`

Comando base da stack em produÃ§Ã£o:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ...
```

Esse formato Ã© importante porque o `docker compose` precisa ler a `.env.production` antes de montar os serviÃ§os.

### Comandos individuais

Subir ou recriar a stack inteira:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Use esse comando quando vocÃª mudar algo da infraestrutura, como:

- `docker-compose.prod.yml`
- `Dockerfile.prod`
- serviÃ§o do banco
- rede, volumes ou estrutura da stack

Subir ou recriar somente a API:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build api
```

Esse Ã© o comando padrÃ£o do dia a dia. Use quando vocÃª mudar:

- cÃ³digo Python em `app/`
- rotas
- serviÃ§os
- regras de negÃ³cio
- dependÃªncias da API

Ver status dos containers:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Ver logs da API:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f api
```

Ver logs do banco:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f db
```

Reiniciar apenas a API:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml restart api
```

Parar a stack sem apagar dados:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml down
```

AtenÃ§Ã£o:

- `down` para os containers, mas preserva os volumes
- `down -v` remove volumes; em produÃ§Ã£o isso pode apagar dados

### AtualizaÃ§Ã£o manual passo a passo

Fluxo recomendado sempre que vocÃª publicar uma nova versÃ£o no GitHub:

```bash
cd /home/cloudpanel/apps/cognix_api
git pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build api
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl https://api.cognix-hub.com/health
```

O que cada etapa faz:

1. `git pull`: baixa a versÃ£o mais nova do repositÃ³rio.
2. `up -d --build api`: rebuilda e recria sÃ³ a API.
3. `ps`: mostra se os containers ficaram saudÃ¡veis.
4. `curl`: valida se o endpoint `/health` continua respondendo.

### `deploy.sh`

O arquivo `deploy.sh` existe para vocÃª nÃ£o precisar decorar todos os comandos do deploy.

Uso padrÃ£o:

```bash
bash deploy.sh
```

Esse comando faz cinco coisas:

1. entra na pasta do projeto
2. roda `git pull --ff-only`
3. atualiza somente a API
4. mostra o status dos containers
5. testa `http://127.0.0.1:8000/health`

Quando vocÃª quiser recriar a stack inteira:

```bash
bash deploy.sh full
```

DiferenÃ§a entre os modos:

- `bash deploy.sh`: atualiza sÃ³ a API; esse Ã© o modo recomendado para o dia a dia
- `bash deploy.sh full`: recria a stack inteira; use quando mexer em infraestrutura

Primeiro uso na VPS:

```bash
cd /home/cloudpanel/apps/cognix_api
chmod +x deploy.sh
./deploy.sh
```

Se preferir, vocÃª tambÃ©m pode rodar assim:

```bash
bash deploy.sh
```

Regra simples para nunca se confundir:

- mudou cÃ³digo da API: `bash deploy.sh`
- mudou compose, Dockerfile ou algo da stack: `bash deploy.sh full`
- quer investigar problema: veja `ps`, `logs -f api` e o endpoint `/health`

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

## Guia Rapido de Deploy na VPS

Se voce estiver atualizando a API em producao, pense assim:

1. faz a mudanca no seu computador
2. sobe para o GitHub
3. entra na VPS
4. atualiza o repositorio
5. recria a API
6. testa o `/health`

O comando base da producao e sempre este:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ...
```

### Comandos individuais

Atualizar so a API:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build api
```

Use esse comando no dia a dia, quando voce mudar:

- codigo Python
- rotas
- servicos
- regras de negocio
- dependencias da API

Atualizar a stack inteira:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Use esse comando quando voce mudar:

- `docker-compose.prod.yml`
- `Dockerfile.prod`
- configuracao do banco
- algo da infraestrutura da stack

Ver status:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Ver logs da API:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f api
```

Ver logs do banco:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f db
```

Reiniciar so a API:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml restart api
```

Parar tudo sem apagar dados:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml down
```

Atencao:

- `down` para os containers, mas mantem os volumes
- `down -v` remove volumes; em producao isso pode apagar dados

### Fluxo manual completo

Quando voce publicar uma nova versao:

```bash
cd /home/cloudpanel/apps/cognix_api
git pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build api
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl https://api.cognix-hub.com/health
```

### `deploy.sh`

O arquivo `deploy.sh` existe para voce nao precisar decorar tudo.

Uso normal:

```bash
bash deploy.sh
```

Esse comando:

1. entra na pasta do projeto
2. roda `git pull --ff-only`
3. atualiza somente a API
4. mostra o status dos containers
5. testa `http://127.0.0.1:8000/health`

Quando voce quiser recriar a stack inteira:

```bash
bash deploy.sh full
```

Primeiro uso na VPS:

```bash
cd /home/cloudpanel/apps/cognix_api
chmod +x deploy.sh
./deploy.sh
```

Regra simples para nunca se confundir:

- mudou codigo da API: `bash deploy.sh`
- mudou compose, Dockerfile ou algo da stack: `bash deploy.sh full`
- quer investigar problema: veja `ps`, `logs -f api` e o endpoint `/health`

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
