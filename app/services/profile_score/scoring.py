from app.services.profile_score.constants import (
    INACTIVITY_GRACE_DAYS,
    LEVEL_THRESHOLDS,
    PROGRESS_ACCURACY_CEILING,
    PROGRESS_ACCURACY_FLOOR,
    PROGRESS_ACCURACY_POINTS_MAX,
    PROGRESS_ACCURACY_SAMPLE_SIZE,
    PROGRESS_DISCIPLINE_GOAL,
    PROGRESS_DISCIPLINE_POINTS_MAX,
    PROGRESS_QUESTION_COVERAGE_POINTS_MAX,
    PROGRESS_SESSION_GOAL,
    PROGRESS_SESSION_POINTS_MAX,
    RECENT_INDEX_ACTIVE_DAYS_GOAL,
    RECENT_INDEX_ATTEMPT_DECAY,
    RECENT_INDEX_ATTEMPTS_WEIGHT,
    RECENT_INDEX_CONSISTENCY_WEIGHT,
    RECENT_INDEX_SESSION_GOAL,
    RECENT_INDEX_SIMULATION_WEIGHT,
    SCORE_INACTIVITY_PENALTY_MAX,
    SCORE_INACTIVITY_PENALTY_PER_DAY,
)


def round_points(value: float) -> float:
    return round(float(value), 1)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def ratio_points(raw_value: float, goal_value: float, max_points: float) -> float:
    if goal_value <= 0:
        return 0.0
    return round_points(min(raw_value / goal_value, 1.0) * max_points)


def normalized_progress(accuracy_percent: float, floor: float, ceiling: float) -> float:
    if ceiling <= floor:
        return 0.0
    return clamp((accuracy_percent - floor) / (ceiling - floor), 0.0, 1.0)


def weighted_accuracy_points(
    accuracy_percent: float,
    sample_size: int,
    floor: float,
    ceiling: float,
    max_points: float,
    sample_goal: int,
) -> float:
    if sample_size <= 0 or sample_goal <= 0:
        return 0.0

    confidence = min(sample_size / sample_goal, 1.0)
    return round_points(
        normalized_progress(accuracy_percent, floor, ceiling) * max_points * confidence
    )


def derive_level(score: float) -> str:
    for minimum_score, label in LEVEL_THRESHOLDS:
        if score >= minimum_score:
            return label
    return 'Iniciante'


def next_level(score: float) -> tuple[str | None, int]:
    ascending = sorted(LEVEL_THRESHOLDS, key=lambda item: item[0])
    for minimum_score, label in ascending:
        if score < minimum_score:
            remaining = max(0, int(round(minimum_score - score)))
            return label, remaining
    return None, 0


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


def calculate_score_components(
    unique_questions_answered: int,
    question_bank_total: int,
    disciplines_covered: int,
    total_completed_sessions: int,
    historical_accuracy_percent: float,
    recent_completed_sessions: int,
    recent_active_days: int,
    recent_attempt_outcomes: list[bool],
    latest_session_accuracy_percent: float,
    inactivity_days: int,
) -> dict:
    progress_question_coverage_score = ratio_points(
        unique_questions_answered,
        question_bank_total,
        PROGRESS_QUESTION_COVERAGE_POINTS_MAX,
    )
    progress_discipline_score = ratio_points(
        disciplines_covered,
        PROGRESS_DISCIPLINE_GOAL,
        PROGRESS_DISCIPLINE_POINTS_MAX,
    )
    progress_session_score = ratio_points(
        total_completed_sessions,
        PROGRESS_SESSION_GOAL,
        PROGRESS_SESSION_POINTS_MAX,
    )
    progress_accuracy_score = weighted_accuracy_points(
        historical_accuracy_percent,
        unique_questions_answered,
        PROGRESS_ACCURACY_FLOOR,
        PROGRESS_ACCURACY_CEILING,
        PROGRESS_ACCURACY_POINTS_MAX,
        PROGRESS_ACCURACY_SAMPLE_SIZE,
    )

    base_exact_score = round_points(
        clamp(
            progress_question_coverage_score
            + progress_discipline_score
            + progress_session_score
            + progress_accuracy_score,
            0.0,
            100.0,
        )
    )
    penalized_inactivity_days = max(inactivity_days - INACTIVITY_GRACE_DAYS, 0)
    score_inactivity_penalty = round_points(
        min(
            penalized_inactivity_days * SCORE_INACTIVITY_PENALTY_PER_DAY,
            SCORE_INACTIVITY_PENALTY_MAX,
        )
    )
    exact_score = round_points(
        clamp(base_exact_score - score_inactivity_penalty, 0.0, 100.0)
    )

    recent_index_data = calculate_recent_index_data(
        recent_attempt_outcomes=recent_attempt_outcomes,
        recent_active_days=recent_active_days,
        recent_completed_sessions=recent_completed_sessions,
        latest_session_accuracy_percent=latest_session_accuracy_percent,
    )

    return {
        'score': int(round(exact_score)),
        'exact_score': exact_score,
        'level': derive_level(exact_score),
        'next_level': next_level(exact_score),
        'score_breakdown': {
            'question_coverage': {
                'points': progress_question_coverage_score,
                'max_points': PROGRESS_QUESTION_COVERAGE_POINTS_MAX,
                'raw': unique_questions_answered,
                'goal': question_bank_total,
            },
            'discipline_coverage': {
                'points': progress_discipline_score,
                'max_points': PROGRESS_DISCIPLINE_POINTS_MAX,
                'raw': disciplines_covered,
                'goal': PROGRESS_DISCIPLINE_GOAL,
            },
            'completed_sessions': {
                'points': progress_session_score,
                'max_points': PROGRESS_SESSION_POINTS_MAX,
                'raw': total_completed_sessions,
                'goal': PROGRESS_SESSION_GOAL,
            },
            'historical_accuracy': {
                'points': progress_accuracy_score,
                'max_points': PROGRESS_ACCURACY_POINTS_MAX,
                'raw': historical_accuracy_percent,
                'sample_size': unique_questions_answered,
                'sample_goal': PROGRESS_ACCURACY_SAMPLE_SIZE,
                'floor': PROGRESS_ACCURACY_FLOOR,
                'ceiling': PROGRESS_ACCURACY_CEILING,
            },
            'inactivity': {
                'days': inactivity_days,
                'grace_days': INACTIVITY_GRACE_DAYS,
                'penalized_days': penalized_inactivity_days,
                'penalty': score_inactivity_penalty,
                'max_penalty': SCORE_INACTIVITY_PENALTY_MAX,
                'base_score': base_exact_score,
            },
        },
        'recent_index': recent_index_data['recent_index'],
        'exact_recent_index': recent_index_data['exact_recent_index'],
        'recent_index_ready': recent_index_data['recent_index_ready'],
        'recent_index_breakdown': recent_index_data['recent_index_breakdown'],
    }
