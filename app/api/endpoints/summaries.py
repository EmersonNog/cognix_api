import json
import logging
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.datetime_utils import to_api_iso, utc_now
from app.db.models import (
    get_attempts_table,
    get_questions_table,
    get_summaries_table,
    get_user_summaries_table,
)
from app.db.session import engine

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_SUMMARY_NODES = 4
MAX_ITEMS_PER_NODE = 3


def _stats_payload(stats: dict | None) -> dict:
    if not stats:
        return {
            'total_attempts': 0,
            'total_correct': 0,
            'accuracy_percent': 0.0,
            'last_attempt_at': None,
        }
    return {
        'total_attempts': stats.get('total_attempts', 0),
        'total_correct': stats.get('total_correct', 0),
        'accuracy_percent': stats.get('accuracy_percent', 0.0),
        'last_attempt_at': stats.get('latest_attempt_at'),
    }


def _require_authenticated_user(user_claims: dict) -> tuple[int, str]:
    internal = user_claims.get('internal_user') or {}
    user_id = internal.get('id')
    firebase_uid = user_claims.get('uid')
    if not user_id or not firebase_uid:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return user_id, firebase_uid


def _require_user_id(user_claims: dict) -> int:
    internal = user_claims.get('internal_user') or {}
    user_id = internal.get('id')
    if not user_id:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return user_id


def _load_summary_payload(payload_json: str) -> dict:
    try:
        return _normalize_summary_payload(json.loads(payload_json))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail='Invalid summary JSON')


def _attach_stats(payload: dict, stats: dict | None) -> dict:
    response = dict(payload)
    response['stats'] = _stats_payload(stats)
    return response


def _normalize_required_summary_fields(payload: dict) -> tuple[str, str, list, str | None]:
    discipline = payload.get('discipline')
    subcategory = payload.get('subcategory')
    nodes = payload.get('nodes')
    title = payload.get('title')

    if not discipline or not str(discipline).strip():
        raise HTTPException(status_code=400, detail='discipline is required')
    if not subcategory or not str(subcategory).strip():
        raise HTTPException(status_code=400, detail='subcategory is required')
    if not isinstance(nodes, list) or not nodes:
        raise HTTPException(status_code=400, detail='nodes is required')

    return str(discipline).strip(), str(subcategory).strip(), nodes, title


def _upsert_base_summary(db: Session, discipline: str, subcategory: str, payload: dict) -> None:
    summaries = get_summaries_table(settings.summaries_table)
    now = utc_now()
    insert_stmt = pg_insert(summaries).values(
        discipline=discipline,
        subcategory=subcategory,
        payload_json=json.dumps(payload, ensure_ascii=True),
        created_at=now,
        updated_at=now,
    )
    db.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=[summaries.c.discipline, summaries.c.subcategory],
            set_={
                'payload_json': json.dumps(payload, ensure_ascii=True),
                'updated_at': now,
            },
        )
    )
    db.commit()


def _insert_base_summary_if_missing(db: Session, discipline: str, subcategory: str, payload: dict) -> None:
    summaries = get_summaries_table(settings.summaries_table)
    now = utc_now()
    insert_stmt = pg_insert(summaries).values(
        discipline=discipline,
        subcategory=subcategory,
        payload_json=json.dumps(payload, ensure_ascii=True),
        created_at=now,
        updated_at=now,
    )
    db.execute(
        insert_stmt.on_conflict_do_nothing(
            index_elements=[summaries.c.discipline, summaries.c.subcategory]
        )
    )
    db.commit()


def _upsert_user_summary(
    db: Session,
    user_id: int,
    firebase_uid: str,
    discipline: str,
    subcategory: str,
    payload: dict,
) -> None:
    table = get_user_summaries_table(settings.user_summaries_table)
    now = utc_now()
    insert_stmt = pg_insert(table).values(
        user_id=user_id,
        firebase_uid=firebase_uid,
        discipline=discipline,
        subcategory=subcategory,
        payload_json=json.dumps(payload, ensure_ascii=True),
        created_at=now,
        updated_at=now,
    )
    db.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=[table.c.user_id, table.c.discipline, table.c.subcategory],
            set_={
                'payload_json': json.dumps(payload, ensure_ascii=True),
                'updated_at': now,
            },
        )
    )
    db.commit()


def _generate_personalized_summary(
    db: Session,
    user_id: int,
    discipline: str,
    subcategory: str,
) -> tuple[dict, dict]:
    stats = _fetch_user_stats(db, user_id, discipline, subcategory)
    samples = _fetch_question_samples(db, discipline, subcategory)
    payload = _normalize_summary_payload(
        _generate_with_gemini(discipline, subcategory, samples, stats)
    )
    return payload, stats


def _default_summary(discipline: str, subcategory: str) -> dict:
    return _normalize_summary_payload(
        {
            'title': f'{subcategory} - Resumo',
            'discipline': discipline,
            'subcategory': subcategory,
            'nodes': [
                {
                    'title': 'Conceitos-chave',
                    'items': [
                        'Definicoes essenciais',
                        'Grandezas e unidades',
                        'Relacoes fundamentais',
                    ],
                },
                {
                    'title': 'Formulas e Leis',
                    'items': [
                        'Formulas principais',
                        'Condicoes de uso',
                        'Observacoes rapidas',
                    ],
                },
                {
                    'title': 'Interpretacao',
                    'items': [
                        'Leitura de graficos',
                        'Palavras-chave do enunciado',
                        'Unidades no contexto',
                    ],
                },
                {
                    'title': 'Estrategias',
                    'items': [
                        'Passo a passo tipico',
                        'Checagem de sinais',
                        'Revisao de alternativas',
                    ],
                },
                {
                    'title': 'Erros comuns',
                    'items': [
                        'Troca de unidades',
                        'Aplicacao fora do dominio',
                        'Interpretacao incorreta',
                    ],
                },
            ],
        }
    )


def _trim_text(value: str, limit: int) -> str:
    text = ' '.join(value.split()).strip()
    if len(text) <= limit:
        return text
    return f'{text[: limit - 3].rstrip()}...'


def _clean_text(value: str) -> str:
    return ' '.join(value.split()).strip()


def _normalize_summary_payload(payload: dict) -> dict:
    raw_nodes = payload.get('nodes')
    normalized_nodes = []

    if isinstance(raw_nodes, list):
        for raw_node in raw_nodes[:MAX_SUMMARY_NODES]:
            if not isinstance(raw_node, dict):
                continue

            title = _trim_text(str(raw_node.get('title') or ''), 48)
            raw_items = raw_node.get('items')
            if not title or not isinstance(raw_items, list):
                continue

            items = []
            for raw_item in raw_items[:MAX_ITEMS_PER_NODE]:
                item = _clean_text(str(raw_item or ''))
                if item:
                    items.append(item)

            if items:
                normalized_nodes.append(
                    {
                        'title': title,
                        'items': items,
                    }
                )

    return {
        'title': _trim_text(
            str(payload.get('title') or payload.get('subcategory') or 'Resumo'),
            80,
        ),
        'discipline': str(payload.get('discipline') or ''),
        'subcategory': str(payload.get('subcategory') or ''),
        'nodes': normalized_nodes,
    }


def _gemini_available() -> bool:
    return bool(settings.gemini_api_key and settings.gemini_api_key.strip())


def _build_schema() -> dict:
    return {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'discipline': {'type': 'string'},
            'subcategory': {'type': 'string'},
            'nodes': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'items': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': ['title', 'items'],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['title', 'discipline', 'subcategory', 'nodes'],
        'additionalProperties': False,
    }


def _fetch_question_samples(
    db: Session,
    discipline: str,
    subcategory: str,
    question_ids: list[int] | None = None,
) -> list[dict]:
    table = get_questions_table(engine, settings.question_table)
    if 'disciplina' not in table.c or 'subcategoria' not in table.c:
        return []

    if question_ids:
        stmt = select(table).where(table.c.id.in_(question_ids)).limit(8)
    else:
        stmt = (
            select(table)
            .where(table.c.disciplina == discipline)
            .where(table.c.subcategoria == subcategory)
            .limit(8)
        )

    rows = db.execute(stmt).mappings().all()
    samples = []
    for row in rows:
        alternatives = []
        for key in (
            'alternativas',
            'alternativa_a',
            'alternativa_b',
            'alternativa_c',
            'alternativa_d',
            'alternativa_e',
        ):
            value = row.get(key)
            if value is not None and str(value).strip():
                alternatives.append(str(value).strip())
        samples.append(
            {
                'id': row.get('id'),
                'enunciado': row.get('enunciado'),
                'ano': row.get('ano'),
                'alternativas': alternatives[:5],
            }
        )
    return samples


def _derive_error_patterns(stats: dict) -> list[str]:
    patterns = []
    accuracy = float(stats.get('accuracy_percent') or 0.0)

    if accuracy < 40:
        patterns.append('Baixa precisao geral na subcategoria, indicando falhas de base.')
    elif accuracy < 65:
        patterns.append('Desempenho instavel, com lacunas em conceitos centrais.')

    return patterns[:4]


def _fetch_user_stats(db: Session, user_id: int, discipline: str, subcategory: str) -> dict:
    attempts = get_attempts_table(settings.attempts_table)
    base_filters = (
        (attempts.c.user_id == user_id)
        & (attempts.c.discipline == discipline)
        & (attempts.c.subcategory == subcategory)
    )

    total = db.execute(
        select(func.count()).select_from(attempts).where(base_filters)
    ).scalar() or 0
    correct = db.execute(
        select(func.count())
        .select_from(attempts)
        .where(base_filters & (attempts.c.is_correct.is_(True)))
    ).scalar() or 0

    incorrect_counts = db.execute(
        select(attempts.c.question_id, func.count().label('qty'))
        .where(base_filters & (attempts.c.is_correct.is_(False)))
        .group_by(attempts.c.question_id)
        .order_by(func.count().desc())
        .limit(8)
    ).all()
    incorrect_ids = [row[0] for row in incorrect_counts if row[0] is not None]
    accuracy = round((correct / total) * 100, 1) if total else 0.0
    latest_attempt = _latest_attempt_at(db, user_id, discipline, subcategory)

    stats = {
        'total_attempts': total,
        'total_correct': correct,
        'accuracy_percent': accuracy,
        'incorrect_question_ids': incorrect_ids,
        'latest_attempt_at': to_api_iso(latest_attempt),
    }
    stats['error_patterns'] = _derive_error_patterns(stats)
    return stats


def _fetch_question_total(db: Session, discipline: str, subcategory: str) -> int:
    table = get_questions_table(engine, settings.question_table)
    if 'disciplina' not in table.c or 'subcategoria' not in table.c:
        return 0

    stmt = (
        select(func.count())
        .select_from(table)
        .where(table.c.disciplina == discipline)
        .where(table.c.subcategoria == subcategory)
    )
    return int(db.execute(stmt).scalar() or 0)


def _latest_attempt_at(db: Session, user_id: int, discipline: str, subcategory: str):
    attempts = get_attempts_table(settings.attempts_table)
    stmt = (
        select(func.max(attempts.c.answered_at))
        .where(attempts.c.user_id == user_id)
        .where(attempts.c.discipline == discipline)
        .where(attempts.c.subcategory == subcategory)
    )
    return db.execute(stmt).scalar()


def _generate_with_gemini(
    discipline: str,
    subcategory: str,
    samples: list[dict],
    stats: dict,
) -> dict:
    prompt = (
        'Crie um mapa mental em JSON para estudo. '
        'Use linguagem clara, objetiva e util para revisao. '
        'O conteudo precisa cobrir os pontos mais importantes da subcategoria, '
        'sem ficar superficial, mas mantendo formato enxuto para mobile. '
        'Inclua de 4 a 5 nos principais, cada um com no maximo 3 itens. '
        'Cada no deve representar um bloco realmente importante do tema. '
        'Cada item deve ser curto, especifico, relevante para prova e revisao, '
        'e idealmente caber em uma frase breve sem precisar de reticencias. '
        'Personalize com foco no desempenho real do aluno usando os dados informados.\n\n'
        'Priorize nesta ordem:\n'
        '1. conceitos centrais da subcategoria;\n'
        '2. formulas, relacoes ou interpretacoes essenciais;\n'
        '3. pontos de confusao e fragilidades sugeridos pelo desempenho;\n'
        '4. aplicacoes ou leituras que mais costumam aparecer nas questoes.\n\n'
        'Se houver pouco desempenho do aluno, cubra o nucleo do assunto. '
        'Se houver sinais de dificuldade, destaque esses pontos sem deixar de cobrir a base.\n\n'
        'Nao use placeholders, colchetes ou textos genericos.\n'
        'Nao crie detalhes irrelevantes ou excessivamente especificos.\n'
        'Use termos reais das amostras, da subcategoria e do desempenho do aluno.\n\n'
        f'Disciplina: {discipline}\n'
        f'Subcategoria: {subcategory}\n'
        f'Desempenho recente do aluno: {stats}\n'
        f'Padroes de erro mais frequentes: {stats.get("error_patterns")}\n'
        f'Amostras de questoes (enunciados): {samples}\n'
        'Retorne apenas o JSON no formato exigido.'
    )

    payload = {
        'contents': [
            {
                'parts': [
                    {'text': prompt},
                ]
            }
        ],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'responseJsonSchema': _build_schema(),
            'temperature': 0.2,
        },
    }

    endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{settings.gemini_model}:generateContent'
    )

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'x-goog-api-key': settings.gemini_api_key,
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode('utf-8')
        except Exception:
            body = ''
        raise HTTPException(
            status_code=502,
            detail=f'Gemini error: {exc.code} {body}'.strip(),
        )
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f'Gemini unavailable: {exc}')

    data = json.loads(raw)
    candidates = data.get('candidates') or []
    for candidate in candidates:
        content = candidate.get('content') or {}
        parts = content.get('parts') or []
        for part in parts:
            text = part.get('text')
            if text:
                return _normalize_summary_payload(json.loads(text))

    raise HTTPException(status_code=500, detail='Invalid Gemini response')

@router.get('', dependencies=[Depends(get_current_user)])
def get_summary(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    summaries = get_summaries_table(settings.summaries_table)
    row = db.execute(
        select(summaries)
        .where(summaries.c.discipline == discipline)
        .where(summaries.c.subcategory == subcategory)
    ).mappings().first()

    if row is not None:
        payload = _load_summary_payload(row['payload_json'])
        return _attach_stats(payload, None)

    payload = _default_summary(discipline, subcategory)
    _insert_base_summary_if_missing(db, discipline, subcategory, payload)
    return _attach_stats(payload, None)


@router.get('/personal', dependencies=[Depends(get_current_user)])
def get_personal_summary(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    auto_generate: bool = Query(True),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    logger.info(
        'Summary request discipline=%s subcategory=%s auto_generate=%s',
        discipline,
        subcategory,
        auto_generate,
    )
    user_id, firebase_uid = _require_authenticated_user(user_claims)
    stats = _fetch_user_stats(db, user_id, discipline, subcategory)

    table = get_user_summaries_table(settings.user_summaries_table)
    row = db.execute(
        select(table)
        .where(table.c.user_id == user_id)
        .where(table.c.discipline == discipline)
        .where(table.c.subcategory == subcategory)
    ).mappings().first()

    if row is not None:
        latest_attempt = _latest_attempt_at(db, user_id, discipline, subcategory)
        if latest_attempt and row['updated_at'] and latest_attempt <= row['updated_at']:
            payload = _load_summary_payload(row['payload_json'])
            return _attach_stats(payload, stats)

    if not auto_generate or not _gemini_available():
        return get_summary(discipline=discipline, subcategory=subcategory, db=db)

    payload, stats = _generate_personalized_summary(db, user_id, discipline, subcategory)
    _upsert_user_summary(db, user_id, firebase_uid, discipline, subcategory, payload)
    return _attach_stats(payload, stats)


@router.get('/progress', dependencies=[Depends(get_current_user)])
def get_training_progress(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id = _require_user_id(user_claims)
    stats = _fetch_user_stats(db, user_id, discipline, subcategory)
    total_questions = _fetch_question_total(db, discipline, subcategory)
    answered_questions = int(stats.get('total_attempts') or 0)
    progress = (answered_questions / total_questions) if total_questions else 0.0

    return {
        'discipline': discipline,
        'subcategory': subcategory,
        'answered_questions': answered_questions,
        'total_questions': total_questions,
        'progress': progress,
    }


@router.post('/auto_generate', dependencies=[Depends(get_current_user)])
def auto_generate_summary(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = _require_authenticated_user(user_claims)

    if not _gemini_available():
        raise HTTPException(status_code=500, detail='Gemini not configured')

    payload, stats = _generate_personalized_summary(db, user_id, discipline, subcategory)
    _upsert_user_summary(db, user_id, firebase_uid, discipline, subcategory, payload)
    return _attach_stats(payload, stats)


@router.post('', dependencies=[Depends(get_current_user)])
def upsert_summary(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    discipline, subcategory, nodes, title = _normalize_required_summary_fields(payload)

    normalized_payload = _normalize_summary_payload(
        {
            'title': title or f'{subcategory} - Resumo',
            'discipline': discipline,
            'subcategory': subcategory,
            'nodes': nodes,
        }
    )
    _upsert_base_summary(db, discipline, subcategory, normalized_payload)
    return {'status': 'ok'}


@router.post('/bootstrap', dependencies=[Depends(get_current_user)])
def bootstrap_summaries(db: Session = Depends(get_db)) -> dict:
    table = get_questions_table(engine, settings.question_table)
    if 'disciplina' not in table.c or 'subcategoria' not in table.c:
        raise HTTPException(status_code=500, detail='Missing columns for bootstrap')

    rows = db.execute(
        select(table.c.disciplina, table.c.subcategoria)
        .where(table.c.disciplina.is_not(None))
        .where(table.c.subcategoria.is_not(None))
        .distinct()
    ).all()

    summaries = get_summaries_table(settings.summaries_table)
    now = utc_now()
    created = 0
    for discipline, subcategory in rows:
        if not str(discipline).strip() or not str(subcategory).strip():
            continue
        payload = _default_summary(str(discipline).strip(), str(subcategory).strip())
        insert_stmt = pg_insert(summaries).values(
            discipline=str(discipline).strip(),
            subcategory=str(subcategory).strip(),
            payload_json=json.dumps(payload, ensure_ascii=True),
            created_at=now,
            updated_at=now,
        )
        result = db.execute(
            insert_stmt.on_conflict_do_nothing(
                index_elements=[summaries.c.discipline, summaries.c.subcategory]
            )
        )
        if result.rowcount:
            created += 1
    db.commit()
    return {'status': 'ok', 'created': created}
