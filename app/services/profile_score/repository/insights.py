from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..constants import (
    SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD,
    SUBCATEGORY_INSIGHT_MIN_ATTEMPTS,
)


def build_subcategory_insights(
    db: Session,
    attempt_history,
    user_id: int,
) -> tuple[dict | None, dict | None, int]:
    rows = db.execute(
        select(
            attempt_history.c.discipline,
            attempt_history.c.subcategory,
            func.count().label('total_attempts'),
            func.sum(
                case((attempt_history.c.is_correct.is_(True), 1), else_=0)
            ).label('total_correct'),
        )
        .where(attempt_history.c.user_id == user_id)
        .where(attempt_history.c.discipline.is_not(None))
        .where(attempt_history.c.subcategory.is_not(None))
        .group_by(attempt_history.c.discipline, attempt_history.c.subcategory)
    ).all()

    stats = []
    for discipline, subcategory, total_attempts, total_correct in rows:
        normalized_discipline = str(discipline or '').strip()
        normalized_subcategory = str(subcategory or '').strip()
        attempts_count = int(total_attempts or 0)
        correct_count = int(total_correct or 0)

        if (
            not normalized_discipline
            or not normalized_subcategory
            or attempts_count <= 0
        ):
            continue

        accuracy_percent = round((correct_count / attempts_count) * 100, 1)
        stats.append(
            {
                'discipline': normalized_discipline,
                'subcategory': normalized_subcategory,
                'accuracy_percent': accuracy_percent,
                'total_attempts': attempts_count,
                'total_correct': correct_count,
            }
        )

    if not stats:
        return None, None, 0

    pedagogical_base = [
        item
        for item in stats
        if item['total_attempts'] >= SUBCATEGORY_INSIGHT_MIN_ATTEMPTS
    ]
    ranked = pedagogical_base or stats

    strongest = max(
        ranked,
        key=lambda item: (item['accuracy_percent'], item['total_attempts']),
    )
    weakest = min(
        ranked,
        key=lambda item: (item['accuracy_percent'], -item['total_attempts']),
    )
    attention_subcategories_count = sum(
        1
        for item in ranked
        if item['accuracy_percent'] < SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD
    )
    return strongest, weakest, attention_subcategories_count
