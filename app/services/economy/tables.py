from app.core.config import settings
from app.db.models import (
    get_user_avatar_inventory_table,
    get_user_coin_ledger_table,
    get_users_table,
)


def users_table():
    return get_users_table(settings.users_table)


def coin_ledger_table():
    return get_user_coin_ledger_table(settings.user_coin_ledger_table)


def avatar_inventory_table():
    return get_user_avatar_inventory_table(settings.user_avatar_inventory_table)
