from sqlalchemy import text

from .utils import get_column_names, table_exists


def ensure_users_schema(engine, users_table_name: str) -> None:
    if not table_exists(engine, users_table_name):
        return

    column_names = get_column_names(engine, users_table_name)
    statements: list[str] = []

    if 'coins_half_units' not in column_names:
        statements.append(
            f'ALTER TABLE {users_table_name} '
            'ADD COLUMN IF NOT EXISTS coins_half_units INTEGER NOT NULL DEFAULT 0'
        )
    if 'equipped_avatar_seed' not in column_names:
        statements.append(
            f'ALTER TABLE {users_table_name} '
            'ADD COLUMN IF NOT EXISTS equipped_avatar_seed VARCHAR(255)'
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
