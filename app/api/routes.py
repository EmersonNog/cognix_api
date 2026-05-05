from fastapi import APIRouter

from app.api.endpoints.ai import router as ai_router
from app.api.endpoints.attempts import router as attempts_router
from app.api.endpoints.entitlements import router as entitlements_router
from app.api.endpoints.flashcards import router as flashcards_router
from app.api.endpoints.multiplayer import router as multiplayer_router
from app.api.endpoints.payments import router as payments_router
from app.api.endpoints.questions import router as questions_router
from app.api.endpoints.sessions import router as sessions_router
from app.api.endpoints.study_plan import router as study_plan_router
from app.api.endpoints.summaries import router as summaries_router
from app.api.endpoints.users import router as users_router
from app.api.endpoints.writing import router as writing_router

def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(
        entitlements_router,
        prefix='/entitlements',
        tags=['entitlements'],
    )
    router.include_router(users_router, prefix='/users', tags=['users'])
    router.include_router(ai_router, prefix='/ai', tags=['ai'])
    router.include_router(flashcards_router, prefix='/flashcards', tags=['flashcards'])
    router.include_router(attempts_router, prefix='/attempts', tags=['attempts'])
    router.include_router(
        multiplayer_router,
        prefix='/multiplayer',
        tags=['multiplayer'],
    )
    router.include_router(payments_router, prefix='/payments', tags=['payments'])
    router.include_router(questions_router, prefix='/questions', tags=['questions'])
    router.include_router(sessions_router, prefix='/sessions', tags=['sessions'])
    router.include_router(study_plan_router, prefix='/study-plan', tags=['study-plan'])
    router.include_router(summaries_router, prefix='/summaries', tags=['summaries'])
    router.include_router(writing_router, prefix='/writing', tags=['writing'])
    return router

api_router = create_api_router()
