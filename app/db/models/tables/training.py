from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Table, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.datetime_utils import utc_now
from app.services.session_state import LEGACY_SESSION_STATE_VERSION

from ..common import (
    _discipline_columns,
    _id_column,
    _timestamp_columns,
    _user_columns,
    metadata,
)


def get_sessions_table(table_name: str) -> Table:
    existing = metadata.tables.get(table_name)
    if existing is not None:
        return existing

    table = Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        *_discipline_columns(),
        Column('state_json', JSONB, nullable=False),
        Column(
            'state_version',
            Integer,
            nullable=False,
            default=LEGACY_SESSION_STATE_VERSION,
            server_default=text(str(LEGACY_SESSION_STATE_VERSION)),
        ),
        Column(
            'completed',
            Boolean,
            nullable=False,
            default=False,
            server_default=text('false'),
        ),
        Column(
            'answered_questions',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column(
            'total_questions',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column(
            'elapsed_seconds',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column('saved_at', DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        UniqueConstraint(
            'user_id',
            'discipline',
            'subcategory',
            name=f'uq_{table_name}_user_session',
        ),
    )
    Index(
        f'ix_{table_name}_user_effective_saved_at',
        table.c.user_id,
        func.coalesce(table.c.saved_at, table.c.updated_at),
    )
    Index(
        f'ix_{table_name}_user_completed_effective_saved_at',
        table.c.user_id,
        table.c.completed,
        func.coalesce(table.c.saved_at, table.c.updated_at),
    )
    return table


def get_session_history_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        *_discipline_columns(),
        Column('session_key', String(64), nullable=False),
        Column('total_questions', Integer, nullable=False, default=0),
        Column('answered_questions', Integer, nullable=False, default=0),
        Column('correct_answers', Integer, nullable=False, default=0),
        Column('wrong_answers', Integer, nullable=False, default=0),
        Column('elapsed_seconds', Integer, nullable=False, default=0),
        Column(
            'completed_at',
            DateTime(timezone=True),
            nullable=False,
            default=utc_now,
            index=True,
        ),
        Index(f'ix_{table_name}_user_completed_at', 'user_id', 'completed_at'),
        Index(
            f'ix_{table_name}_user_disc_sub_completed_at',
            'user_id',
            'discipline',
            'subcategory',
            'completed_at',
        ),
        UniqueConstraint(
            'user_id',
            'discipline',
            'subcategory',
            'session_key',
            name=f'uq_{table_name}_user_disc_sub_key',
        ),
        extend_existing=True,
    )
