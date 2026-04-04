from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from .tables import coin_ledger_table


def insert_coin_ledger_entry(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    reason: str,
    delta_half_units: int,
    balance_after_half_units: int,
    question_id: int | None = None,
    avatar_seed: str | None = None,
) -> None:
    ledger = coin_ledger_table()
    now = utc_now()
    db.execute(
        ledger.insert().values(
            user_id=user_id,
            firebase_uid=firebase_uid,
            reason=reason,
            delta_half_units=delta_half_units,
            balance_after_half_units=balance_after_half_units,
            question_id=question_id,
            avatar_seed=avatar_seed,
            created_at=now,
            updated_at=now,
        )
    )
