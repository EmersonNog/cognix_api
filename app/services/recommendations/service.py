from sqlalchemy.orm import Session

from app.services.profile_score.repository import fetch_profile_metrics
from app.services.study_plan.repository import (
    fetch_study_plan_row,
    parse_priority_disciplines,
)
from app.services.summaries import fetch_question_total

from .candidates import (
    candidate_key as _candidate_key,
    fetch_subcategory_candidates as _fetch_subcategory_candidates,
    recommendation_key as _recommendation_key,
    select_best_candidate as _select_best_candidate,
)
from .builders import (
    build_candidate_recommendation as _build_candidate_recommendation,
    build_section_subtitle as _build_section_subtitle,
    build_weakest_recommendation as _build_weakest_recommendation,
)

MAX_RECOMMENDATIONS = 4


def fetch_home_recommendations(db: Session, *, user_id: int) -> dict[str, object]:
    metrics = fetch_profile_metrics(db, user_id)
    study_plan_row = fetch_study_plan_row(db, user_id)
    priority_disciplines = parse_priority_disciplines(
        None if study_plan_row is None else study_plan_row.get('priority_disciplines_json')
    )

    items: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    weakest = metrics.get('weakest_subcategory')
    if isinstance(weakest, dict):
        weakest_item = _build_weakest_item(db, weakest)
        if weakest_item is not None:
            items.append(weakest_item)
            seen.add(_recommendation_key(weakest_item))

    items.extend(
        _build_priority_items(
            db,
            user_id=user_id,
            priority_disciplines=priority_disciplines,
            seen=seen,
            limit=MAX_RECOMMENDATIONS - len(items),
        )
    )

    if len(items) < MAX_RECOMMENDATIONS:
        items.extend(
            _build_coverage_gap_items(
                db,
                user_id=user_id,
                seen=seen,
                limit=MAX_RECOMMENDATIONS - len(items),
            )
        )

    return {
        'title': 'Recomendado para Hoje',
        'subtitle': _build_section_subtitle(
            items=items,
            has_priority_disciplines=bool(priority_disciplines),
        ),
        'items': items,
    }


def _build_weakest_item(
    db: Session,
    weakest: dict[str, object],
) -> dict[str, object] | None:
    discipline = str(weakest.get('discipline') or '').strip()
    subcategory = str(weakest.get('subcategory') or '').strip()
    total_questions = fetch_question_total(db, discipline, subcategory)
    return _build_weakest_recommendation(weakest, total_questions=total_questions)


def _build_priority_items(
    db: Session,
    *,
    user_id: int,
    priority_disciplines: list[str],
    seen: set[tuple[str, str]],
    limit: int,
) -> list[dict[str, object]]:
    if limit <= 0:
        return []

    items: list[dict[str, object]] = []

    for discipline in priority_disciplines:
        candidate = _select_best_candidate(
            _fetch_subcategory_candidates(
                db,
                user_id=user_id,
                discipline=discipline,
            ),
            seen=seen,
        )
        if candidate is None:
            continue

        item = _build_candidate_recommendation(
            candidate,
            source='priority_discipline',
        )
        items.append(item)
        seen.add(_recommendation_key(item))
        if len(items) >= limit:
            break

    return items


def _build_coverage_gap_items(
    db: Session,
    *,
    user_id: int,
    seen: set[tuple[str, str]],
    limit: int,
) -> list[dict[str, object]]:
    if limit <= 0:
        return []

    items: list[dict[str, object]] = []

    for candidate in _fetch_subcategory_candidates(db, user_id=user_id):
        key = _candidate_key(candidate)
        if key in seen:
            continue

        item = _build_candidate_recommendation(
            candidate,
            source='coverage_gap',
        )
        items.append(item)
        seen.add(key)
        if len(items) >= limit:
            break

    return items
