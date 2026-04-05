from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import get_attempt_history_table, get_questions_table
from app.db.session import engine


def fetch_subcategory_candidates(
    db: Session,
    *,
    user_id: int,
    discipline: str | None = None,
) -> list[dict[str, object]]:
    questions = get_questions_table(engine, settings.question_table)
    attempt_history = get_attempt_history_table(settings.attempt_history_table)

    if 'disciplina' not in questions.c or 'subcategoria' not in questions.c:
        return []

    question_stmt = (
        select(
            questions.c.disciplina.label('discipline'),
            questions.c.subcategoria.label('subcategory'),
            func.count().label('total_questions'),
        )
        .where(questions.c.disciplina.is_not(None))
        .where(questions.c.subcategoria.is_not(None))
    )
    if discipline:
        question_stmt = question_stmt.where(questions.c.disciplina == discipline)
    question_stmt = question_stmt.group_by(
        questions.c.disciplina,
        questions.c.subcategoria,
    )

    attempt_stmt = (
        select(
            attempt_history.c.discipline.label('discipline'),
            attempt_history.c.subcategory.label('subcategory'),
            func.count().label('total_attempts'),
            func.sum(
                case((attempt_history.c.is_correct.is_(True), 1), else_=0)
            ).label('total_correct'),
        )
        .where(attempt_history.c.user_id == user_id)
        .where(attempt_history.c.discipline.is_not(None))
        .where(attempt_history.c.subcategory.is_not(None))
    )
    if discipline:
        attempt_stmt = attempt_stmt.where(attempt_history.c.discipline == discipline)
    attempt_stmt = attempt_stmt.group_by(
        attempt_history.c.discipline,
        attempt_history.c.subcategory,
    )

    question_rows = db.execute(question_stmt).all()
    attempt_rows = db.execute(attempt_stmt).all()

    attempt_lookup = {
        (
            str(row.discipline or '').strip().casefold(),
            str(row.subcategory or '').strip().casefold(),
        ): {
            'total_attempts': int(row.total_attempts or 0),
            'total_correct': int(row.total_correct or 0),
        }
        for row in attempt_rows
        if str(row.discipline or '').strip() and str(row.subcategory or '').strip()
    }

    candidates: list[dict[str, object]] = []
    for row in question_rows:
        normalized_discipline = str(row.discipline or '').strip()
        normalized_subcategory = str(row.subcategory or '').strip()
        if not normalized_discipline or not normalized_subcategory:
            continue

        key = (
            normalized_discipline.casefold(),
            normalized_subcategory.casefold(),
        )
        attempts = attempt_lookup.get(key, {})
        total_attempts = int(attempts.get('total_attempts') or 0)
        total_correct = int(attempts.get('total_correct') or 0)
        accuracy_percent = (
            round((total_correct / total_attempts) * 100, 1)
            if total_attempts > 0
            else None
        )
        candidates.append(
            {
                'discipline': normalized_discipline,
                'subcategory': normalized_subcategory,
                'total_questions': int(row.total_questions or 0),
                'total_attempts': total_attempts,
                'accuracy_percent': accuracy_percent,
            }
        )

    return sorted(candidates, key=candidate_rank)


def candidate_rank(candidate: dict[str, object]) -> tuple[object, ...]:
    total_attempts = int(candidate.get('total_attempts') or 0)
    total_questions = int(candidate.get('total_questions') or 0)
    accuracy_percent = candidate.get('accuracy_percent')
    coverage_ratio = (
        total_attempts / total_questions
        if total_attempts > 0 and total_questions > 0
        else 0.0
    )

    if total_attempts <= 0:
        return (0, -total_questions, str(candidate.get('subcategory') or '').casefold())

    return (
        1,
        float(accuracy_percent if accuracy_percent is not None else 100.0),
        coverage_ratio,
        -total_questions,
        str(candidate.get('subcategory') or '').casefold(),
    )


def select_best_candidate(
    candidates: list[dict[str, object]],
    *,
    seen: set[tuple[str, str]],
) -> dict[str, object] | None:
    for candidate in candidates:
        if candidate_key(candidate) in seen:
            continue
        return candidate
    return None


def candidate_key(candidate: dict[str, object]) -> tuple[str, str]:
    return (
        str(candidate.get('discipline') or '').strip().casefold(),
        str(candidate.get('subcategory') or '').strip().casefold(),
    )


def recommendation_key(item: dict[str, object]) -> tuple[str, str]:
    return (
        str(item.get('discipline') or '').strip().casefold(),
        str(item.get('subcategory') or '').strip().casefold(),
    )
