from app.services.profile_score.constants import (
    ACCURACY_CEILING,
    ACCURACY_FLOOR,
    ACCURACY_POINTS_MAX,
    COMPLETED_SESSION_POINTS,
    COMPLETED_SESSION_POINTS_MAX,
    CONSISTENCY_DAYS_WINDOW,
    CONSISTENCY_POINTS_MAX,
    CONSISTENCY_POINTS_PER_DAY,
    LEVEL_THRESHOLDS,
    QUESTION_GOAL,
    QUESTION_POINTS_MAX,
)


def round_points(value: float) -> float:
    return round(float(value), 1)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


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


def calculate_score_components(
    total_questions: int,
    accuracy_percent: float,
    completed_sessions: int,
    active_days_last_30: int,
) -> dict:
    questions_score = round_points(
        min(total_questions / QUESTION_GOAL, 1.0) * QUESTION_POINTS_MAX
    )
    accuracy_progress = clamp(
        (accuracy_percent - ACCURACY_FLOOR)
        / (ACCURACY_CEILING - ACCURACY_FLOOR),
        0.0,
        1.0,
    )
    accuracy_score = round_points(accuracy_progress * ACCURACY_POINTS_MAX)
    completed_sessions_score = round_points(
        min(completed_sessions * COMPLETED_SESSION_POINTS, COMPLETED_SESSION_POINTS_MAX)
    )
    consistency_score = round_points(
        min(active_days_last_30 * CONSISTENCY_POINTS_PER_DAY, CONSISTENCY_POINTS_MAX)
    )
    exact_score = round_points(
        min(
            questions_score
            + accuracy_score
            + completed_sessions_score
            + consistency_score,
            100.0,
        )
    )

    return {
        'score': int(round(exact_score)),
        'exact_score': exact_score,
        'level': derive_level(exact_score),
        'next_level': next_level(exact_score),
        'score_breakdown': {
            'questions': {
                'points': questions_score,
                'max_points': QUESTION_POINTS_MAX,
                'raw': total_questions,
                'goal': QUESTION_GOAL,
            },
            'accuracy': {
                'points': accuracy_score,
                'max_points': ACCURACY_POINTS_MAX,
                'raw': accuracy_percent,
                'floor': ACCURACY_FLOOR,
                'ceiling': ACCURACY_CEILING,
            },
            'completed_sessions': {
                'points': completed_sessions_score,
                'max_points': COMPLETED_SESSION_POINTS_MAX,
                'raw': completed_sessions,
                'points_per_session': COMPLETED_SESSION_POINTS,
            },
            'consistency': {
                'points': consistency_score,
                'max_points': CONSISTENCY_POINTS_MAX,
                'raw': active_days_last_30,
                'window_days': CONSISTENCY_DAYS_WINDOW,
                'points_per_day': CONSISTENCY_POINTS_PER_DAY,
            },
        },
    }
