from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import verify_firebase_token

from .db import get_db
from .users import sync_internal_user

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail='Missing Authorization')

    try:
        claims = verify_firebase_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid token')

    return sync_internal_user(db, claims)
