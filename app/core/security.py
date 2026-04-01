from functools import lru_cache

import firebase_admin
from firebase_admin import App, auth, credentials

from app.core.config import settings


def _get_firebase_credential():
    if not settings.firebase_credentials:
        return None
    return credentials.Certificate(settings.firebase_credentials)


@lru_cache(maxsize=1)
def get_firebase_app() -> App:
    if firebase_admin._apps:
        return firebase_admin.get_app()

    credential = _get_firebase_credential()
    if credential is not None:
        return firebase_admin.initialize_app(credential)

    return firebase_admin.initialize_app()


def verify_firebase_token(token: str) -> dict:
    return auth.verify_id_token(token, app=get_firebase_app())
