from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from .catalog import catalog_by_seed, coins_from_half_units
from ..ledger import insert_coin_ledger_entry
from ..state import (
    ensure_user_economy_defaults,
    fetch_user_economy_state,
    lock_user_economy_row,
)
from ..tables import avatar_inventory_table, users_table


def select_profile_avatar(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    avatar_seed: str,
) -> dict[str, object]:
    normalized_seed = avatar_seed.strip()
    catalog_item = catalog_by_seed().get(normalized_seed)
    if catalog_item is None:
        return {'status': 'invalid_avatar'}

    users = users_table()
    inventory = avatar_inventory_table()
    ensure_user_economy_defaults(db, user_id=user_id, firebase_uid=firebase_uid)
    locked_user = lock_user_economy_row(db, user_id=user_id)
    if locked_user is None:
        return {'status': 'user_not_found'}

    state = fetch_user_economy_state(db, user_id=user_id, firebase_uid=firebase_uid)
    if normalized_seed == state['equipped_avatar_seed']:
        return {
            'status': 'ok',
            'action': 'already_equipped',
            **state,
        }

    owned_avatar_seeds = {
        str(seed)
        for seed in state['owned_avatar_seeds']
    }
    cost_half_units = catalog_item.cost_half_units

    if (
        normalized_seed not in owned_avatar_seeds
        and int(state['coins_half_units']) < cost_half_units
    ):
        missing_half_units = cost_half_units - int(state['coins_half_units'])
        return {
            'status': 'insufficient_funds',
            'action': 'insufficient_funds',
            'required_coins': coins_from_half_units(cost_half_units),
            'missing_coins': coins_from_half_units(missing_half_units),
            **state,
        }

    action = 'equipped'
    now = utc_now()
    if normalized_seed not in owned_avatar_seeds:
        if cost_half_units > 0:
            updated_balance = db.execute(
                users.update()
                .where(users.c.id == user_id)
                .where(users.c.coins_half_units >= cost_half_units)
                .values(
                    coins_half_units=users.c.coins_half_units - cost_half_units,
                    equipped_avatar_seed=normalized_seed,
                    updated_at=now,
                )
                .returning(users.c.coins_half_units)
            ).first()
            if updated_balance is None:
                refreshed_state = fetch_user_economy_state(
                    db,
                    user_id=user_id,
                    firebase_uid=firebase_uid,
                )
                missing_half_units = max(
                    cost_half_units - int(refreshed_state['coins_half_units']),
                    0,
                )
                return {
                    'status': 'insufficient_funds',
                    'action': 'insufficient_funds',
                    'required_coins': coins_from_half_units(cost_half_units),
                    'missing_coins': coins_from_half_units(missing_half_units),
                    **refreshed_state,
                }
            action = 'purchased_and_equipped'
        else:
            db.execute(
                users.update()
                .where(users.c.id == user_id)
                .values(
                    equipped_avatar_seed=normalized_seed,
                    updated_at=now,
                )
            )
            action = 'unlocked_and_equipped'

        db.execute(
            pg_insert(inventory)
            .values(
                user_id=user_id,
                firebase_uid=firebase_uid,
                avatar_seed=normalized_seed,
                acquired_via='purchase' if cost_half_units > 0 else 'unlock',
                cost_half_units=cost_half_units,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[inventory.c.user_id, inventory.c.avatar_seed]
            )
        )
    else:
        db.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(
                equipped_avatar_seed=normalized_seed,
                updated_at=now,
            )
        )

    state = fetch_user_economy_state(db, user_id=user_id, firebase_uid=firebase_uid)
    if action == 'purchased_and_equipped' and cost_half_units > 0:
        insert_coin_ledger_entry(
            db,
            user_id=user_id,
            firebase_uid=firebase_uid,
            reason='avatar_purchase',
            delta_half_units=-cost_half_units,
            balance_after_half_units=int(state['coins_half_units']),
            avatar_seed=normalized_seed,
        )

    return {
        'status': 'ok',
        'action': action,
        'selected_avatar_seed': normalized_seed,
        **state,
    }
