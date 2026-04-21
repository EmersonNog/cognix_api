import hashlib
import json
from datetime import datetime
from datetime import timedelta
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import to_api_iso, utc_now
from app.db.models import get_users_table


def build_profile_ai_insight(
    db: Session,
    user_id: int,
    metrics: dict,
    score_data: dict,
) -> dict | None:
    fingerprint = _build_fingerprint(metrics, score_data)
    cached = _load_cached_insight(db, user_id=user_id)

    if cached and cached['fingerprint'] == fingerprint and not cached['expired']:
        return _serialize_insight_result(
            cached['insight'],
            generated_at=cached['generated_at'],
            cache_hit=True,
        )

    if not _gemini_available():
        if not cached:
            return None
        return _serialize_insight_result(
            cached['insight'],
            generated_at=cached['generated_at'],
            cache_hit=True,
        )

    prompt = _build_prompt(metrics, score_data)
    try:
        insight = _generate_insight(prompt)
    except Exception:
        if not cached:
            return None
        return _serialize_insight_result(
            cached['insight'],
            generated_at=cached['generated_at'],
            cache_hit=True,
        )

    if insight is None:
        if not cached:
            return None
        return _serialize_insight_result(
            cached['insight'],
            generated_at=cached['generated_at'],
            cache_hit=True,
        )

    generated_at = _store_cached_insight(
        db,
        user_id=user_id,
        fingerprint=fingerprint,
        insight=insight,
    )
    return _serialize_insight_result(
        insight,
        generated_at=generated_at,
        cache_hit=False,
    )


def _build_fingerprint(metrics: dict, score_data: dict) -> str:
    strongest = metrics.get('strongest_subcategory') or {}
    weakest = metrics.get('weakest_subcategory') or {}
    question_rows = metrics.get('question_rows') or []

    payload = {
        'insight_schema_version': 2,
        'score': score_data.get('score'),
        'level': score_data.get('level'),
        'recent_index': score_data.get('recent_index'),
        'questions_answered_bucket': int((metrics.get('total_questions') or 0) / 10),
        'accuracy_percent_bucket': round(float(metrics.get('accuracy_percent') or 0.0), 0),
        'completed_sessions': metrics.get('completed_sessions'),
        'active_days_last_30': metrics.get('active_days_last_30'),
        'current_streak_days': metrics.get('current_streak_days'),
        'attention_subcategories_count': metrics.get('attention_subcategories_count'),
        'top_disciplines': [
            {
                'discipline': row[0],
                'count_bucket': int((int(row[1] or 0)) / 5),
            }
            for row in question_rows[:4]
            if row and row[0]
        ],
        'strongest_subcategory': {
            'discipline': strongest.get('discipline'),
            'subcategory': strongest.get('subcategory'),
            'accuracy_percent_bucket': round(
                float(strongest.get('accuracy_percent') or 0.0),
                0,
            ),
        },
        'weakest_subcategory': {
            'discipline': weakest.get('discipline'),
            'subcategory': weakest.get('subcategory'),
            'accuracy_percent_bucket': round(
                float(weakest.get('accuracy_percent') or 0.0),
                0,
            ),
        },
    }

    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _load_cached_insight(db: Session, *, user_id: int) -> dict | None:
    users = get_users_table(settings.users_table)
    row = db.execute(
        select(
            users.c.profile_ai_insight_json,
            users.c.profile_ai_insight_fingerprint,
            users.c.profile_ai_insight_generated_at,
        ).where(users.c.id == user_id)
    ).mappings().first()
    if not row:
        return None

    raw_json = row.get('profile_ai_insight_json')
    fingerprint = str(row.get('profile_ai_insight_fingerprint') or '').strip()
    generated_at = _parse_stored_timestamp(row.get('profile_ai_insight_generated_at'))
    if not raw_json or not fingerprint:
        return None

    try:
        insight = json.loads(raw_json)
    except json.JSONDecodeError:
        return None

    expires_at = (generated_at + timedelta(minutes=settings.profile_ai_insight_ttl_minutes)) if generated_at else None
    expired = expires_at is None or utc_now() >= expires_at
    return {
        'insight': insight if isinstance(insight, dict) else None,
        'fingerprint': fingerprint,
        'generated_at': generated_at,
        'expired': expired,
    }


def _parse_stored_timestamp(raw_value) -> datetime | None:
    normalized = str(raw_value or '').strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _store_cached_insight(
    db: Session,
    *,
    user_id: int,
    fingerprint: str,
    insight: dict,
) -> None:
    users = get_users_table(settings.users_table)
    now = utc_now()
    db.execute(
        users.update()
        .where(users.c.id == user_id)
        .values(
            profile_ai_insight_json=json.dumps(insight, ensure_ascii=False),
            profile_ai_insight_fingerprint=fingerprint,
            profile_ai_insight_generated_at=to_api_iso(now),
            updated_at=now,
        )
    )
    return now


def _serialize_insight_result(
    insight: dict | None,
    *,
    generated_at,
    cache_hit: bool,
) -> dict | None:
    if not isinstance(insight, dict):
        return None

    return {
        **insight,
        'generated_at': to_api_iso(generated_at),
        'ttl_minutes': settings.profile_ai_insight_ttl_minutes,
        'uses_ttl': True,
        'cache_hit': cache_hit,
    }


def _gemini_available() -> bool:
    return bool(settings.gemini_api_key and settings.gemini_api_key.strip())


def _build_prompt(metrics: dict, score_data: dict) -> str:
    strongest = metrics.get('strongest_subcategory') or {}
    weakest = metrics.get('weakest_subcategory') or {}
    question_rows = metrics.get('question_rows') or []
    top_disciplines = [
        {'discipline': row[0], 'count': int(row[1] or 0)}
        for row in question_rows[:4]
        if row and row[0]
    ]

    total_questions = int(metrics.get('total_questions') or 0)
    active_days_last_30 = int(metrics.get('active_days_last_30') or 0)
    completed_sessions = int(metrics.get('completed_sessions') or 0)
    leader_share_percent = 0
    if total_questions > 0 and top_disciplines:
        leader_share_percent = round((top_disciplines[0]['count'] / total_questions) * 100)

    insight_payload = {
        'score': score_data.get('score'),
        'level': score_data.get('level'),
        'recent_index': score_data.get('recent_index'),
        'questions_answered': total_questions,
        'total_correct': metrics.get('total_correct'),
        'accuracy_percent': metrics.get('accuracy_percent'),
        'completed_sessions': completed_sessions,
        'total_study_seconds': metrics.get('total_study_seconds'),
        'active_days_last_30': active_days_last_30,
        'current_streak_days': metrics.get('current_streak_days'),
        'disciplines': top_disciplines,
        'leader_discipline': top_disciplines[0]['discipline'] if top_disciplines else None,
        'leader_share_percent': leader_share_percent,
        'strongest_subcategory': strongest,
        'weakest_subcategory': weakest,
        'attention_subcategories_count': metrics.get('attention_subcategories_count'),
        'sample_quality': _sample_quality_label(
            total_questions=total_questions,
            completed_sessions=completed_sessions,
            active_days_last_30=active_days_last_30,
        ),
    }

    return (
        'Voce e um analista pedagogico do Cognix. '
        'Receba metricas reais de estudo e responda em JSON com as chaves: '
        '`title`, `summary`, `priority`, `risk_level`, `next_action`, `confidence`. '
        'Regras: '
        '1) Nao invente numeros. '
        '2) Use tom claro, humano e direto. '
        '3) O title deve ter no maximo 4 palavras. '
        '4) O summary deve ter entre 2 e 4 frases curtas, explicando panorama atual, '
        'qualidade do desempenho e proximo melhor movimento. '
        '5) priority deve ser curta e pratica, como "Revisar Algebra". '
        '6) risk_level deve ser exatamente "baixo", "medio" ou "alto". '
        '7) next_action deve ser uma acao objetiva, em uma frase curta. '
        '8) confidence deve ser um numero decimal entre 0.0 e 1.0. '
        '9) Se houver pouca base, diga isso com honestidade. '
        '10) Diferencie claramente presenca/volume de prioridade de revisao. '
        'Presenca indica onde ha mais questoes respondidas. Prioridade indica onde agir agora. '
        '11) Nao diga "o foco atual e X" se X for apenas a prioridade de revisao. '
        'Se o volume estiver em uma disciplina e a prioridade estiver em outra, deixe isso explicito. '
        '12) Se sample_quality for "baixa", trate as conclusoes como leitura inicial e evite afirmacoes fortes. '
        '13) Responda apenas JSON valido.\n\n'
        f'DADOS:\n{json.dumps(insight_payload, ensure_ascii=False)}'
    )


def _sample_quality_label(
    *,
    total_questions: int,
    completed_sessions: int,
    active_days_last_30: int,
) -> str:
    if total_questions < 12 or active_days_last_30 < 3:
        return 'baixa'
    if total_questions < 30 or completed_sessions < 3:
        return 'media'
    return 'alta'


def _generate_insight(prompt: str) -> dict | None:
    endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{settings.gemini_model}:generateContent'
    )
    request_payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'responseJsonSchema': _build_response_schema(),
            'temperature': 0.35,
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(request_payload).encode('utf-8'),
        headers={
            'x-goog-api-key': settings.gemini_api_key,
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode('utf-8')

    envelope = json.loads(raw)
    for candidate in envelope.get('candidates') or []:
        content = candidate.get('content') or {}
        for part in content.get('parts') or []:
            text = part.get('text')
            if not text:
                continue
            payload = json.loads(text)
            title = str(payload.get('title') or '').strip()
            summary = str(payload.get('summary') or '').strip()
            priority = str(payload.get('priority') or '').strip()
            risk_level = str(payload.get('risk_level') or '').strip().lower()
            next_action = str(payload.get('next_action') or '').strip()
            try:
                confidence = float(payload.get('confidence'))
            except (TypeError, ValueError):
                confidence = 0.0

            if (
                title and
                summary and
                priority and
                risk_level and
                next_action
            ):
                return {
                    'title': title,
                    'summary': summary,
                    'priority': priority,
                    'risk_level': risk_level,
                    'next_action': next_action,
                    'confidence': max(0.0, min(confidence, 1.0)),
                }

    return None


def _build_response_schema() -> dict:
    return {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'summary': {'type': 'string'},
            'priority': {'type': 'string'},
            'risk_level': {'type': 'string'},
            'next_action': {'type': 'string'},
            'confidence': {'type': 'number'},
        },
        'required': [
            'title',
            'summary',
            'priority',
            'risk_level',
            'next_action',
            'confidence',
        ],
    }
