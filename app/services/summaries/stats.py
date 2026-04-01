from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import to_api_iso
from app.db.models import get_attempts_table, get_questions_table
from app.db.session import engine


def derive_error_patterns(stats: dict) -> list[str]:
    patterns = []
    accuracy = float(stats.get('accuracy_percent') or 0.0)

    if accuracy < 40:
        patterns.append('Baixa precisao geral na subcategoria, indicando falhas de base.')
    elif accuracy < 65:
        patterns.append('Desempenho instavel, com lacunas em conceitos centrais.')

    return patterns[:4]


def latest_attempt_at(db: Session, user_id: int, discipline: str, subcategory: str):
    attempts = get_attempts_table(settings.attempts_table)
    stmt = (
        select(func.max(attempts.c.answered_at))
        .where(attempts.c.user_id == user_id)
        .where(attempts.c.discipline == discipline)
        .where(attempts.c.subcategory == subcategory)
    )
    return db.execute(stmt).scalar()


def fetch_user_stats(
    db: Session,
    user_id: int,
    discipline: str,
    subcategory: str,
) -> dict:
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
    latest_attempt = latest_attempt_at(db, user_id, discipline, subcategory)

    stats = {
        'total_attempts': total,
        'total_correct': correct,
        'accuracy_percent': accuracy,
        'incorrect_question_ids': incorrect_ids,
        'latest_attempt_at': to_api_iso(latest_attempt),
    }
    stats['error_patterns'] = derive_error_patterns(stats)
    return stats


def fetch_question_total(db: Session, discipline: str, subcategory: str) -> int:
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


def fetch_question_samples(
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
