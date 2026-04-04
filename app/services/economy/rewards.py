from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from .catalog import QUESTION_REWARD_HALF_UNITS, coins_from_half_units
from .ledger import insert_coin_ledger_entry
from .state import ensure_user_economy_defaults, fetch_user_economy_state
from .tables import users_table


def sync_attempt_reward(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    question_id: int,
    eligible_for_reward: bool,
) -> dict[str, object]:
    users = users_table()
    ensure_user_economy_defaults(db, user_id=user_id, firebase_uid=firebase_uid)

    awarded_half_units = QUESTION_REWARD_HALF_UNITS if eligible_for_reward else 0
    if awarded_half_units > 0:
        db.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(
                coins_half_units=users.c.coins_half_units + awarded_half_units,
                updated_at=utc_now(),
            )
        )

    state = fetch_user_economy_state(db, user_id=user_id, firebase_uid=firebase_uid)

    if awarded_half_units > 0:
        insert_coin_ledger_entry(
            db,
            user_id=user_id,
            firebase_uid=firebase_uid,
            reason='question_answer_reward',
            delta_half_units=awarded_half_units,
            balance_after_half_units=int(state['coins_half_units']),
            question_id=question_id,
        )

    return {
        **state,
        'coins_awarded_half_units': awarded_half_units,
        'coins_awarded': coins_from_half_units(awarded_half_units),
        'coins_reward_applied': awarded_half_units > 0,
    }
