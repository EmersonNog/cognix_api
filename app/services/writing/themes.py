import json
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import get_writing_themes_table


def writing_themes_table():
    return get_writing_themes_table(settings.writing_themes_table)


def list_writing_themes(
    db: Session,
    category: str | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    table = writing_themes_table()
    stmt = _filtered_themes_statement(table, category=category, search=search)
    if offset > 0:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = db.execute(
        stmt.order_by(table.c.categoria, table.c.titulo)
    ).mappings().all()
    return [_serialize_theme(row) for row in rows]


def count_writing_themes(
    db: Session,
    category: str | None = None,
    search: str | None = None,
) -> int:
    table = writing_themes_table()
    stmt = _filtered_themes_statement(table, category=category, search=search)
    return int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0)


def list_writing_categories(db: Session) -> list[str]:
    table = writing_themes_table()
    rows = db.execute(
        select(table.c.categoria)
        .where(table.c.ativo.is_(True))
        .distinct()
        .order_by(table.c.categoria)
    ).all()
    return [row[0] for row in rows if row[0]]


def get_monthly_writing_theme(db: Session, today: date | None = None) -> dict:
    table = writing_themes_table()
    monthly = db.execute(
        select(table)
        .where(table.c.ativo.is_(True), table.c.redacao_do_mes.is_(True))
        .order_by(table.c.updated_at.desc(), table.c.titulo)
        .limit(1)
    ).mappings().first()
    if monthly:
        return _serialize_theme(monthly)

    themes = list_writing_themes(db)
    if not themes:
        return {}
    current = today or date.today()
    month_index = max(0, current.month - 1)
    return themes[month_index % len(themes)]


def _serialize_theme(row: dict) -> dict:
    return {
        'id': row['slug'],
        'title': row['titulo'],
        'category': row['categoria'],
        'description': row['descricao'],
        'keywords': _parse_keywords(row.get('palavras_chave_json')),
        'difficulty': row.get('dificuldade') or 'medio',
        'exam': row.get('prova') or 'ENEM',
    }


def _parse_keywords(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded if str(item).strip()]


def _normalize(value: object) -> str:
    if not isinstance(value, str):
        return ''
    return value.strip().lower()


def _filtered_themes_statement(
    table,
    category: str | None = None,
    search: str | None = None,
):
    stmt = select(table).where(table.c.ativo.is_(True))
    normalized_category = _normalize(category)
    if normalized_category:
        stmt = stmt.where(table.c.categoria == category.strip())

    normalized_search = _normalize(search)
    if normalized_search:
        pattern = f'%{search.strip()}%'
        stmt = stmt.where(
            or_(
                table.c.titulo.ilike(pattern),
                table.c.categoria.ilike(pattern),
                table.c.descricao.ilike(pattern),
                table.c.palavras_chave_json.ilike(pattern),
            )
        )
    return stmt
