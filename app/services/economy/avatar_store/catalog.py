from collections.abc import Iterable
from dataclasses import dataclass

DEFAULT_AVATAR_SEED = 'avatar_1'
QUESTION_REWARD_HALF_UNITS = 1

@dataclass(frozen=True, slots=True)
class AvatarCatalogItem:
    seed: str
    title: str
    theme: str
    rarity: str
    cost_half_units: int

AVATAR_STORE_CATALOG: tuple[AvatarCatalogItem, ...] = (
    AvatarCatalogItem('avatar_1', 'Zenith', 'Coleção Aurora', 'comum', 0),
    AvatarCatalogItem('avatar_2', 'Nix', 'Coleção Arcade', 'comum', 6),
    AvatarCatalogItem('avatar_3', 'Luna', 'Coleção Neon', 'comum', 10),
    AvatarCatalogItem('avatar_4', 'Orion', 'Coleção Eclipse', 'comum', 14),
    AvatarCatalogItem('avatar_5', 'Solis', 'Coleção Aurora', 'comum', 18),
    AvatarCatalogItem('avatar_6', 'Kael', 'Coleção Neon', 'raro', 22),
    AvatarCatalogItem('avatar_7', 'Vega', 'Coleção Eclipse', 'raro', 26),
    AvatarCatalogItem('avatar_8', 'Zuri', 'Coleção Arcade', 'raro', 30),
    AvatarCatalogItem('avatar_9', 'Astra', 'Coleção Aurora', 'raro', 36),
    AvatarCatalogItem('avatar_10', 'Draco', 'Coleção Neon', 'raro', 44),
    AvatarCatalogItem('avatar_11', 'Bloom', 'Coleção Eclipse', 'epico', 52),
    AvatarCatalogItem('avatar_12', 'Selene', 'Coleção Arcade', 'epico', 60),
    AvatarCatalogItem('avatar_13', 'Helios', 'Coleção Aurora', 'epico', 68),
    AvatarCatalogItem('avatar_14', 'Cipher', 'Coleção Neon', 'epico', 76),
    AvatarCatalogItem('avatar_15', 'Eclipse', 'Coleção Eclipse', 'epico', 84),
    AvatarCatalogItem('avatar_16', 'Vortex', 'Coleção Arcade', 'epico', 92),
    AvatarCatalogItem('avatar_17', 'Helios', 'Coleção Prime', 'lendario', 100),
    AvatarCatalogItem('avatar_18', 'Nyra', 'Coleção Prime', 'lendario', 110),
    AvatarCatalogItem('avatar_19', 'Prisma', 'Coleção Prime', 'lendario', 120),
    AvatarCatalogItem('avatar_20', 'Atlas', 'Coleção Prime', 'lendario', 130),
)

def coins_from_half_units(value: int) -> float:
    return round(max(0, int(value or 0)) / 2.0, 1)

def catalog_by_seed() -> dict[str, AvatarCatalogItem]:
    return {item.seed: item for item in AVATAR_STORE_CATALOG}

def normalize_owned_avatar_seeds(raw_items: Iterable[object]) -> list[str]:
    unique = {str(item).strip() for item in raw_items if str(item).strip()}
    return [item.seed for item in AVATAR_STORE_CATALOG if item.seed in unique]

def build_avatar_store_payload(
    *,
    coins_half_units: int,
    equipped_avatar_seed: str,
    owned_avatar_seeds: Iterable[object],
) -> list[dict[str, object]]:
    owned = set(normalize_owned_avatar_seeds(owned_avatar_seeds))
    items: list[dict[str, object]] = []
    for item in AVATAR_STORE_CATALOG:
        is_owned = item.seed in owned or item.cost_half_units == 0
        items.append(
            {
                'seed': item.seed,
                'title': item.title,
                'theme': item.theme,
                'rarity': item.rarity,
                'cost_half_units': item.cost_half_units,
                'cost_coins': coins_from_half_units(item.cost_half_units),
                'owned': is_owned,
                'equipped': item.seed == equipped_avatar_seed,
                'affordable': is_owned or coins_half_units >= item.cost_half_units,
                'is_default': item.seed == DEFAULT_AVATAR_SEED,
            }
        )
    return items
