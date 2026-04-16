import json

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON, JSONB

from app.services.session_state import (
    LEGACY_SESSION_STATE_VERSION,
    derive_session_snapshot_columns,
    parse_session_state,
)

from .utils import get_columns_by_name, quote_identifier, table_exists


def ensure_sessions_schema(engine, sessions_table_name: str) -> None:
    if not table_exists(engine, sessions_table_name):
        return

    quoted_table_name = quote_identifier(engine, sessions_table_name)
    effective_saved_at_index_name = quote_identifier(
        engine,
        f'ix_{sessions_table_name}_user_effective_saved_at',
    )
    completed_effective_saved_at_index_name = quote_identifier(
        engine,
        f'ix_{sessions_table_name}_user_completed_effective_saved_at',
    )
    columns = get_columns_by_name(engine, sessions_table_name)
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
