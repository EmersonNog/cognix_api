from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import get_attempt_history_table, get_questions_table
from app.db.session import engine


@dataclass(frozen=True)
class CandidateSnapshot:
    question_rows: list[object]
    attempt_rows: list[object]


def fetch_candidate_snapshot(
    db: Session,
    *,
    user_id: int,
) -> CandidateSnapshot:
    questions = get_questions_table(engine, settings.question_table)
    attempt_history = get_attempt_history_table(settings.attempt_history_table)

    if 'disciplina' not in questions.c or 'subcategoria' not in questions.c:
        return CandidateSnapshot(question_rows=[], attempt_rows=[])

    question_rows = db.execute(
        select(
            questions.c.disciplina.label('discipline'),
            questions.c.subcategoria.label('subcategory'),
            func.count().label('total_questions'),
        )
        .where(questions.c.disciplina.is_not(None))
        .where(questions.c.subcategoria.is_not(None))
        .group_by(
            questions.c.disciplina,
            questions.c.subcategoria,
        )
    ).all()

    attempt_rows = db.execute(
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
        .group_by(
            attempt_history.c.discipline,
            attempt_history.c.subcategory,
        )
    ).all()

    return CandidateSnapshot(
        question_rows=list(question_rows),
        attempt_rows=list(attempt_rows),
    )


def fetch_subcategory_candidates(
    db: Session,
    *,
    user_id: int,
    discipline: str | None = None,
) -> list[dict[str, object]]:
    snapshot = fetch_candidate_snapshot(db, user_id=user_id)
    return build_subcategory_candidates(snapshot, discipline=discipline)


def build_subcategory_candidates(
    snapshot: CandidateSnapshot,
    *,
    discipline: str | None = None,
) -> list[dict[str, object]]:
    question_rows = [
        row
        for row in snapshot.question_rows
        if discipline is None or _row_value(row, 'discipline', 0) == discipline
    ]
    attempt_rows = [
        row
        for row in snapshot.attempt_rows
        if discipline is None or _row_value(row, 'discipline', 0) == discipline
    ]

    attempt_lookup = {
        (
            str(_row_value(row, 'discipline', 0) or '').strip().casefold(),
            str(_row_value(row, 'subcategory', 1) or '').strip().casefold(),
        ): {
            'total_attempts': int(_row_value(row, 'total_attempts', 2) or 0),
            'total_correct': int(_row_value(row, 'total_correct', 3) or 0),
        }
        for row in attempt_rows
        if str(_row_value(row, 'discipline', 0) or '').strip()
        and str(_row_value(row, 'subcategory', 1) or '').strip()
    }

    candidates: list[dict[str, object]] = []
    for row in question_rows:
        normalized_discipline = str(_row_value(row, 'discipline', 0) or '').strip()
        normalized_subcategory = str(_row_value(row, 'subcategory', 1) or '').strip()
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
                'total_questions': int(_row_value(row, 'total_questions', 2) or 0),
                'total_attempts': total_attempts,
                'accuracy_percent': accuracy_percent,
            }
        )

    return sorted(candidates, key=candidate_rank)


def question_total_from_snapshot(
    snapshot: CandidateSnapshot,
    *,
    discipline: str,
    subcategory: str,
) -> int:
    total = 0
    for row in snapshot.question_rows:
        if _row_value(row, 'discipline', 0) != discipline:
            continue
        if _row_value(row, 'subcategory', 1) != subcategory:
            continue
        total += int(_row_value(row, 'total_questions', 2) or 0)
    return total


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


def _row_value(row: object, name: str, position: int) -> object:
    mapping = getattr(row, '_mapping', None)
    if mapping is not None:
        return mapping.get(name)
    if isinstance(row, dict):
        return row.get(name)
    if hasattr(row, name):
        return getattr(row, name)
    return row[position]
