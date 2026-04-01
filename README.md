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

## Configuracao

1. Copie `.env.example` para `.env`
2. Ajuste as variaveis necessarias
3. Instale as dependencias:

```bash
pip install -r requirements.txt
```

4. Rode a API:

```bash
python -m uvicorn app.main:app --reload
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

## Endpoints

### Sistema

- `GET /health`

### Usuarios

- `POST /users/sync`

### Questoes

- `GET /questions`
  - query params: `limit`, `offset`, `subject`, `subcategory`, `year`, `search`, `include_total`
- `GET /questions/disciplines`
- `GET /questions/subcategories`
  - query params: `discipline`
- `GET /questions/by_ids`
  - query params: `ids`
- `GET /questions/{question_id}`

Observacoes:

- o campo sensivel `gabarito` nao e retornado
- a tabela de questoes e refletida dinamicamente a partir de `QUESTION_TABLE`
- a reflexao da tabela foi cacheada para evitar custo repetido por request

### Tentativas

- `POST /attempts`

Responsabilidades:

- salvar resposta escolhida pelo usuario
- persistir `is_correct`
- registrar `discipline` e `subcategory`
- atualizar indicadores usados por progresso e resumos

### Sessoes de treino

- `POST /sessions`
- `GET /sessions`
- `DELETE /sessions`
- `GET /sessions/overview`

#### `POST /sessions`

Salva ou atualiza a sessao do usuario para uma subcategoria.

Payload esperado:

```json
{
  "discipline": "Linguagens, codigos e suas tecnologias",
  "subcategory": "Lingua Estrangeira",
  "state": {
    "currentIndex": 3,
    "questionIds": [10, 20, 30],
    "lastSubmitted": {"10": "A"},
    "elapsedSeconds": 182
  }
}
```

#### `GET /sessions`

Retorna a sessao persistida de uma subcategoria para o usuario autenticado.

#### `DELETE /sessions`

Limpa a sessao persistida da subcategoria.

#### `GET /sessions/overview`

Retorna um agregado para alimentar o app com dados reais do usuario:

- `completed_sessions`
- `in_progress_sessions`
- `latest_session`

`latest_session` inclui:

- `discipline`
- `subcategory`
- `completed`
- `answered_questions`
- `total_questions`
- `progress`
- `updated_at`

Esse endpoint e usado pelo app para:

- mostrar quantos simulados ja foram concluidos
- recuperar o ultimo simulado em andamento ou concluido
- manter o comportamento consistente entre varios dispositivos da mesma conta

### Resumos e mapa mental

- `GET /summaries`
- `GET /summaries/personal`
- `GET /summaries/progress`

#### `GET /summaries`

Retorna um resumo base da subcategoria.

#### `GET /summaries/personal`

Retorna um resumo personalizado para o usuario.

Comportamento atual:

- usa dados reais de desempenho em `question_attempts`
- considera `discipline` e `subcategory`
- usa amostras reais de questoes da base
- pode gerar automaticamente via Gemini quando necessario
- normaliza a saida para um formato compacto e compativel com mobile

Limites atuais do payload:

- ate `4` nos principais
- ate `3` itens por no

#### `GET /summaries/progress`

Retorna progresso percentual por subcategoria:

- `answered_questions`
- `total_questions`
- `progress`

## Como o mapa mental e gerado

O backend atual nao usa um agente autonomo. O fluxo e:

1. consulta desempenho do usuario no banco
2. busca amostras reais da subcategoria
3. monta um prompt estruturado
4. chama o Gemini
5. normaliza o JSON de resposta
6. salva o resumo na base

Fallback:

- se a Gemini API nao estiver disponivel, a API retorna um resumo padrao

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
- agregados pedagógicos mais ricos por area e disciplina
- endurecimento de contratos de resposta da IA
