from app.core.config import settings
from app.db.models import get_flashcard_deck_states_table, get_flashcards_table


def flashcards_table():
    return get_flashcards_table(settings.flashcards_table)


def flashcard_deck_states_table():
    return get_flashcard_deck_states_table(settings.flashcard_deck_states_table)
