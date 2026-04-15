from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

LEGACY_SESSION_STATE_VERSION = 1
CURRENT_SESSION_STATE_VERSION = 2
SUPPORTED_SESSION_STATE_VERSIONS = {
    LEGACY_SESSION_STATE_VERSION,
    CURRENT_SESSION_STATE_VERSION,
}


class SessionStateValidationError(ValueError):
    pass


class SessionCompletionResultModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    totalQuestions: int = Field(ge=0)
    answeredQuestions: int = Field(ge=0)
    correctAnswers: int = Field(ge=0)
    wrongAnswers: int = Field(ge=0)
    elapsedSeconds: int = Field(ge=0)

    @field_validator(
        'totalQuestions',
        'answeredQuestions',
        'correctAnswers',
        'wrongAnswers',
        'elapsedSeconds',
        mode='before',
    )
    @classmethod
    def _coerce_non_negative_int(cls, value: object) -> int:
        return _coerce_non_negative_int(value)


class SessionStateBaseModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stateVersion: int = LEGACY_SESSION_STATE_VERSION
    discipline: str
    subcategory: str
    savedAt: int = Field(ge=0)

    @field_validator('stateVersion', mode='before')
    @classmethod
    def _validate_state_version(cls, value: object) -> int:
        try:
            normalized = int(value if value is not None else LEGACY_SESSION_STATE_VERSION)
        except (TypeError, ValueError) as exc:
            raise ValueError('stateVersion must be an integer') from exc
        if normalized not in SUPPORTED_SESSION_STATE_VERSIONS:
            raise ValueError(
                f'stateVersion must be one of {sorted(SUPPORTED_SESSION_STATE_VERSIONS)}'
            )
        return normalized

    @field_validator('discipline', 'subcategory', mode='before')
    @classmethod
    def _validate_required_text(cls, value: object) -> str:
        normalized = str(value or '').strip()
        if not normalized:
            raise ValueError('field is required')
        return normalized

    @field_validator('savedAt', mode='before')
    @classmethod
    def _coerce_saved_at(cls, value: object) -> int:
        return _coerce_non_negative_int(value)


class InProgressSessionStateModel(SessionStateBaseModel):
    completed: Literal[False] = False
    currentIndex: int = Field(ge=0)
    questionIds: list[int] = Field(default_factory=list)
    selections: dict[str, int] = Field(default_factory=dict)
    lastSubmitted: dict[str, str] = Field(default_factory=dict)
    isCorrect: dict[str, bool | None] = Field(default_factory=dict)
    correctOptionIndexByQuestionId: dict[str, int] = Field(default_factory=dict)
    elapsedSeconds: int = Field(ge=0)
    paused: bool = False
    totalAvailable: int | None = Field(default=None, ge=0)
    offset: int = Field(default=0, ge=0)
    showingAnswerFeedback: bool = False
    feedbackQuestionId: int | None = Field(default=None, ge=0)
    currentCorrectOptionIndex: int | None = Field(default=None, ge=0)
    lastAnswerWasCorrect: bool | None = None
    questions: list[dict[str, Any]] | None = None

    @field_validator('currentIndex', 'elapsedSeconds', 'offset', mode='before')
    @classmethod
    def _coerce_index_and_elapsed(cls, value: object) -> int:
        return _coerce_non_negative_int(value)

    @field_validator('feedbackQuestionId', 'currentCorrectOptionIndex', mode='before')
    @classmethod
    def _coerce_optional_non_negative_int(cls, value: object) -> int | None:
        if value is None:
            return None
        return _coerce_non_negative_int(value)

    @field_validator('questionIds', mode='before')
    @classmethod
    def _normalize_question_ids(cls, value: object) -> list[int]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError('questionIds must be a list')

        normalized: list[int] = []
        seen: set[int] = set()
        for raw_item in value:
            question_id = _coerce_positive_int(raw_item, field_name='questionIds item')
            if question_id in seen:
                continue
            seen.add(question_id)
            normalized.append(question_id)
        return normalized

    @field_validator('selections', mode='before')
    @classmethod
    def _normalize_selections(cls, value: object) -> dict[str, int]:
        return _normalize_int_mapping(
            value,
            field_name='selections',
            value_name='selected option index',
            allow_empty=True,
        )

    @field_validator('lastSubmitted', mode='before')
    @classmethod
    def _normalize_last_submitted(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError('lastSubmitted must be an object')

        normalized: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = _normalize_question_id_key(raw_key, field_name='lastSubmitted')
            submitted = str(raw_value or '').strip().upper()
            if not submitted:
                raise ValueError(f'lastSubmitted[{key}] must be a non-empty string')
            normalized[key] = submitted
        return normalized

    @field_validator('isCorrect', mode='before')
    @classmethod
    def _normalize_is_correct(cls, value: object) -> dict[str, bool | None]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError('isCorrect must be an object')

        normalized: dict[str, bool | None] = {}
        for raw_key, raw_value in value.items():
            key = _normalize_question_id_key(raw_key, field_name='isCorrect')
            if raw_value is None or raw_value == 'null':
                normalized[key] = None
                continue
            if isinstance(raw_value, bool):
                normalized[key] = raw_value
                continue
            if isinstance(raw_value, str):
                lowered = raw_value.strip().lower()
                if lowered == 'true':
                    normalized[key] = True
                    continue
                if lowered == 'false':
                    normalized[key] = False
                    continue
            raise ValueError(f'isCorrect[{key}] must be true, false or null')
        return normalized

    @field_validator('correctOptionIndexByQuestionId', mode='before')
    @classmethod
    def _normalize_correct_option_indexes(cls, value: object) -> dict[str, int]:
        return _normalize_int_mapping(
            value,
            field_name='correctOptionIndexByQuestionId',
            value_name='correct option index',
            allow_empty=True,
        )


class CompletedSessionStateModel(SessionStateBaseModel):
    completed: Literal[True]
    result: SessionCompletionResultModel


def parse_session_state(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str):
        return {}

    try:
        decoded = json.loads(value or '{}')
    except json.JSONDecodeError:
        return {}

    if not isinstance(decoded, dict):
        return {}
    return decoded


def normalize_session_state_for_storage(raw_state: object) -> dict[str, Any]:
    if not isinstance(raw_state, dict):
        raise SessionStateValidationError('state must be a JSON object')

    model_cls: type[SessionStateBaseModel]
    model_cls = (
        CompletedSessionStateModel
        if raw_state.get('completed') is True
        else InProgressSessionStateModel
    )

    try:
        validated = model_cls.model_validate(raw_state)
    except ValidationError as exc:
        raise SessionStateValidationError(_format_validation_error(exc)) from exc

    return validated.model_dump()


def derive_session_snapshot_columns(state: dict[str, Any]) -> dict[str, Any]:
    completed = state.get('completed') is True
    result = state.get('result') if isinstance(state.get('result'), dict) else {}
    last_submitted = state.get('lastSubmitted')
    question_ids = state.get('questionIds')

    answered_questions = (
        _safe_non_negative_int(result.get('answeredQuestions'))
        if completed
        else len(last_submitted) if isinstance(last_submitted, dict) else 0
    )
    in_progress_total = _safe_non_negative_int(state.get('totalAvailable'))
    if not in_progress_total and isinstance(question_ids, list):
        in_progress_total = len(question_ids)
    total_questions = (
        _safe_non_negative_int(result.get('totalQuestions'))
        if completed
        else in_progress_total
    )
    elapsed_seconds = (
        _safe_non_negative_int(result.get('elapsedSeconds'))
        if completed
        else _safe_non_negative_int(state.get('elapsedSeconds'))
    )

    return {
        'state_version': _resolve_state_version(state.get('stateVersion')),
        'completed': completed,
        'answered_questions': answered_questions,
        'total_questions': total_questions,
        'elapsed_seconds': elapsed_seconds,
        'saved_at': _saved_at_to_datetime(state.get('savedAt')),
    }


def _resolve_state_version(raw_value: object) -> int:
    try:
        normalized = int(raw_value or LEGACY_SESSION_STATE_VERSION)
    except (TypeError, ValueError):
        return LEGACY_SESSION_STATE_VERSION
    if normalized in SUPPORTED_SESSION_STATE_VERSIONS:
        return normalized
    return LEGACY_SESSION_STATE_VERSION


def _coerce_non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        raise ValueError('value must be an integer')


def _safe_non_negative_int(value: object) -> int:
    try:
        return _coerce_non_negative_int(value)
    except ValueError:
        return 0


def _coerce_positive_int(value: object, *, field_name: str) -> int:
    try:
        normalized = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{field_name} must be an integer') from exc
    if normalized <= 0:
        raise ValueError(f'{field_name} must be greater than zero')
    return normalized


def _normalize_question_id_key(raw_key: object, *, field_name: str) -> str:
    normalized = str(raw_key or '').strip()
    if not normalized:
        raise ValueError(f'{field_name} contains an empty key')
    question_id = _coerce_positive_int(normalized, field_name=f'{field_name} key')
    return str(question_id)


def _normalize_int_mapping(
    value: object,
    *,
    field_name: str,
    value_name: str,
    allow_empty: bool,
) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f'{field_name} must be an object')

    normalized: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        key = _normalize_question_id_key(raw_key, field_name=field_name)
        normalized_value = _coerce_non_negative_int(raw_value)
        if not allow_empty and normalized_value <= 0:
            raise ValueError(f'{field_name}[{key}] {value_name} must be positive')
        normalized[key] = normalized_value
    return normalized


def _saved_at_to_datetime(raw_value: object) -> datetime | None:
    try:
        milliseconds = int(raw_value)
    except (TypeError, ValueError):
        return None
    if milliseconds <= 0:
        return None

    try:
        return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _format_validation_error(exc: ValidationError) -> str:
    first_error = exc.errors()[0] if exc.errors() else None
    if first_error is None:
        return 'state payload is invalid'

    location = '.'.join(str(part) for part in first_error.get('loc', ()))
    message = first_error.get('msg', 'invalid value')
    if location:
        return f'state.{location}: {message}'
    return f'state: {message}'
