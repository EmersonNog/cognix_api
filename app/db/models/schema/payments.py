from sqlalchemy import text

from .utils import get_column_names, quote_identifier, table_exists


def ensure_payment_subscriptions_schema(
    engine,
    payment_subscriptions_table_name: str,
) -> None:
    for column_name, column_spec in (
        ('current_period_ends_at', 'TIMESTAMPTZ'),
        ('attribution_json', 'TEXT'),
        ('utmify_status', 'VARCHAR(64)'),
        ('utmify_sent_at', 'TIMESTAMPTZ'),
        ('utmify_last_error', 'TEXT'),
    ):
        _ensure_column_exists(
            engine,
            payment_subscriptions_table_name,
            column_name=column_name,
            column_spec=column_spec,
        )


def ensure_google_play_subscriptions_schema(
    engine,
    google_play_subscriptions_table_name: str,
) -> None:
    _ensure_column_exists(
        engine,
        google_play_subscriptions_table_name,
        column_name='offer_id',
        column_spec='VARCHAR(255)',
    )


def _ensure_column_exists(
    engine,
    table_name: str,
    *,
    column_name: str,
    column_spec: str,
) -> None:
    if not table_exists(engine, table_name):
        return

    columns = get_column_names(engine, table_name)
    if column_name in columns:
        return

    quoted_table_name = quote_identifier(engine, table_name)
    with engine.begin() as connection:
        connection.execute(
            text(
                f'ALTER TABLE {quoted_table_name} '
                f'ADD COLUMN IF NOT EXISTS {column_name} {column_spec}'
            )
        )
