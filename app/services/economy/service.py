from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import (
    get_user_avatar_inventory_table,
    get_user_coin_ledger_table,
    get_users_table,
)

DEFAULT_AVATAR_SEED = 'avatar_1'
QUESTION_REWARD_HALF_UNITS = 1

AVATAR_STORE_CATALOG: tuple[dict[str, object], ...] = (
    {'seed': 'avatar_1', 'title': 'Avatar 1', 'cost_half_units': 0},
    {'seed': 'avatar_2', 'title': 'Avatar 2', 'cost_half_units': 6},
    {'seed': 'avatar_3', 'title': 'Avatar 3', 'cost_half_units': 10},
    {'seed': 'avatar_4', 'title': 'Avatar 4', 'cost_half_units': 14},
    {'seed': 'avatar_5', 'title': 'Avatar 5', 'cost_half_units': 18},
    {'seed': 'avatar_6', 'title': 'Avatar 6', 'cost_half_units': 22},
    {'seed': 'avatar_7', 'title': 'Avatar 7', 'cost_half_units': 26},
    {'seed': 'avatar_8', 'title': 'Avatar 8', 'cost_half_units': 30},
    {'seed': 'avatar_9', 'title': 'Avatar 9', 'cost_half_units': 36},
    {'seed': 'avatar_10', 'title': 'Avatar 10', 'cost_half_units': 44},
)


def coins_from_half_units(value: int) -> float:
    return round(max(0, int(value or 0)) / 2.0, 1)


def _catalog_by_seed() -> dict[str, dict[str, object]]:
    return {
        str(item['seed']): item
        for item in AVATAR_STORE_CATALOG
    }


def _normalize_owned_avatar_seeds(raw_items: Iterable[object]) -> list[str]:
    unique = {
        str(item).strip()
        for item in raw_items
        if str(item).strip()
    }
    ordered = [
        str(item['seed'])
        for item in AVATAR_STORE_CATALOG
        if str(item['seed']) in unique
    ]
    return ordered


def _build_avatar_store_payload(
    *,
    coins_half_units: int,
    equipped_avatar_seed: str,
    owned_avatar_seeds: Iterable[object],
) -> list[dict[str, object]]:
    owned = set(_normalize_owned_avatar_seeds(owned_avatar_seeds))
    items: list[dict[str, object]] = []
    for item in AVATAR_STORE_CATALOG:
        seed = str(item['seed'])
        cost_half_units = int(item['cost_half_units'])
        is_owned = seed in owned or cost_half_units == 0
        items.append(
            {
                'seed': seed,
                'title': str(item['title']),
                'cost_half_units': cost_half_units,
                'cost_coins': coins_from_half_units(cost_half_units),
                'owned': is_owned,
                'equipped': seed == equipped_avatar_seed,
                'affordable': is_owned or coins_half_units >= cost_half_units,
                'is_default': seed == DEFAULT_AVATAR_SEED,
            }
        )
    return items


def _users_table():
    return get_users_table(settings.users_table)


def _coin_ledger_table():
    return get_user_coin_ledger_table(settings.user_coin_ledger_table)


def _avatar_inventory_table():
    return get_user_avatar_inventory_table(settings.user_avatar_inventory_table)


def _lock_user_economy_row(db: Session, *, user_id: int) -> dict[str, object] | None:
    users = _users_table()
    return db.execute(
        select(
            users.c.id,
            users.c.coins_half_units,
            users.c.equipped_avatar_seed,
        )
        .where(users.c.id == user_id)
        .with_for_update()
    ).mappings().first()


def _ensure_user_economy_defaults(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
) -> None:
    users = _users_table()
    inventory = _avatar_inventory_table()

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

    db.execute(
        pg_insert(inventory)
        .values(
            user_id=user_id,
            firebase_uid=firebase_uid,
            avatar_seed=DEFAULT_AVATAR_SEED,
            acquired_via='default',
            cost_half_units=0,
            created_at=utc_now(),
            updated_at=utc_now(),
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
    _ensure_user_economy_defaults(db, user_id=user_id, firebase_uid=firebase_uid)

    users = _users_table()
    inventory = _avatar_inventory_table()

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
    owned_avatar_seeds = _normalize_owned_avatar_seeds(
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
        'avatar_store': _build_avatar_store_payload(
            coins_half_units=coins_half_units,
            equipped_avatar_seed=equipped_avatar_seed,
            owned_avatar_seeds=owned_avatar_seeds,
        ),
    }


def _insert_coin_ledger_entry(
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
    ledger = _coin_ledger_table()
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


def sync_attempt_reward(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    question_id: int,
    eligible_for_reward: bool,
) -> dict[str, object]:
    users = _users_table()
    _ensure_user_economy_defaults(db, user_id=user_id, firebase_uid=firebase_uid)

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
        _insert_coin_ledger_entry(
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


def select_profile_avatar(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    avatar_seed: str,
) -> dict[str, object]:
    normalized_seed = avatar_seed.strip()
    catalog_item = _catalog_by_seed().get(normalized_seed)
    if catalog_item is None:
        return {'status': 'invalid_avatar'}

    users = _users_table()
    inventory = _avatar_inventory_table()
    _ensure_user_economy_defaults(db, user_id=user_id, firebase_uid=firebase_uid)
    locked_user = _lock_user_economy_row(db, user_id=user_id)
    if locked_user is None:
        return {'status': 'user_not_found'}
    state = fetch_user_economy_state(db, user_id=user_id, firebase_uid=firebase_uid)

    if normalized_seed == state['equipped_avatar_seed']:
        return {
            'status': 'ok',
            'action': 'already_equipped',
            **state,
        }

    owned_avatar_seeds = set(
        str(seed)
        for seed in state['owned_avatar_seeds']
    )
    cost_half_units = int(catalog_item['cost_half_units'])

    if normalized_seed not in owned_avatar_seeds and int(state['coins_half_units']) < cost_half_units:
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
        _insert_coin_ledger_entry(
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
