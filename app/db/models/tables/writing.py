from sqlalchemy import Boolean, Column, Index, String, Table, Text, text

from ..common import _id_column, _timestamp_columns, metadata


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
