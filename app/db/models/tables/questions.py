from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Table, Text, UniqueConstraint, text

from app.core.datetime_utils import utc_now

from ..common import (
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
