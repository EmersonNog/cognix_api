from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.endpoints.helpers import require_user_context
from app.services.flashcards import (
    create_flashcard,
    delete_flashcard_deck,
    list_flashcard_deck_states,
    list_flashcards,
    save_flashcard_deck_progress,
)

router = APIRouter()


class CreateFlashcardRequest(BaseModel):
    subject: str = ''
    front_text: str = ''
    back_text: str = ''
    front_image_base64: str = ''
    back_image_base64: str = ''


class SaveFlashcardDeckProgressRequest(BaseModel):
    subject: str = ''
    current_index: int = Field(default=0)
    correct_count: int = Field(default=0)
    wrong_count: int = Field(default=0)


@router.get('')
def get_flashcards(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, _firebase_uid = require_user_context(user_claims)
    return {
        'items': list_flashcards(db, user_id=user_id),
        'deck_states': list_flashcard_deck_states(db, user_id=user_id),
    }


@router.post('')
def create_user_flashcard(
    payload: CreateFlashcardRequest,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    result = create_flashcard(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        subject=payload.subject,
        front_text=payload.front_text,
        back_text=payload.back_text,
        front_image_base64=payload.front_image_base64,
        back_image_base64=payload.back_image_base64,
    )
    db.commit()
    return result


@router.delete('/deck')
def delete_user_flashcard_deck(
    subject: str = Query(default=''),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, _firebase_uid = require_user_context(user_claims)
    result = delete_flashcard_deck(
        db,
        user_id=user_id,
        subject=subject,
    )
    db.commit()
    return result


@router.post('/deck/progress')
def save_user_flashcard_deck_progress(
    payload: SaveFlashcardDeckProgressRequest,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    result = save_flashcard_deck_progress(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        subject=payload.subject,
        current_index=payload.current_index,
        correct_count=payload.correct_count,
        wrong_count=payload.wrong_count,
    )
    db.commit()
    return result
