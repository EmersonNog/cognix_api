from collections.abc import Iterable

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


def catalog_by_seed() -> dict[str, dict[str, object]]:
    return {
        str(item['seed']): item
        for item in AVATAR_STORE_CATALOG
    }


def normalize_owned_avatar_seeds(raw_items: Iterable[object]) -> list[str]:
    unique = {
        str(item).strip()
        for item in raw_items
        if str(item).strip()
    }
    return [
        str(item['seed'])
        for item in AVATAR_STORE_CATALOG
        if str(item['seed']) in unique
    ]


def build_avatar_store_payload(
    *,
    coins_half_units: int,
    equipped_avatar_seed: str,
    owned_avatar_seeds: Iterable[object],
) -> list[dict[str, object]]:
    owned = set(normalize_owned_avatar_seeds(owned_avatar_seeds))
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
