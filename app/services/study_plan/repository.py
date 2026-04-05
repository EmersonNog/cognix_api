import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import get_user_study_plan_table

def study_plan_table():
    return get_user_study_plan_table(settings.study_plan_table)

def fetch_study_plan_row(db: Session, user_id: int) -> dict[str, object] | None:
    table = study_plan_table()
    return db.execute(
        select(table).where(table.c.user_id == user_id)
    ).mappings().first()

def upsert_study_plan_row(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    study_days_per_week: int,
    minutes_per_day: int,
    weekly_questions_goal: int,
    focus_mode: str,
    preferred_period: str,
    priority_disciplines: list[str],
) -> None:
    table = study_plan_table()
    now = utc_now()
    insert_stmt = pg_insert(table).values(
        user_id=user_id,
        firebase_uid=firebase_uid,
        study_days_per_week=study_days_per_week,
        minutes_per_day=minutes_per_day,
        weekly_questions_goal=weekly_questions_goal,
        focus_mode=focus_mode,
        preferred_period=preferred_period,
        priority_disciplines_json=json.dumps(priority_disciplines, ensure_ascii=True),
        created_at=now,
        updated_at=now,
    )
    db.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=[table.c.user_id],
            set_={
                'firebase_uid': firebase_uid,
                'study_days_per_week': study_days_per_week,
                'minutes_per_day': minutes_per_day,
                'weekly_questions_goal': weekly_questions_goal,
                'focus_mode': focus_mode,
                'preferred_period': preferred_period,
                'priority_disciplines_json': json.dumps(
                    priority_disciplines,
                    ensure_ascii=True,
                ),
                'updated_at': now,
            },
        )
    )

def parse_priority_disciplines(raw: object) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        return []

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(decoded, list):
        return []

    values: list[str] = []
    for item in decoded:
        value = str(item or '').strip()
        if value:
            values.append(value)
    return values
