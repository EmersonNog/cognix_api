from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models.tables.entitlements import get_user_access_grants_table

def find_user_grant(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    grant_type: str,
) -> dict | None:
    table = get_user_access_grants_table(settings.user_access_grants_table)
    filters = [table.c.user_id == user_id]

    if firebase_uid:
        filters.append(table.c.firebase_uid == firebase_uid)

    row = db.execute(
        select(table)
        .where(or_(*filters), table.c.grant_type == grant_type)
        .order_by(desc(table.c.created_at), desc(table.c.id))
        .limit(1)
    ).mappings().first()

    return dict(row) if row else None

def create_user_grant(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    grant_type: str,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    table = get_user_access_grants_table(settings.user_access_grants_table)
    now = utc_now()

    db.execute(
        insert(table).values(
            user_id=user_id,
            firebase_uid=firebase_uid,
            grant_type=grant_type,
            status='active',
            starts_at=starts_at,
            ends_at=ends_at,
            created_at=now,
            updated_at=now,
        )
    )

def mark_user_grant_expired(
    db: Session,
    *,
    grant_id: int,
) -> None:
    table = get_user_access_grants_table(settings.user_access_grants_table)

    db.execute(
        update(table)
        .where(table.c.id == grant_id)
        .values(status='expired', updated_at=utc_now())
    )
