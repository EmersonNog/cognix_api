from firebase_admin import auth
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_firebase_app
from app.db.models import (
    get_attempt_history_table,
    get_attempts_table,
    get_session_history_table,
    get_sessions_table,
    get_user_avatar_inventory_table,
    get_user_coin_ledger_table,
    get_user_study_plan_table,
    get_user_summaries_table,
    get_users_table,
)


def _user_scoped_tables():
    return [
        get_attempts_table(settings.attempts_table),
        get_attempt_history_table(settings.attempt_history_table),
        get_sessions_table(settings.sessions_table),
        get_session_history_table(settings.session_history_table),
        get_user_summaries_table(settings.user_summaries_table),
        get_user_coin_ledger_table(settings.user_coin_ledger_table),
        get_user_avatar_inventory_table(settings.user_avatar_inventory_table),
        get_user_study_plan_table(settings.study_plan_table),
    ]


def delete_user_account(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
) -> dict[str, str]:
    users = get_users_table(settings.users_table)

    try:
        for table in _user_scoped_tables():
            db.execute(delete(table).where(table.c.user_id == user_id))

        db.execute(
            delete(users)
            .where(users.c.id == user_id)
            .where(users.c.firebase_uid == firebase_uid)
        )

        try:
            auth.delete_user(firebase_uid, app=get_firebase_app())
        except auth.UserNotFoundError:
            pass

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {'status': 'ok'}
