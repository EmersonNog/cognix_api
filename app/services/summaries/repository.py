import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import (
    get_sessions_table,
    get_summaries_table,
    get_user_summaries_table,
)


def has_completed_session(
    db: Session,
    user_id: int,
    discipline: str,
    subcategory: str,
) -> bool:
    sessions = get_sessions_table(settings.sessions_table)
    completed = db.execute(
        select(sessions.c.completed)
        .where(sessions.c.user_id == user_id)
        .where(sessions.c.discipline == discipline)
        .where(sessions.c.subcategory == subcategory)
    ).scalar_one_or_none()
    return completed is True


def insert_base_summary_if_missing(
    db: Session,
    discipline: str,
    subcategory: str,
    payload: dict,
) -> None:
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


def upsert_base_summary(
    db: Session,
    discipline: str,
    subcategory: str,
    payload: dict,
) -> None:
    summaries = get_summaries_table(settings.summaries_table)
    now = utc_now()
    payload_json = json.dumps(payload, ensure_ascii=True)
    insert_stmt = pg_insert(summaries).values(
        discipline=discipline,
        subcategory=subcategory,
        payload_json=payload_json,
        created_at=now,
        updated_at=now,
    )
    db.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=[summaries.c.discipline, summaries.c.subcategory],
            set_={'payload_json': payload_json, 'updated_at': now},
        )
    )
    db.commit()


def upsert_user_summary(
    db: Session,
    user_id: int,
    firebase_uid: str,
    discipline: str,
    subcategory: str,
    payload: dict,
) -> None:
    table = get_user_summaries_table(settings.user_summaries_table)
    now = utc_now()
    payload_json = json.dumps(payload, ensure_ascii=True)
    insert_stmt = pg_insert(table).values(
        user_id=user_id,
        firebase_uid=firebase_uid,
        discipline=discipline,
        subcategory=subcategory,
        payload_json=payload_json,
        created_at=now,
        updated_at=now,
    )
    db.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=[table.c.user_id, table.c.discipline, table.c.subcategory],
            set_={'payload_json': payload_json, 'updated_at': now},
        )
    )
    db.commit()
