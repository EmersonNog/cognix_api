from sqlalchemy import text

from .utils import get_column_names, quote_identifier, table_exists


def ensure_payment_subscriptions_schema(
    engine,
    payment_subscriptions_table_name: str,
) -> None:
    if not table_exists(engine, payment_subscriptions_table_name):
        return

    columns = get_column_names(engine, payment_subscriptions_table_name)
    if 'current_period_ends_at' in columns:
        return

    quoted_table_name = quote_identifier(engine, payment_subscriptions_table_name)
    with engine.begin() as connection:
        connection.execute(
            text(
                f'ALTER TABLE {quoted_table_name} '
                'ADD COLUMN IF NOT EXISTS current_period_ends_at TIMESTAMPTZ'
            )
        )
