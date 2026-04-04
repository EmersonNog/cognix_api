from ..constants import (
    RECENT_INDEX_ACTIVE_DAYS_GOAL,
    RECENT_INDEX_ATTEMPT_DECAY,
    RECENT_INDEX_ATTEMPTS_WEIGHT,
    RECENT_INDEX_CONSISTENCY_WEIGHT,
    RECENT_INDEX_SESSION_GOAL,
    RECENT_INDEX_SIMULATION_WEIGHT,
)
from .math_utils import clamp, round_points


def _weighted_recent_accuracy_signal(recent_attempt_outcomes: list[bool]) -> float | None:
    if not recent_attempt_outcomes:
        return None

    weighted_points = 0.0
    total_weight = 0.0
    for index, is_correct in enumerate(recent_attempt_outcomes):
        weight = RECENT_INDEX_ATTEMPT_DECAY ** index
        weighted_points += (100.0 if is_correct else 0.0) * weight
        total_weight += weight

    if total_weight <= 0:
        return None
    return round_points(weighted_points / total_weight)


def _recent_consistency_signal(recent_active_days: int) -> float:
    if RECENT_INDEX_ACTIVE_DAYS_GOAL <= 0:
        return 0.0

    return round_points(
        clamp(recent_active_days / RECENT_INDEX_ACTIVE_DAYS_GOAL, 0.0, 1.0) * 100.0
    )


def _recent_simulation_signal(
    latest_session_accuracy_percent: float,
    recent_completed_sessions: int,
) -> float:
    if RECENT_INDEX_SESSION_GOAL <= 0:
        return 50.0

    session_activity_ratio = clamp(
        recent_completed_sessions / RECENT_INDEX_SESSION_GOAL,
        0.0,
        1.0,
    )
    latest_accuracy = clamp(latest_session_accuracy_percent, 0.0, 100.0)
    return round_points(50.0 + ((latest_accuracy - 50.0) * session_activity_ratio))


def calculate_recent_index_data(
    recent_attempt_outcomes: list[bool],
    recent_active_days: int,
    recent_completed_sessions: int,
    latest_session_accuracy_percent: float,
) -> dict:
    accuracy_signal = _weighted_recent_accuracy_signal(recent_attempt_outcomes)
    consistency_signal = _recent_consistency_signal(recent_active_days)
    simulation_signal = _recent_simulation_signal(
        latest_session_accuracy_percent,
        recent_completed_sessions,
    )
    ready = (
        bool(recent_attempt_outcomes)
        or recent_active_days > 0
        or recent_completed_sessions > 0
    )

    if not ready:
        return {
            'recent_index': 0,
            'exact_recent_index': 0.0,
            'recent_index_ready': False,
            'recent_index_breakdown': {
                'accuracy_signal': 0.0,
                'consistency_signal': 0.0,
                'simulation_signal': 0.0,
                'attempt_sample_size': 0,
                'weights': {
                    'accuracy': RECENT_INDEX_ATTEMPTS_WEIGHT,
                    'consistency': RECENT_INDEX_CONSISTENCY_WEIGHT,
                    'simulation': RECENT_INDEX_SIMULATION_WEIGHT,
                },
            },
        }

    exact_recent_index = round_points(
        clamp(
            (accuracy_signal if accuracy_signal is not None else 50.0)
            * RECENT_INDEX_ATTEMPTS_WEIGHT
            + consistency_signal * RECENT_INDEX_CONSISTENCY_WEIGHT
            + simulation_signal * RECENT_INDEX_SIMULATION_WEIGHT,
            0.0,
            100.0,
        )
    )

    return {
        'recent_index': int(round(exact_recent_index)),
        'exact_recent_index': exact_recent_index,
        'recent_index_ready': True,
        'recent_index_breakdown': {
            'accuracy_signal': accuracy_signal if accuracy_signal is not None else 50.0,
            'consistency_signal': consistency_signal,
            'simulation_signal': simulation_signal,
            'attempt_sample_size': len(recent_attempt_outcomes),
            'weights': {
                'accuracy': RECENT_INDEX_ATTEMPTS_WEIGHT,
                'consistency': RECENT_INDEX_CONSISTENCY_WEIGHT,
                'simulation': RECENT_INDEX_SIMULATION_WEIGHT,
            },
        },
    }
