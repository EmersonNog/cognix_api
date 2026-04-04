from sqlalchemy import Column, DateTime, Integer, MetaData, String

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
