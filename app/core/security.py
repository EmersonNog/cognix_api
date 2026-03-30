from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials

from app.core.config import settings


@lru_cache(maxsize=1)
def get_firebase_app() -> firebase_admin.App:
    if firebase_admin._apps:
        return firebase_admin.get_app()
    if settings.firebase_credentials:
        cred = credentials.Certificate(settings.firebase_credentials)
        return firebase_admin.initialize_app(cred)
    return firebase_admin.initialize_app()


def verify_firebase_token(token: str) -> dict:
    app = get_firebase_app()
    return auth.verify_id_token(token, app=app)
