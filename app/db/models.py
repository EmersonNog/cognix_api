from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from app.core.datetime_utils import utc_now

metadata = MetaData()


def _id_column() -> Column:
    return Column('id', Integer, primary_key=True, autoincrement=True)


def _timestamp_columns() -> list[Column]:
    return [
        Column('created_at', DateTime(timezone=True), nullable=False, default=utc_now),
        Column(
            'updated_at',
            DateTime(timezone=True),
            nullable=False,
            default=utc_now,
            onupdate=utc_now,
        ),
    ]


def _user_columns() -> list[Column]:
    return [
        Column('user_id', Integer, nullable=False, index=True),
        Column('firebase_uid', String(255), nullable=False, index=True),
    ]


def _discipline_columns(nullable: bool = False) -> list[Column]:
    return [
        Column('discipline', String(255), nullable=nullable),
        Column('subcategory', String(255), nullable=nullable),
    ]


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


def get_sessions_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        *_discipline_columns(),
        Column('state_json', Text, nullable=False),
        *_timestamp_columns(),
        UniqueConstraint(
            'user_id',
            'discipline',
            'subcategory',
            name=f'uq_{table_name}_user_session',
        ),
        extend_existing=True,
    )


def get_summaries_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        *_discipline_columns(),
        Column('payload_json', Text, nullable=False),
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
        Column('payload_json', Text, nullable=False),
        *_timestamp_columns(),
        UniqueConstraint(
            'user_id',
            'discipline',
            'subcategory',
            name=f'uq_{table_name}_user_disc_sub',
        ),
        extend_existing=True,
    )


def create_internal_tables(
    engine,
    users_table_name: str,
    attempts_table_name: str,
    sessions_table_name: str,
    summaries_table_name: str,
    user_summaries_table_name: str,
) -> None:
    get_users_table(users_table_name)
    get_attempts_table(attempts_table_name)
    get_sessions_table(sessions_table_name)
    get_summaries_table(summaries_table_name)
    get_user_summaries_table(user_summaries_table_name)
    metadata.create_all(
        bind=engine,
        tables=[
            metadata.tables[users_table_name],
            metadata.tables[attempts_table_name],
            metadata.tables[sessions_table_name],
            metadata.tables[summaries_table_name],
            metadata.tables[user_summaries_table_name],
        ],
    )
