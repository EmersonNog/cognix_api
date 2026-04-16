from sqlalchemy import Column, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from ..common import (
    _discipline_columns,
    _id_column,
    _timestamp_columns,
    _user_columns,
    metadata,
)


def get_summaries_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_discipline_columns(),
        Column('payload_json', JSONB, nullable=False),
        *_timestamp_columns(),
        UniqueConstraint(
            'discipline',
            'subcategory',
            name=f'uq_{table_name}_disc_sub',
        ),
        extend_existing=True,
    )


def get_user_summaries_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        *_discipline_columns(),
        Column('payload_json', JSONB, nullable=False),
        *_timestamp_columns(),
        UniqueConstraint(
            'user_id',
            'discipline',
            'subcategory',
            name=f'uq_{table_name}_user_disc_sub',
        ),
        extend_existing=True,
    )
