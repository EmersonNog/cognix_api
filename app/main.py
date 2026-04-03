from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.db.models import create_internal_tables
from app.db.session import engine


def _configure_middlewares(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )


def _register_routes(app: FastAPI) -> None:
    app.include_router(api_router)

    @app.get('/health')
    def health() -> dict:
        return {'status': 'ok'}


def _create_internal_tables() -> None:
    create_internal_tables(
        engine,
        settings.users_table,
        settings.attempts_table,
        settings.attempt_history_table,
        settings.sessions_table,
        settings.session_history_table,
        settings.summaries_table,
        settings.user_summaries_table,
    )


def create_app() -> FastAPI:
    app = FastAPI(title='Cognix API', version='0.1.0')

    _configure_middlewares(app)
    _register_routes(app)

    @app.on_event('startup')
    def on_startup() -> None:
        _create_internal_tables()

    return app


app = create_app()
