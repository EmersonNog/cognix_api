from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Table,
    UniqueConstraint,
    text,
)

from app.core.datetime_utils import utc_now

from ..common import _id_column, _timestamp_columns, _user_columns, metadata


def get_multiplayer_rooms_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        Column('pin', String(6), nullable=False, unique=True, index=True),
        Column('host_user_id', Integer, nullable=False, index=True),
        Column('host_firebase_uid', String(255), nullable=False, index=True),
        Column(
            'status',
            String(40),
            nullable=False,
            default='waiting',
            server_default=text("'waiting'"),
            index=True,
        ),
        Column(
            'max_participants',
            Integer,
            nullable=False,
            default=8,
            server_default=text('8'),
        ),
        Column('question_ids', JSON, nullable=True),
        Column(
            'current_question_index',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column(
            'round_duration_seconds',
            Integer,
            nullable=False,
            default=60,
            server_default=text('60'),
        ),
        Column('started_at', DateTime(timezone=True), nullable=True),
        Column('round_started_at', DateTime(timezone=True), nullable=True),
        Column('finished_at', DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        Index(f'ix_{table_name}_pin_status', 'pin', 'status'),
        Index(
            f'ix_{table_name}_host_status_created_at',
            'host_user_id',
            'status',
            'created_at',
        ),
        extend_existing=True,
    )


def get_multiplayer_participants_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        Column('room_id', Integer, nullable=False, index=True),
        *_user_columns(),
        Column('display_name', String(255), nullable=True),
        Column(
            'role',
            String(40),
            nullable=False,
            default='player',
            server_default=text("'player'"),
        ),
        Column(
            'status',
            String(40),
            nullable=False,
            default='joined',
            server_default=text("'joined'"),
            index=True,
        ),
        Column(
            'score',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column(
            'correct_answers',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column(
            'answered_current_question',
            Boolean,
            nullable=False,
            default=False,
            server_default=text('false'),
        ),
        Column('current_question_id', Integer, nullable=True),
        Column('selected_letter', String(2), nullable=True),
        Column('last_answered_at', DateTime(timezone=True), nullable=True),
        Column('joined_at', DateTime(timezone=True), nullable=False, default=utc_now),
        Column('removed_at', DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        UniqueConstraint(
            'room_id',
            'user_id',
            name=f'uq_{table_name}_room_user',
        ),
        Index(f'ix_{table_name}_room_status', 'room_id', 'status'),
        extend_existing=True,
    )
