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
    text,
)

from app.core.datetime_utils import utc_now

from ..common import _id_column, _timestamp_columns, _user_columns, metadata


def get_writing_themes_table(table_name: str) -> Table:
    existing = metadata.tables.get(table_name)
    if existing is not None:
        return existing

    return Table(
        table_name,
        metadata,
        _id_column(),
        Column('slug', String(120), nullable=False, unique=True, index=True),
        Column('titulo', String(255), nullable=False),
        Column('categoria', String(80), nullable=False, index=True),
        Column('descricao', Text, nullable=False),
        Column('palavras_chave_json', Text, nullable=False, default='[]'),
        Column(
            'dificuldade',
            String(40),
            nullable=False,
            default='medio',
            server_default=text("'medio'"),
        ),
        Column(
            'prova',
            String(40),
            nullable=False,
            default='ENEM',
            server_default=text("'ENEM'"),
        ),
        Column(
            'ativo',
            Boolean,
            nullable=False,
            default=True,
            server_default=text('true'),
        ),
        Column(
            'redacao_do_mes',
            Boolean,
            nullable=False,
            default=False,
            server_default=text('false'),
        ),
        *_timestamp_columns(),
        Index(f'ix_{table_name}_ativo_categoria', 'ativo', 'categoria'),
        Index(
            f'ix_{table_name}_ativo_redacao_do_mes',
            'ativo',
            'redacao_do_mes',
        ),
        extend_existing=True,
    )


def get_writing_submissions_table(table_name: str) -> Table:
    existing = metadata.tables.get(table_name)
    if existing is not None:
        return existing

    table = Table(
        table_name,
        metadata,
        _id_column(),
        *_user_columns(),
        Column('theme_slug', String(120), nullable=False),
        Column('theme_title', String(255), nullable=False),
        Column('theme_category', String(80), nullable=False),
        Column(
            'status',
            String(32),
            nullable=False,
            default='active',
            server_default=text("'active'"),
        ),
        Column(
            'current_version',
            Integer,
            nullable=False,
            default=0,
            server_default=text('0'),
        ),
        Column('latest_version_id', Integer, nullable=True),
        Column('latest_score', Integer, nullable=True),
        Column('latest_summary', Text, nullable=True),
        Column('last_analyzed_at', DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        extend_existing=True,
    )
    Index(
        f'ix_{table_name}_user_last_analyzed_at',
        table.c.user_id,
        table.c.last_analyzed_at,
    )
    return table


def get_writing_submission_versions_table(table_name: str) -> Table:
    existing = metadata.tables.get(table_name)
    if existing is not None:
        return existing

    table = Table(
        table_name,
        metadata,
        _id_column(),
        Column('submission_id', Integer, nullable=False, index=True),
        Column('version_number', Integer, nullable=False),
        Column('thesis', Text, nullable=False, default='', server_default=text("''")),
        Column('repertoire', Text, nullable=False, default='', server_default=text("''")),
        Column('argument_one', Text, nullable=False, default='', server_default=text("''")),
        Column('argument_two', Text, nullable=False, default='', server_default=text("''")),
        Column('intervention', Text, nullable=False, default='', server_default=text("''")),
        Column('final_text', Text, nullable=False),
        Column('estimated_score', Integer, nullable=False),
        Column('summary', Text, nullable=False),
        Column('checklist_json', Text, nullable=False),
        Column('competencies_json', Text, nullable=False),
        Column('rewrite_suggestions_json', Text, nullable=False),
        Column(
            'analyzed_at',
            DateTime(timezone=True),
            nullable=False,
            default=utc_now,
            server_default=text('CURRENT_TIMESTAMP'),
        ),
        *_timestamp_columns(),
        UniqueConstraint(
            'submission_id',
            'version_number',
            name=f'uq_{table_name}_submission_version',
        ),
        extend_existing=True,
    )
    Index(
        f'ix_{table_name}_submission_analyzed_at',
        table.c.submission_id,
        table.c.analyzed_at,
    )
    return table
