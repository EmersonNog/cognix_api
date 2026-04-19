from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .constants import DEFAULT_MATCH_QUESTION_LIMIT
from . import tables


def normalize_question_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    question_ids: list[int] = []
    for item in value:
        try:
            question_id = int(str(item).strip())
        except (TypeError, ValueError):
            continue
        if question_id > 0:
            question_ids.append(question_id)
    return question_ids


def fetch_match_question_ids(db: Session) -> list[int]:
    questions = tables.questions_table()
    rows = db.execute(
        select(questions.c.id).order_by(func.random()).limit(DEFAULT_MATCH_QUESTION_LIMIT)
    ).all()
    return [int(row[0]) for row in rows]


def fetch_question_answer_key(
    db: Session,
    question_id: int,
) -> tuple[bool, str | None]:
    questions = tables.questions_table()
    columns = [questions.c.id]
    has_answer_key = 'gabarito' in questions.c
    if has_answer_key:
        columns.append(questions.c.gabarito)

    row = db.execute(select(*columns).where(questions.c.id == question_id)).first()
    if row is None:
        return False, None
    if not has_answer_key or row[1] is None:
        return True, None
    return True, str(row[1]).strip().upper()[:2]


def resolve_is_correct(selected_letter: str, correct_letter: str | None) -> bool | None:
    if not correct_letter:
        return None
    return selected_letter == correct_letter
