import json

from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import JSON, JSONB

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
from app.services.session_state import (
    LEGACY_SESSION_STATE_VERSION,
    derive_session_snapshot_columns,
    parse_session_state,
)


def _quote_identifier(engine, identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote(identifier)


def _ensure_users_schema(engine, users_table_name: str) -> None:
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


def _ensure_sessions_schema(engine, sessions_table_name: str) -> None:
    inspector = inspect(engine)
    if sessions_table_name not in inspector.get_table_names():
        return

    quoted_table_name = _quote_identifier(engine, sessions_table_name)
    effective_saved_at_index_name = _quote_identifier(
        engine,
        f'ix_{sessions_table_name}_user_effective_saved_at',
    )
    completed_effective_saved_at_index_name = _quote_identifier(
        engine,
        f'ix_{sessions_table_name}_user_completed_effective_saved_at',
    )
    columns = {
        column['name']: column
        for column in inspector.get_columns(sessions_table_name)
    }
    state_json_column = columns.get('state_json')
    if state_json_column is None:
        return

    statements: list[str] = []
    if 'state_version' not in columns:
        statements.append(
            f'ALTER TABLE {quoted_table_name} '
            f'ADD COLUMN IF NOT EXISTS state_version INTEGER NOT NULL DEFAULT {LEGACY_SESSION_STATE_VERSION}'
        )
    if 'completed' not in columns:
        statements.append(
            f'ALTER TABLE {quoted_table_name} '
            'ADD COLUMN IF NOT EXISTS completed BOOLEAN NOT NULL DEFAULT FALSE'
        )
    if 'answered_questions' not in columns:
        statements.append(
            f'ALTER TABLE {quoted_table_name} '
            'ADD COLUMN IF NOT EXISTS answered_questions INTEGER NOT NULL DEFAULT 0'
        )
    if 'total_questions' not in columns:
        statements.append(
            f'ALTER TABLE {quoted_table_name} '
            'ADD COLUMN IF NOT EXISTS total_questions INTEGER NOT NULL DEFAULT 0'
        )
    if 'elapsed_seconds' not in columns:
        statements.append(
            f'ALTER TABLE {quoted_table_name} '
            'ADD COLUMN IF NOT EXISTS elapsed_seconds INTEGER NOT NULL DEFAULT 0'
        )
    if 'saved_at' not in columns:
        statements.append(
            f'ALTER TABLE {quoted_table_name} '
            'ADD COLUMN IF NOT EXISTS saved_at TIMESTAMPTZ'
        )

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

        state_rows = connection.execute(
            text(f'SELECT id, state_json FROM {quoted_table_name}')
        ).mappings().all()

        state_updates: list[dict[str, object]] = []
        for row in state_rows:
            parsed_state = parse_session_state(row.get('state_json'))
            state_updates.append(
                {
                    'id': row['id'],
                    **derive_session_snapshot_columns(parsed_state),
                }
            )

            if not isinstance(state_json_column['type'], (JSON, JSONB)):
                connection.execute(
                    text(
                        f'UPDATE {quoted_table_name} '
                        'SET state_json = :state_json '
                        'WHERE id = :id'
                    ),
                    {
                        'id': row['id'],
                        'state_json': json.dumps(parsed_state, ensure_ascii=True),
                    },
                )

        if not isinstance(state_json_column['type'], (JSON, JSONB)):
            connection.execute(
                text(
                    f'ALTER TABLE {quoted_table_name} '
                    'ALTER COLUMN state_json TYPE JSONB '
                    'USING state_json::jsonb'
                )
            )

        if state_updates:
            connection.execute(
                text(
                    f'UPDATE {quoted_table_name} '
                    'SET state_version = :state_version, '
                    'completed = :completed, '
                    'answered_questions = :answered_questions, '
                    'total_questions = :total_questions, '
                    'elapsed_seconds = :elapsed_seconds, '
                    'saved_at = :saved_at '
                    'WHERE id = :id'
                ),
                state_updates,
            )

        connection.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS {effective_saved_at_index_name} '
                f'ON {quoted_table_name} (user_id, COALESCE(saved_at, updated_at))'
            )
        )
        connection.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS {completed_effective_saved_at_index_name} '
                f'ON {quoted_table_name} '
                '(user_id, completed, COALESCE(saved_at, updated_at))'
            )
        )


def ensure_internal_schema(
    engine,
    users_table_name: str,
    sessions_table_name: str,
) -> None:
    _ensure_users_schema(engine, users_table_name)
    _ensure_sessions_schema(engine, sessions_table_name)


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
    ensure_internal_schema(engine, users_table_name, sessions_table_name)
