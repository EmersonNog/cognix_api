from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from .serializers import serialize_flashcard, serialize_flashcard_deck_state
from .tables import flashcard_deck_states_table, flashcards_table


_DEFAULT_SUBJECT = 'Sem materia'


def _normalize_subject(subject: str) -> str:
    normalized = str(subject or '').strip()
    return normalized or _DEFAULT_SUBJECT


def _normalize_text(value: str | None) -> str:
    return str(value or '').strip()


def _normalize_non_negative_int(value: int | None) -> int:
    return max(0, int(value or 0))


def _get_flashcard_row(db: Session, *, flashcard_id: int, user_id: int) -> dict:
    flashcards = flashcards_table()
    return db.execute(
        select(flashcards).where(
            flashcards.c.id == flashcard_id,
            flashcards.c.user_id == user_id,
        )
    ).mappings().one()


def _get_deck_state_row(db: Session, *, deck_state_id: int) -> dict:
    deck_states = flashcard_deck_states_table()
    return db.execute(
        select(deck_states).where(deck_states.c.id == deck_state_id)
    ).mappings().one()


def create_flashcard(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    subject: str,
    front_text: str,
    back_text: str,
    front_image_base64: str = '',
    back_image_base64: str = '',
) -> dict:
    normalized_front = _normalize_text(front_text)
    normalized_back = _normalize_text(back_text)
    if not normalized_front:
        raise HTTPException(status_code=400, detail='front_text is required')
    if not normalized_back:
        raise HTTPException(status_code=400, detail='back_text is required')

    flashcards = flashcards_table()
    now = utc_now()
    insert_payload = {
        'user_id': user_id,
        'firebase_uid': _normalize_text(firebase_uid),
        'subject': _normalize_subject(subject),
        'front_text': normalized_front,
        'front_image_base64': _normalize_text(front_image_base64),
        'back_text': normalized_back,
        'back_image_base64': _normalize_text(back_image_base64),
        'created_at': now,
        'updated_at': now,
    }
    result = db.execute(flashcards.insert(), insert_payload)
    flashcard_id = int(result.inserted_primary_key[0])
    return serialize_flashcard(
        _get_flashcard_row(db, flashcard_id=flashcard_id, user_id=user_id)
    )


def delete_flashcard_deck(
    db: Session,
    *,
    user_id: int,
    subject: str,
) -> dict:
    normalized_subject = _normalize_subject(subject)
    flashcards = flashcards_table()
    deck_states = flashcard_deck_states_table()

    deleted_count = int(
        db.execute(
            select(func.count())
            .select_from(flashcards)
            .where(
                flashcards.c.user_id == user_id,
                flashcards.c.subject == normalized_subject,
            )
        ).scalar_one()
    )

    db.execute(
        delete(flashcards).where(
            flashcards.c.user_id == user_id,
            flashcards.c.subject == normalized_subject,
        )
    )
    db.execute(
        delete(deck_states).where(
            deck_states.c.user_id == user_id,
            deck_states.c.subject == normalized_subject,
        )
    )
    return {
        'subject': normalized_subject,
        'deleted_count': deleted_count,
    }


def save_flashcard_deck_progress(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    subject: str,
    current_index: int,
    correct_count: int,
    wrong_count: int,
) -> dict:
    normalized_subject = _normalize_subject(subject)
    deck_states = flashcard_deck_states_table()
    now = utc_now()

    payload = {
        'user_id': user_id,
        'firebase_uid': _normalize_text(firebase_uid),
        'subject': normalized_subject,
        'current_index': _normalize_non_negative_int(current_index),
        'correct_count': _normalize_non_negative_int(correct_count),
        'wrong_count': _normalize_non_negative_int(wrong_count),
        'updated_at': now,
    }

    existing = db.execute(
        select(deck_states.c.id).where(
            deck_states.c.user_id == user_id,
            deck_states.c.subject == normalized_subject,
        )
    ).first()
    if existing:
        deck_state_id = int(existing[0])
        db.execute(
            deck_states.update()
            .where(deck_states.c.id == deck_state_id)
            .values(**payload)
        )
        return serialize_flashcard_deck_state(
            _get_deck_state_row(db, deck_state_id=deck_state_id)
        )

    insert_payload = {
        **payload,
        'created_at': now,
    }
    try:
        result = db.execute(deck_states.insert(), insert_payload)
        deck_state_id = int(result.inserted_primary_key[0])
    except IntegrityError:
        db.rollback()
        db.execute(
            deck_states.update()
            .where(
                deck_states.c.user_id == user_id,
                deck_states.c.subject == normalized_subject,
            )
            .values(**payload)
        )
        deck_state_id = int(
            db.execute(
                select(deck_states.c.id).where(
                    deck_states.c.user_id == user_id,
                    deck_states.c.subject == normalized_subject,
                )
            ).scalar_one()
        )

    return serialize_flashcard_deck_state(
        _get_deck_state_row(db, deck_state_id=deck_state_id)
    )
