from sqlalchemy import text

from .utils import get_column_names, quote_identifier, table_exists


def ensure_question_reports_schema(engine, table_name: str) -> None:
    if not table_exists(engine, table_name):
        return

    quoted_table_name = quote_identifier(engine, table_name)
    unique_index_name = quote_identifier(
        engine,
        f'uq_{table_name}_user_question',
    )
    required_columns = {'id', 'user_id', 'question_id', 'created_at'}
    if not required_columns.issubset(get_column_names(engine, table_name)):
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                f'DELETE FROM {quoted_table_name} reports '
                'USING ('
                'SELECT id, ROW_NUMBER() OVER ('
                'PARTITION BY user_id, question_id '
                'ORDER BY created_at DESC, id DESC'
                ') AS report_rank '
                f'FROM {quoted_table_name}'
                ') ranked '
                'WHERE reports.id = ranked.id '
                'AND ranked.report_rank > 1'
            )
        )
        connection.execute(
            text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS {unique_index_name} '
                f'ON {quoted_table_name} (user_id, question_id)'
            )
        )
