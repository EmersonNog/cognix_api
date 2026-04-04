from ..constants import (
    INACTIVITY_GRACE_DAYS,
    PROGRESS_ACCURACY_CEILING,
    PROGRESS_ACCURACY_FLOOR,
    PROGRESS_ACCURACY_POINTS_MAX,
    PROGRESS_ACCURACY_SAMPLE_SIZE,
    PROGRESS_DISCIPLINE_GOAL,
    PROGRESS_DISCIPLINE_POINTS_MAX,
    PROGRESS_QUESTION_COVERAGE_POINTS_MAX,
    PROGRESS_SESSION_GOAL,
    PROGRESS_SESSION_POINTS_MAX,
    SCORE_INACTIVITY_PENALTY_MAX,
    SCORE_INACTIVITY_PENALTY_PER_DAY,
)
from .levels import derive_level, next_level
from .math_utils import (
    clamp,
    ratio_points,
    round_points,
    weighted_accuracy_points,
)
from .recent_index import calculate_recent_index_data


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
