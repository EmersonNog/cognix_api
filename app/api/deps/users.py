from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import get_users_table


def get_internal_user(db: Session, firebase_uid: str):
    users_table = get_users_table(settings.users_table)
    return db.execute(
        select(users_table).where(users_table.c.firebase_uid == firebase_uid)
    ).mappings().first()


def sync_internal_user(db: Session, claims: dict) -> dict:
    users_table = get_users_table(settings.users_table)

    firebase_uid = claims.get('uid') or claims.get('user_id') or claims.get('sub')
    if not firebase_uid:
        raise HTTPException(status_code=401, detail='Invalid token')

    provider = claims.get('firebase', {}).get('sign_in_provider')
    email = claims.get('email')
    display_name = claims.get('name')
    existing = get_internal_user(db, firebase_uid)

    now = utc_now()
    if existing is None:
        db.execute(
            users_table.insert().values(
                firebase_uid=firebase_uid,
                email=email,
                display_name=display_name,
                provider=provider,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        existing = get_internal_user(db, firebase_uid)
    else:
        updates = {}
        if existing.get('email') != email:
            updates['email'] = email
        if existing.get('display_name') != display_name:
            updates['display_name'] = display_name
        if existing.get('provider') != provider:
            updates['provider'] = provider

        if updates:
            updates['updated_at'] = now
            db.execute(
                users_table.update()
                .where(users_table.c.firebase_uid == firebase_uid)
                .values(**updates)
            )
            db.commit()
            existing = get_internal_user(db, firebase_uid)

    claims['internal_user'] = dict(existing) if existing else None
    return claims
