"""Compatibility facade for multiplayer persistence operations."""

from .data.answers import submit_answer
from .data.constants import (
    ANSWER_SCORE_POINTS,
    DEFAULT_MATCH_QUESTION_LIMIT,
    DEFAULT_ROUND_DURATION_SECONDS,
    PARTICIPANT_STATUS_JOINED,
    ROLE_HOST,
    ROLE_PLAYER,
    ROOM_CLOSED_REASON_HOST_LEFT,
    ROOM_CLOSED_REASON_HOST_OFFLINE,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_WAITING,
)
from .data.queries import (
    fetch_room_by_pin_row as _fetch_room_by_pin_row,
    fetch_room_row as _fetch_room_row,
    generate_pin as _generate_pin,
    joined_participants_count as _joined_participants_count,
    require_host as _require_host,
)
from .data.questions import (
    fetch_match_question_ids as _fetch_match_question_ids,
    fetch_question_answer_key as _fetch_question_answer_key,
    normalize_question_ids as _normalize_question_ids,
    resolve_is_correct as _resolve_is_correct,
)
from .data.rooms import (
    close_room_for_host_disconnect,
    create_room,
    delete_empty_room as _delete_empty_room,
    delete_room as _delete_room,
    get_room_by_id,
    get_room_by_pin,
    join_room,
    leave_room,
    remove_participant,
    start_room,
)
from .data.rounds import (
    advance_room_after_participant_exit as _advance_room_after_participant_exit,
    advance_room_if_round_expired as _advance_room_if_round_expired,
    advance_round as _advance_round,
)
from .data.serializers import (
    participant_sort_key as _participant_sort_key,
    serialize_closed_room as _serialize_closed_room,
    serialize_participant as _serialize_participant,
    serialize_room,
    serialize_room_snapshot as _serialize_room,
)
from .data.tables import (
    participants_table as _participants_table,
    questions_table as _questions_table,
    rooms_table as _rooms_table,
)

__all__ = [
    'ANSWER_SCORE_POINTS',
    'close_room_for_host_disconnect',
    'create_room',
    'DEFAULT_MATCH_QUESTION_LIMIT',
    'DEFAULT_ROUND_DURATION_SECONDS',
    'get_room_by_id',
    'get_room_by_pin',
    'join_room',
    'leave_room',
    'PARTICIPANT_STATUS_JOINED',
    'remove_participant',
    'ROLE_HOST',
    'ROLE_PLAYER',
    'ROOM_CLOSED_REASON_HOST_LEFT',
    'ROOM_CLOSED_REASON_HOST_OFFLINE',
    'ROOM_STATUS_FINISHED',
    'ROOM_STATUS_IN_PROGRESS',
    'ROOM_STATUS_WAITING',
    'serialize_room',
    'start_room',
    'submit_answer',
]
