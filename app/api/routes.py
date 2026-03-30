from fastapi import APIRouter

from app.api.endpoints.questions import router as questions_router

api_router = APIRouter()
api_router.include_router(questions_router, prefix='/questions', tags=['questions'])
