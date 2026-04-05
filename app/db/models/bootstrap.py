from sqlalchemy import inspect, text

from .common import metadata
from .tables import (
    get_attempt_history_table,
    get_attempts_table,
    get_session_history_table,
    get_sessions_table,
    get_summaries_table,
    get_user_avatar_inventory_table,
    get_user_coin_ledger_table,
    get_user_study_plan_table,
    get_user_summaries_table,
    get_users_table,
)


def ensure_internal_schema(engine, users_table_name: str) -> None:
    inspector = inspect(engine)
    if users_table_name not in inspector.get_table_names():
        return

    column_names = {
        column['name']
        for column in inspector.get_columns(users_table_name)
    }
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


def create_internal_tables(
    engine,
    users_table_name: str,
    attempts_table_name: str,
    attempt_history_table_name: str,
    sessions_table_name: str,
    session_history_table_name: str,
    summaries_table_name: str,
    user_summaries_table_name: str,
    user_coin_ledger_table_name: str,
    user_avatar_inventory_table_name: str,
    study_plan_table_name: str,
) -> None:
    get_users_table(users_table_name)
    get_attempts_table(attempts_table_name)
    get_attempt_history_table(attempt_history_table_name)
    get_sessions_table(sessions_table_name)
    get_session_history_table(session_history_table_name)
    get_summaries_table(summaries_table_name)
    get_user_summaries_table(user_summaries_table_name)
    get_user_coin_ledger_table(user_coin_ledger_table_name)
    get_user_avatar_inventory_table(user_avatar_inventory_table_name)
    get_user_study_plan_table(study_plan_table_name)
    metadata.create_all(
        bind=engine,
        tables=[
            metadata.tables[users_table_name],
            metadata.tables[attempts_table_name],
            metadata.tables[attempt_history_table_name],
            metadata.tables[sessions_table_name],
            metadata.tables[session_history_table_name],
            metadata.tables[summaries_table_name],
            metadata.tables[user_summaries_table_name],
            metadata.tables[user_coin_ledger_table_name],
            metadata.tables[user_avatar_inventory_table_name],
            metadata.tables[study_plan_table_name],
        ],
    )
    ensure_internal_schema(engine, users_table_name)
