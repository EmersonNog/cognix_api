from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import get_questions_table
from app.db.session import engine

router = APIRouter()

SENSITIVE_FIELDS = {'gabarito'}


def _get_questions_table():
    return get_questions_table(engine, settings.question_table)


def _require_column(table, column_name: str) -> None:
    if column_name not in table.c:
        raise HTTPException(status_code=500, detail=f'No {column_name} column found')


def _get_id_column(table):
    id_column = table.c.id if 'id' in table.c else None
    if id_column is None:
        raise HTTPException(status_code=500, detail='No id column found')
    return id_column


def _apply_filters(stmt, table, subject, subcategory, year, search):
    if subject and 'disciplina' in table.c:
        stmt = stmt.where(table.c.disciplina == subject)
    if subcategory and 'subcategoria' in table.c:
        stmt = stmt.where(table.c.subcategoria == subcategory)
    if year and 'ano' in table.c:
        stmt = stmt.where(table.c.ano == year)
    if search and 'enunciado' in table.c:
        stmt = stmt.where(table.c.enunciado.ilike(f'%{search}%'))
    return stmt


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='ignore')
    return value


def _serialize_row(row: dict) -> dict:
    sanitized = dict(row)
    for field in SENSITIVE_FIELDS:
        sanitized.pop(field, None)
    return {key: _serialize_value(value) for key, value in sanitized.items()}


def _serialize_rows(rows) -> list[dict]:
    return [_serialize_row(dict(row)) for row in rows]


def _parse_ids(ids: str) -> list[int]:
    raw_ids = [item.strip() for item in ids.split(',') if item.strip()]
    try:
        return [int(item) for item in raw_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail='ids must be integers')


@router.get('', dependencies=[Depends(get_current_user)])
def list_questions(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    subject: str | None = None,
    subcategory: str | None = None,
    year: int | None = None,
    search: str | None = None,
    include_total: bool = False,
) -> dict:
    table = _get_questions_table()
    stmt = select(table)
    stmt = _apply_filters(stmt, table, subject, subcategory, year, search)
    if 'id' in table.c:
        stmt = stmt.order_by(table.c.id.asc())
    stmt = stmt.limit(limit).offset(offset)

    rows = db.execute(stmt).mappings().all()
    data = _serialize_rows(rows)

    if not include_total:
        return {'items': data, 'limit': limit, 'offset': offset}

    count_stmt = select(func.count()).select_from(table)
    count_stmt = _apply_filters(count_stmt, table, subject, subcategory, year, search)
    total = db.execute(count_stmt).scalar_one()
    return {'items': data, 'limit': limit, 'offset': offset, 'total': total}


@router.get('/disciplines', dependencies=[Depends(get_current_user)])
def list_disciplines(db: Session = Depends(get_db)) -> dict:
    table = _get_questions_table()
    _require_column(table, 'disciplina')

    stmt = (
        select(distinct(table.c.disciplina))
        .where(table.c.disciplina.is_not(None))
        .order_by(table.c.disciplina.asc())
    )
    rows = db.execute(stmt).scalars().all()
    items = [row for row in rows if str(row).strip()]
    return {'items': items}


@router.get('/subcategories', dependencies=[Depends(get_current_user)])
def list_subcategories(
    db: Session = Depends(get_db),
    discipline: str | None = None,
) -> dict:
    table = _get_questions_table()
    _require_column(table, 'subcategoria')

    count_col = func.count().label('total')
    stmt = select(table.c.subcategoria, count_col).where(
        table.c.subcategoria.is_not(None)
    )
    if discipline and 'disciplina' in table.c:
        stmt = stmt.where(table.c.disciplina == discipline)

    stmt = stmt.group_by(table.c.subcategoria).order_by(table.c.subcategoria.asc())
    rows = db.execute(stmt).all()
    items = [
        {'name': row[0], 'total': int(row[1]), 'discipline': discipline or ''}
        for row in rows
        if str(row[0]).strip()
    ]
    return {'items': items}


@router.get('/by_ids', dependencies=[Depends(get_current_user)])
def list_questions_by_ids(
    ids: str = Query(..., description='Comma-separated question ids'),
    db: Session = Depends(get_db),
) -> dict:
    table = _get_questions_table()
    id_column = _get_id_column(table)
    id_list = _parse_ids(ids)

    if not id_list:
        return {'items': []}

    ordering = case({value: index for index, value in enumerate(id_list)}, value=id_column)
    stmt = select(table).where(id_column.in_(id_list)).order_by(ordering)
    rows = db.execute(stmt).mappings().all()
    return {'items': _serialize_rows(rows)}


@router.get('/{question_id}', dependencies=[Depends(get_current_user)])
def get_question(question_id: Any, db: Session = Depends(get_db)) -> dict:
    table = _get_questions_table()
    id_column = _get_id_column(table)

    stmt = select(table).where(id_column == question_id)
    row = db.execute(stmt).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail='Question not found')
    return _serialize_row(dict(row))
