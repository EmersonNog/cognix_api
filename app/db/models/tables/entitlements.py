from sqlalchemy import Column, DateTime, Index, Integer, String, Table, UniqueConstraint

from ..common import _id_column, _timestamp_columns, metadata

def get_user_access_grants_table(table_name: str) -> Table:
    if table_name in metadata.tables:
        return metadata.tables[table_name]

    return Table(
        table_name,
        metadata,
        _id_column(),
        Column('user_id', Integer, nullable=False, index=True),
        Column('firebase_uid', String(255), nullable=False, index=True),
        Column('grant_type', String(64), nullable=False),
        Column('status', String(64), nullable=False, default='active'),
        Column('starts_at', DateTime(timezone=True), nullable=False),
        Column('ends_at', DateTime(timezone=True), nullable=False),
        Column('revoked_at', DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        UniqueConstraint(
            'user_id',
            'grant_type',
            name=f'uq_{table_name}_user_grant_type',
        ),
        UniqueConstraint(
            'firebase_uid',
            'grant_type',
            name=f'uq_{table_name}_firebase_grant_type',
        ),
        Index(f'ix_{table_name}_user_status', 'user_id', 'status'),
        Index(f'ix_{table_name}_grant_status', 'grant_type', 'status'),
        extend_existing=True,
    )
