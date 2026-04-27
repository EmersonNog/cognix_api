from sqlalchemy import text

from .utils import get_column_names, quote_identifier, table_exists

def ensure_user_access_grants_schema(engine, table_name: str) -> None:
    if not table_exists(engine, table_name):
        return

    quoted_table_name = quote_identifier(engine, table_name)
    columns = get_column_names(engine, table_name)
    if 'id' not in columns:
        return

    with engine.begin() as connection:
        _add_missing_columns(connection, quoted_table_name, columns)
        _delete_duplicate_grants(connection, quoted_table_name)
        _create_indexes(connection, engine, table_name, quoted_table_name)

def _add_missing_columns(connection, quoted_table_name: str, columns: set[str]) -> None:
    column_specs = {
        'user_id': 'INTEGER',
        'firebase_uid': 'VARCHAR(255)',
        'grant_type': 'VARCHAR(64)',
        'status': "VARCHAR(64) DEFAULT 'active'",
        'starts_at': 'TIMESTAMPTZ',
        'ends_at': 'TIMESTAMPTZ',
        'revoked_at': 'TIMESTAMPTZ',
        'created_at': 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP',
        'updated_at': 'TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP',
    }

    for column_name, column_spec in column_specs.items():
        if column_name not in columns:
            connection.execute(
                text(
                    f'ALTER TABLE {quoted_table_name} '
                    f'ADD COLUMN IF NOT EXISTS {column_name} {column_spec}'
                )
            )

def _delete_duplicate_grants(connection, quoted_table_name: str) -> None:
    _delete_duplicates_by_key(
        connection,
        quoted_table_name,
        key_columns=('user_id', 'grant_type'),
    )
    _delete_duplicates_by_key(
        connection,
        quoted_table_name,
        key_columns=('firebase_uid', 'grant_type'),
    )

def _delete_duplicates_by_key(
    connection,
    quoted_table_name: str,
    *,
    key_columns: tuple[str, str],
) -> None:
    identity_column, grant_type_column = key_columns
    connection.execute(
        text(
            f'DELETE FROM {quoted_table_name} grants '
            'USING ('
            'SELECT id, ROW_NUMBER() OVER ('
            f'PARTITION BY {identity_column}, {grant_type_column} '
            'ORDER BY created_at DESC, id DESC'
            ') AS grant_rank '
            f'FROM {quoted_table_name} '
            f'WHERE {identity_column} IS NOT NULL '
            f'AND {grant_type_column} IS NOT NULL'
            ') ranked '
            'WHERE grants.id = ranked.id '
            'AND ranked.grant_rank > 1'
        )
    )

def _create_indexes(
    connection,
    engine,
    table_name: str,
    quoted_table_name: str,
) -> None:
    index_specs = [
        (f'ix_{table_name}_user_id', '(user_id)'),
        (f'ix_{table_name}_firebase_uid', '(firebase_uid)'),
        (f'ix_{table_name}_user_status', '(user_id, status)'),
        (f'ix_{table_name}_grant_status', '(grant_type, status)'),
    ]
    unique_index_specs = [
        (
            f'uq_{table_name}_user_grant_type',
            '(user_id, grant_type)',
            'user_id IS NOT NULL AND grant_type IS NOT NULL',
        ),
        (
            f'uq_{table_name}_firebase_grant_type',
            '(firebase_uid, grant_type)',
            'firebase_uid IS NOT NULL AND grant_type IS NOT NULL',
        ),
    ]

    for index_name, index_columns in index_specs:
        connection.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS {quote_identifier(engine, index_name)} '
                f'ON {quoted_table_name} {index_columns}'
            )
        )

    for index_name, index_columns, predicate in unique_index_specs:
        connection.execute(
            text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS '
                f'{quote_identifier(engine, index_name)} '
                f'ON {quoted_table_name} {index_columns} '
                f'WHERE {predicate}'
            )
        )
