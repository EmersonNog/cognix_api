from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.datetime_utils import utc_now
from app.services.session_state import LEGACY_SESSION_STATE_VERSION

from .common import (
    _discipline_columns,
    _id_column,
    _timestamp_columns,
    _user_columns,
    metadata,
)


def get_questions_table(engine, table_name: str) -> Table:
    existing = metadata.tables.get(table_name)
    if existing is not None:
        return existing

    return Table(table_name, metadata, autoload_with=engine)


def get_users_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        Column('firebase_uid', String(255), nullable=False, unique=True, index=True),
        Column('email', String(320), nullable=True),
        Column('display_name', String(255), nullable=True),
        Column('provider', String(100), nullable=True),
        Column('coins_half_units', Integer, nullable=False, default=0),
        Column('equipped_avatar_seed', String(255), nullable=True),
        *_timestamp_columns(),
        extend_existing=True,
    )


def get_attempts_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('question_id', Integer, nullable=False, index=True),
        Column('selected_letter', String(2), nullable=False),
        Column('is_correct', Boolean, nullable=True),
        *_discipline_columns(nullable=True),
        Column('answered_at', DateTime(timezone=True), nullable=False, default=utc_now),
        UniqueConstraint('user_id', 'question_id', name=f'uq_{table_name}_user_q'),
        extend_existing=True,
    )


def get_attempt_history_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('question_id', Integer, nullable=False, index=True),
        Column('selected_letter', String(2), nullable=False),
        Column('is_correct', Boolean, nullable=True),
        *_discipline_columns(nullable=True),
        Column(
            'answered_at',
            DateTime(timezone=True),
            nullable=False,
            default=utc_now,
            index=True,
        ),
        Index(f'ix_{table_name}_user_answered_at', 'user_id', 'answered_at'),
        Index(
            f'ix_{table_name}_user_disc_sub_answered_at',
            'user_id',
            'discipline',
            'subcategory',
            'answered_at',
        ),
        extend_existing=True,
    )


def get_question_reports_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('question_id', Integer, nullable=False, index=True),
        Column('reason', String(80), nullable=False, index=True),
        Column('details', Text, nullable=True),
        *_discipline_columns(nullable=True),
        Column(
            'status',
            String(40),
            nullable=False,
            default='open',
            server_default=text("'open'"),
        ),
        *_timestamp_columns(),
        Index(f'ix_{table_name}_question_created_at', 'question_id', 'created_at'),
        Index(f'ix_{table_name}_user_created_at', 'user_id', 'created_at'),
        Index(f'ix_{table_name}_status_created_at', 'status', 'created_at'),
        UniqueConstraint(
            'user_id',
            'question_id',
            name=f'uq_{table_name}_user_question',
        ),
        extend_existing=True,
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


def get_user_coin_ledger_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('reason', String(100), nullable=False),
        Column('delta_half_units', Integer, nullable=False),
        Column('balance_after_half_units', Integer, nullable=False, default=0),
        Column('question_id', Integer, nullable=True),
        Column('avatar_seed', String(255), nullable=True),
        *_timestamp_columns(),
        Index(f'ix_{table_name}_user_created_at', 'user_id', 'created_at'),
        extend_existing=True,
    )


def get_user_avatar_inventory_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('avatar_seed', String(255), nullable=False),
        Column('acquired_via', String(100), nullable=False, default='purchase'),
        Column('cost_half_units', Integer, nullable=False, default=0),
        *_timestamp_columns(),
        UniqueConstraint('user_id', 'avatar_seed', name=f'uq_{table_name}_user_seed'),
        extend_existing=True,
    )


def get_user_study_plan_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('study_days_per_week', Integer, nullable=False, default=5),
        Column('minutes_per_day', Integer, nullable=False, default=60),
        Column('weekly_questions_goal', Integer, nullable=False, default=80),
        Column('focus_mode', String(50), nullable=False, default='constancia'),
        Column('preferred_period', String(50), nullable=False, default='flexivel'),
        Column('priority_disciplines_json', Text, nullable=False, default='[]'),
        *_timestamp_columns(),
        UniqueConstraint('user_id', name=f'uq_{table_name}_user'),
        extend_existing=True,
    )
