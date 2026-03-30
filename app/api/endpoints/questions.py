from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import get_questions_table
from app.db.session import engine

router = APIRouter()


SENSITIVE_FIELDS = {'gabarito'}


def _apply_filters(stmt, table, subject, year, search):
    if subject and 'disciplina' in table.c:
        stmt = stmt.where(table.c.disciplina == subject)
    if year and 'ano' in table.c:
        stmt = stmt.where(table.c.ano == year)
    if search and 'enunciado' in table.c:
        stmt = stmt.where(table.c.enunciado.ilike(f'%{search}%'))
    return stmt


def _strip_sensitive(row: dict) -> dict:
    for field in SENSITIVE_FIELDS:
        row.pop(field, None)
    return row


@router.get('', dependencies=[Depends(get_current_user)])
def list_questions(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    subject: str | None = None,
    year: int | None = None,
    search: str | None = None,
    include_total: bool = False,
) -> dict:
    table = get_questions_table(engine, settings.question_table)
    stmt = select(table).limit(limit).offset(offset)
    stmt = _apply_filters(stmt, table, subject, year, search)

    rows = db.execute(stmt).mappings().all()
    data = [_strip_sensitive(dict(row)) for row in rows]

    if not include_total:
        return {'items': data, 'limit': limit, 'offset': offset}

    count_stmt = select(func.count()).select_from(table)
    count_stmt = _apply_filters(count_stmt, table, subject, year, search)
    total = db.execute(count_stmt).scalar_one()
    return {'items': data, 'limit': limit, 'offset': offset, 'total': total}


@router.get('/disciplinas', dependencies=[Depends(get_current_user)])
def list_disciplines(db: Session = Depends(get_db)) -> dict:
    table = get_questions_table(engine, settings.question_table)
    if 'disciplina' not in table.c:
        raise HTTPException(status_code=500, detail='No disciplina column found')

    stmt = (
        select(distinct(table.c.disciplina))
        .where(table.c.disciplina.is_not(None))
        .order_by(table.c.disciplina.asc())
    )
    rows = db.execute(stmt).scalars().all()
    items = [row for row in rows if str(row).strip()]
    return {'items': items}


@router.get('/subcategorias', dependencies=[Depends(get_current_user)])
def list_subcategories(
    db: Session = Depends(get_db),
    disciplina: str | None = None,
) -> dict:
    table = get_questions_table(engine, settings.question_table)
    if 'subcategoria' not in table.c:
        raise HTTPException(status_code=500, detail='No subcategoria column found')

    count_col = func.count().label('total')
    stmt = select(table.c.subcategoria, count_col).where(
        table.c.subcategoria.is_not(None)
    )
    if disciplina and 'disciplina' in table.c:
        stmt = stmt.where(table.c.disciplina == disciplina)

    stmt = stmt.group_by(table.c.subcategoria).order_by(table.c.subcategoria.asc())
    rows = db.execute(stmt).all()
    items = [
        {'nome': row[0], 'total': int(row[1])}
        for row in rows
        if str(row[0]).strip()
    ]
    return {'items': items}


@router.get('/{question_id}', dependencies=[Depends(get_current_user)])
def get_question(question_id: Any, db: Session = Depends(get_db)) -> dict:
    table = get_questions_table(engine, settings.question_table)
    id_column = table.c.id if 'id' in table.c else None
    if id_column is None:
        raise HTTPException(status_code=500, detail='No id column found')

    stmt = select(table).where(id_column == question_id)
    row = db.execute(stmt).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail='Question not found')
    return _strip_sensitive(dict(row))
