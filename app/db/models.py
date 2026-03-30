from sqlalchemy import MetaData, Table

metadata = MetaData()

def get_questions_table(engine, table_name: str) -> Table:
    return Table(table_name, metadata, autoload_with=engine)
