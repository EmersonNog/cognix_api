from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.endpoints.helpers import require_user_context
from app.services.writing import (
    analyze_writing,
    count_writing_themes,
    get_monthly_writing_theme,
    list_writing_categories,
    list_writing_themes,
)

router = APIRouter()


@router.get('/themes', dependencies=[Depends(get_current_user)])
def get_writing_themes(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    total = count_writing_themes(db, category=category, search=search)
    return {
        'items': list_writing_themes(
            db,
            category=category,
            search=search,
            limit=limit,
            offset=offset,
        ),
        'monthly_theme': get_monthly_writing_theme(db),
        'categories': list_writing_categories(db),
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': offset + limit < total,
    }


@router.get('/themes/monthly', dependencies=[Depends(get_current_user)])
def get_monthly_theme(db: Session = Depends(get_db)) -> dict[str, object]:
    return get_monthly_writing_theme(db)


@router.get('/themes/categories', dependencies=[Depends(get_current_user)])
def get_theme_categories(db: Session = Depends(get_db)) -> dict[str, object]:
    return {'items': list_writing_categories(db)}


@router.post('/analyze')
def analyze_user_writing(
    payload: dict[str, object],
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, _firebase_uid = require_user_context(user_claims)
    result = analyze_writing(dict(payload), user_id=user_id)
    db.commit()
    return result
