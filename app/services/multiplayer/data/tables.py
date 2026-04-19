from app.core.config import settings
from app.db.models import (
    get_multiplayer_participants_table,
    get_multiplayer_rooms_table,
    get_questions_table,
)
from app.db.session import engine


def rooms_table():
    return get_multiplayer_rooms_table(settings.multiplayer_rooms_table)


def participants_table():
    return get_multiplayer_participants_table(settings.multiplayer_participants_table)


def questions_table():
    return get_questions_table(engine, settings.question_table)
