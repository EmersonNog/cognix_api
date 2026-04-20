from fastapi import HTTPException
from sqlalchemy.orm import Session

from .gemini import gemini_available as _gemini_available
from .gemini import generate_with_gemini
from .normalize import normalize_writing_feedback
from .prompt import build_writing_prompt
from .submissions import store_writing_analysis
from .validation import validate_writing_payload


def gemini_available() -> bool:
    return _gemini_available()


def analyze_writing(
    payload: dict,
    *,
    user_id: int,
    firebase_uid: str | None,
    db: Session,
) -> dict:
    _ensure_gemini_available()
    validate_writing_payload(payload)

    response_payload = _generate_with_gemini(build_writing_prompt(payload, user_id))
    normalized_feedback = normalize_writing_feedback(response_payload)
    submission_id = _parse_submission_id(payload)

    return store_writing_analysis(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        payload=payload,
        feedback=normalized_feedback,
        submission_id=submission_id,
    )


def _ensure_gemini_available() -> None:
    if not gemini_available():
        raise HTTPException(status_code=503, detail='Gemini API key is not configured')


def _parse_submission_id(payload: dict) -> int | None:
    raw_submission_id = payload.get('submission_id')
    if raw_submission_id is None:
        return None

    try:
        return int(raw_submission_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail='submission_id is invalid') from exc


def _generate_with_gemini(prompt: str) -> dict:
    return generate_with_gemini(prompt)
