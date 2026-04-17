from sqlalchemy import text

from .utils import get_column_names, quote_identifier, table_exists


def ensure_multiplayer_schema(
    engine,
    rooms_table_name: str,
    participants_table_name: str,
) -> None:
    with engine.begin() as conn:
        if table_exists(engine, rooms_table_name):
            _ensure_rooms_schema(conn, engine, rooms_table_name)
        if table_exists(engine, participants_table_name):
            _ensure_participants_schema(conn, engine, participants_table_name)


def _ensure_rooms_schema(conn, engine, table_name: str) -> None:
    table = quote_identifier(engine, table_name)
    columns = get_column_names(engine, table_name)

    if 'question_ids' not in columns:
        json_type = 'JSONB' if engine.dialect.name == 'postgresql' else 'JSON'
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN question_ids {json_type}'))
    if 'current_question_index' not in columns:
        conn.execute(
            text(
                f'ALTER TABLE {table} '
                'ADD COLUMN current_question_index INTEGER NOT NULL DEFAULT 0'
            )
        )
    if 'round_duration_seconds' not in columns:
        conn.execute(
            text(
                f'ALTER TABLE {table} '
                'ADD COLUMN round_duration_seconds INTEGER NOT NULL DEFAULT 60'
            )
        )
    if 'round_started_at' not in columns:
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN round_started_at TIMESTAMPTZ'))


def _ensure_participants_schema(conn, engine, table_name: str) -> None:
    table = quote_identifier(engine, table_name)
    columns = get_column_names(engine, table_name)

    if 'score' not in columns:
        conn.execute(
            text(f'ALTER TABLE {table} ADD COLUMN score INTEGER NOT NULL DEFAULT 0')
        )
    if 'correct_answers' not in columns:
        conn.execute(
            text(
                f'ALTER TABLE {table} '
                'ADD COLUMN correct_answers INTEGER NOT NULL DEFAULT 0'
            )
        )
    if 'answered_current_question' not in columns:
        conn.execute(
            text(
                f'ALTER TABLE {table} '
                'ADD COLUMN answered_current_question BOOLEAN NOT NULL DEFAULT false'
            )
        )
    if 'current_question_id' not in columns:
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN current_question_id INTEGER'))
    if 'selected_letter' not in columns:
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN selected_letter VARCHAR(2)'))
    if 'last_answered_at' not in columns:
        conn.execute(
            text(f'ALTER TABLE {table} ADD COLUMN last_answered_at TIMESTAMPTZ')
        )
