from sqlalchemy import Column, Index, Integer, String, Table, Text, UniqueConstraint

from ..common import _id_column, _timestamp_columns, _user_columns, metadata


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
        Column('profile_ai_insight_json', Text, nullable=True),
        Column('profile_ai_insight_fingerprint', String(64), nullable=True),
        Column('profile_ai_insight_generated_at', Text, nullable=True),
        *_timestamp_columns(),
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
