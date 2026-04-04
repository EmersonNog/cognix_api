from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    inspect,
    text,
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


def ensure_internal_schema(engine, users_table_name: str) -> None:
    inspector = inspect(engine)
    if users_table_name not in inspector.get_table_names():
        return

    column_names = {
        column['name']
        for column in inspector.get_columns(users_table_name)
    }
    statements: list[str] = []

    if 'coins_half_units' not in column_names:
        statements.append(
            f'ALTER TABLE {users_table_name} '
            'ADD COLUMN IF NOT EXISTS coins_half_units INTEGER NOT NULL DEFAULT 0'
        )
    if 'equipped_avatar_seed' not in column_names:
        statements.append(
            f'ALTER TABLE {users_table_name} '
            'ADD COLUMN IF NOT EXISTS equipped_avatar_seed VARCHAR(255)'
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def create_internal_tables(
    engine,
    users_table_name: str,
    attempts_table_name: str,
    attempt_history_table_name: str,
    sessions_table_name: str,
    session_history_table_name: str,
    summaries_table_name: str,
    user_summaries_table_name: str,
    user_coin_ledger_table_name: str,
    user_avatar_inventory_table_name: str,
) -> None:
    get_users_table(users_table_name)
    get_attempts_table(attempts_table_name)
    get_attempt_history_table(attempt_history_table_name)
    get_sessions_table(sessions_table_name)
    get_session_history_table(session_history_table_name)
    get_summaries_table(summaries_table_name)
    get_user_summaries_table(user_summaries_table_name)
    get_user_coin_ledger_table(user_coin_ledger_table_name)
    get_user_avatar_inventory_table(user_avatar_inventory_table_name)
    metadata.create_all(
        bind=engine,
        tables=[
            metadata.tables[users_table_name],
            metadata.tables[attempts_table_name],
            metadata.tables[attempt_history_table_name],
            metadata.tables[sessions_table_name],
            metadata.tables[session_history_table_name],
            metadata.tables[summaries_table_name],
            metadata.tables[user_summaries_table_name],
            metadata.tables[user_coin_ledger_table_name],
            metadata.tables[user_avatar_inventory_table_name],
        ],
    )
    ensure_internal_schema(engine, users_table_name)
