from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from .catalog import (
    DEFAULT_AVATAR_SEED,
    QUESTION_REWARD_HALF_UNITS,
    build_avatar_store_payload,
    coins_from_half_units,
    normalize_owned_avatar_seeds,
)
from .tables import avatar_inventory_table, users_table


def lock_user_economy_row(
    db: Session,
    *,
    user_id: int,
) -> dict[str, object] | None:
    users = users_table()
    return db.execute(
        select(
            users.c.id,
            users.c.coins_half_units,
            users.c.equipped_avatar_seed,
        )
        .where(users.c.id == user_id)
        .with_for_update()
    ).mappings().first()


def ensure_user_economy_defaults(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
) -> None:
    users = users_table()
    inventory = avatar_inventory_table()

    user_row = db.execute(
        select(
            users.c.coins_half_units,
            users.c.equipped_avatar_seed,
        ).where(users.c.id == user_id)
    ).mappings().first()
    if user_row is None:
        return

    updates: dict[str, object] = {}
    if user_row.get('coins_half_units') is None:
        updates['coins_half_units'] = 0

    equipped_seed = str(user_row.get('equipped_avatar_seed') or '').strip()
    if not equipped_seed:
        updates['equipped_avatar_seed'] = DEFAULT_AVATAR_SEED

    if updates:
        updates['updated_at'] = utc_now()
        db.execute(
            users.update().where(users.c.id == user_id).values(**updates)
        )

    now = utc_now()
    db.execute(
        pg_insert(inventory)
        .values(
            user_id=user_id,
            firebase_uid=firebase_uid,
            avatar_seed=DEFAULT_AVATAR_SEED,
            acquired_via='default',
            cost_half_units=0,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(
            index_elements=[inventory.c.user_id, inventory.c.avatar_seed]
        )
    )


def fetch_user_economy_state(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
) -> dict[str, object]:
    ensure_user_economy_defaults(db, user_id=user_id, firebase_uid=firebase_uid)

    users = users_table()
    inventory = avatar_inventory_table()

    user_row = db.execute(
        select(
            users.c.coins_half_units,
            users.c.equipped_avatar_seed,
        ).where(users.c.id == user_id)
    ).mappings().first()

    coins_half_units = int(user_row.get('coins_half_units') or 0) if user_row else 0
    equipped_avatar_seed = (
        str(user_row.get('equipped_avatar_seed') or '').strip()
        if user_row
        else ''
    ) or DEFAULT_AVATAR_SEED

    owned_rows = db.execute(
        select(inventory.c.avatar_seed)
        .where(inventory.c.user_id == user_id)
        .order_by(inventory.c.created_at.asc(), inventory.c.id.asc())
    ).all()
    owned_avatar_seeds = normalize_owned_avatar_seeds(
        seed for (seed,) in owned_rows
    )
    if DEFAULT_AVATAR_SEED not in owned_avatar_seeds:
        owned_avatar_seeds = [DEFAULT_AVATAR_SEED, *owned_avatar_seeds]

    return {
        'coins_half_units': coins_half_units,
        'coins_balance': coins_from_half_units(coins_half_units),
        'question_reward_half_units': QUESTION_REWARD_HALF_UNITS,
        'question_reward_coins': coins_from_half_units(QUESTION_REWARD_HALF_UNITS),
        'equipped_avatar_seed': equipped_avatar_seed,
        'owned_avatar_seeds': owned_avatar_seeds,
        'avatar_store': build_avatar_store_payload(
            coins_half_units=coins_half_units,
            equipped_avatar_seed=equipped_avatar_seed,
            owned_avatar_seeds=owned_avatar_seeds,
        ),
    }
