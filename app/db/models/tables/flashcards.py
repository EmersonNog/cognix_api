from sqlalchemy import Column, Integer, String, Table, Text, UniqueConstraint, text

from ..common import _id_column, _timestamp_columns, _user_columns, metadata

def get_flashcards_table(table_name: str) -> Table:
    existing = metadata.tables.get(table_name)
    if existing is not None:
        return existing

    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('subject', String(255), nullable=False, default='', server_default=text("''")),
        Column('front_text', Text, nullable=False),
        Column(
            'front_image_base64',
            Text,
            nullable=False,
            default='',
            server_default=text("''"),
        ),
        Column('back_text', Text, nullable=False),
        Column(
            'back_image_base64',
            Text,
            nullable=False,
            default='',
            server_default=text("''"),
        ),
        *_timestamp_columns(),
        extend_existing=True,
    )

def get_flashcard_deck_states_table(table_name: str) -> Table:
    existing = metadata.tables.get(table_name)
    if existing is not None:
        return existing

    return Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('subject', String(255), nullable=False, default='', server_default=text("''")),
        Column(
            'current_index',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column(
            'correct_count',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column(
            'wrong_count',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        *_timestamp_columns(),
        UniqueConstraint(
            'user_id',
            'subject',
            name=f'uq_{table_name}_user_subject',
        ),
        extend_existing=True,
    )