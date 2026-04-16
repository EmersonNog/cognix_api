import json

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON, JSONB

from .utils import get_columns_by_name, quote_identifier, table_exists


def _load_normalized_summary_payload(row: dict[str, object]) -> dict[str, object]:
    from app.services.summaries.payloads import (
        default_summary,
        normalize_summary_payload,
    )

    payload_json = row.get('payload_json')
    if isinstance(payload_json, dict):
        return normalize_summary_payload(payload_json)

    if isinstance(payload_json, str):
        try:
            decoded = json.loads(payload_json)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            return normalize_summary_payload(decoded)

    discipline = str(row.get('discipline') or '').strip()
    subcategory = str(row.get('subcategory') or '').strip()
    return default_summary(discipline, subcategory)


def ensure_summary_payload_schema(engine, table_name: str) -> None:
    if not table_exists(engine, table_name):
        return

    quoted_table_name = quote_identifier(engine, table_name)
    columns = get_columns_by_name(engine, table_name)
    payload_column = columns.get('payload_json')
    if payload_column is None:
        return

    if isinstance(payload_column['type'], (JSON, JSONB)):
        return

    with engine.begin() as connection:
        rows = connection.execute(
            text(
                f'SELECT id, discipline, subcategory, payload_json '
                f'FROM {quoted_table_name}'
            )
        ).mappings().all()

        normalized_payloads = [
            {
                'id': row['id'],
                'payload_json': _load_normalized_summary_payload(row),
            }
            for row in rows
        ]

        for row in normalized_payloads:
            connection.execute(
                text(
                    f'UPDATE {quoted_table_name} '
                    'SET payload_json = :payload_json '
                    'WHERE id = :id'
                ),
                {
                    'id': row['id'],
                    'payload_json': json.dumps(
                        row['payload_json'],
                        ensure_ascii=True,
                    ),
                },
            )

        connection.execute(
            text(
                f'ALTER TABLE {quoted_table_name} '
                'ALTER COLUMN payload_json TYPE JSONB '
                'USING payload_json::jsonb'
            )
        )
