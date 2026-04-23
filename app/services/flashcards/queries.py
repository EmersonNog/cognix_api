from sqlalchemy import select
from sqlalchemy.orm import Session

from .serializers import serialize_flashcard, serialize_flashcard_deck_state
from .tables import flashcard_deck_states_table, flashcards_table


def list_flashcards(db: Session, *, user_id: int) -> list[dict]:
    flashcards = flashcards_table()
    rows = db.execute(
        select(flashcards)
        .where(flashcards.c.user_id == user_id)
        .order_by(flashcards.c.updated_at.desc(), flashcards.c.id.desc())
    ).mappings().all()
    return [serialize_flashcard(row) for row in rows]


def list_flashcard_deck_states(db: Session, *, user_id: int) -> list[dict]:
    deck_states = flashcard_deck_states_table()
    rows = db.execute(
        select(deck_states)
        .where(deck_states.c.user_id == user_id)
        .order_by(deck_states.c.updated_at.desc(), deck_states.c.id.desc())
    ).mappings().all()
    return [serialize_flashcard_deck_state(row) for row in rows]
