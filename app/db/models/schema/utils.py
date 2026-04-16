from sqlalchemy import inspect


def quote_identifier(engine, identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote(identifier)


def table_exists(engine, table_name: str) -> bool:
    return table_name in inspect(engine).get_table_names()


def get_columns_by_name(engine, table_name: str) -> dict[str, dict]:
    return {
        column['name']: column
        for column in inspect(engine).get_columns(table_name)
    }


def get_column_names(engine, table_name: str) -> set[str]:
    return set(get_columns_by_name(engine, table_name))
