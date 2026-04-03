from app.services.profile_score.constants import (
    LEVEL_THRESHOLDS,
    MOMENTUM_ACCURACY_CEILING,
    MOMENTUM_ACCURACY_FLOOR,
    MOMENTUM_ACCURACY_POINTS_ABS,
    MOMENTUM_ACCURACY_SAMPLE_SIZE,
    MOMENTUM_ACTIVE_DAYS_GOAL,
    MOMENTUM_ACTIVE_DAYS_POINTS_ABS,
    MOMENTUM_ATTEMPTS_GOAL,
    MOMENTUM_ATTEMPTS_POINTS_ABS,
    MOMENTUM_SESSION_DELTA_FOR_MAX,
    MOMENTUM_SESSION_DELTA_NEUTRAL,
    MOMENTUM_SESSION_POINTS_ABS,
    MOMENTUM_INACTIVITY_PENALTY_MAX,
    MOMENTUM_INACTIVITY_PENALTY_PER_DAY,
    MOMENTUM_SIMULATION_GOAL,
    MOMENTUM_SIMULATION_POINTS_MAX,
    MOMENTUM_STREAK_CAP,
    MOMENTUM_STREAK_POINTS_MAX,
    PROGRESS_ACCURACY_CEILING,
    PROGRESS_ACCURACY_FLOOR,
    PROGRESS_ACCURACY_POINTS_MAX,
    PROGRESS_ACCURACY_SAMPLE_SIZE,
    PROGRESS_DISCIPLINE_GOAL,
    INACTIVITY_GRACE_DAYS,
    SCORE_INACTIVITY_PENALTY_MAX,
    SCORE_INACTIVITY_PENALTY_PER_DAY,
    PROGRESS_DISCIPLINE_POINTS_MAX,
    PROGRESS_QUESTION_COVERAGE_POINTS_MAX,
    PROGRESS_SESSION_GOAL,
    PROGRESS_SESSION_POINTS_MAX,
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



def balanced_habit_points(raw_value: float, goal_value: float, max_abs_points: float) -> float:
    if goal_value <= 0:
        return 0.0
    progress = clamp(raw_value / goal_value, 0.0, 1.0)
    return round_points(((progress * 2.0) - 1.0) * max_abs_points)



def balanced_accuracy_points(
    accuracy_percent: float,
    sample_size: int,
    floor: float,
    ceiling: float,
    max_abs_points: float,
    sample_goal: int,
) -> float:
    if sample_size <= 0 or sample_goal <= 0:
        return 0.0

    centered_progress = (normalized_progress(accuracy_percent, floor, ceiling) * 2.0) - 1.0
    confidence = min(sample_size / sample_goal, 1.0)
    return round_points(centered_progress * max_abs_points * confidence)



def session_delta_points(delta_percent: float) -> float:
    if MOMENTUM_SESSION_DELTA_FOR_MAX <= MOMENTUM_SESSION_DELTA_NEUTRAL:
        return 0.0

    absolute_delta = abs(delta_percent)
    if absolute_delta <= MOMENTUM_SESSION_DELTA_NEUTRAL:
        return 0.0

    scaled = min(
        (absolute_delta - MOMENTUM_SESSION_DELTA_NEUTRAL)
        / (MOMENTUM_SESSION_DELTA_FOR_MAX - MOMENTUM_SESSION_DELTA_NEUTRAL),
        1.0,
    )
    direction = 1.0 if delta_percent > 0 else -1.0
    return round_points(direction * scaled * MOMENTUM_SESSION_POINTS_ABS)



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



def derive_momentum_label(momentum_score: float) -> str:
    if momentum_score >= 6.0:
        return 'Em alta'
    if momentum_score >= 2.0:
        return 'Positivo'
    if momentum_score <= -6.0:
        return 'Em queda'
    if momentum_score <= -2.0:
        return 'Atencao'
    return 'Estavel'



def calculate_score_components(
    unique_questions_answered: int,
    question_bank_total: int,
    disciplines_covered: int,
    total_completed_sessions: int,
    historical_accuracy_percent: float,
    recent_attempts: int,
    recent_accuracy_percent: float,
    recent_accuracy_sample_size: int,
    recent_completed_sessions: int,
    recent_active_days: int,
    current_correct_streak: int,
    session_accuracy_delta_percent: float,
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

    momentum_attempts_score = balanced_habit_points(
        recent_attempts,
        MOMENTUM_ATTEMPTS_GOAL,
        MOMENTUM_ATTEMPTS_POINTS_ABS,
    )
    momentum_consistency_score = balanced_habit_points(
        recent_active_days,
        MOMENTUM_ACTIVE_DAYS_GOAL,
        MOMENTUM_ACTIVE_DAYS_POINTS_ABS,
    )
    momentum_accuracy_score = balanced_accuracy_points(
        recent_accuracy_percent,
        recent_accuracy_sample_size,
        MOMENTUM_ACCURACY_FLOOR,
        MOMENTUM_ACCURACY_CEILING,
        MOMENTUM_ACCURACY_POINTS_ABS,
        MOMENTUM_ACCURACY_SAMPLE_SIZE,
    )
    momentum_simulations_score = ratio_points(
        recent_completed_sessions,
        MOMENTUM_SIMULATION_GOAL,
        MOMENTUM_SIMULATION_POINTS_MAX,
    )
    momentum_streak_score = ratio_points(
        min(current_correct_streak, MOMENTUM_STREAK_CAP),
        MOMENTUM_STREAK_CAP,
        MOMENTUM_STREAK_POINTS_MAX,
    )
    momentum_session_score = session_delta_points(session_accuracy_delta_percent)

    raw_momentum_score = round_points(
        clamp(
            momentum_attempts_score
            + momentum_consistency_score
            + momentum_accuracy_score
            + momentum_simulations_score
            + momentum_streak_score
            + momentum_session_score,
            -10.0,
            10.0,
        )
    )

    momentum_ready = total_completed_sessions > 0
    momentum_inactivity_penalty = round_points(
        min(
            penalized_inactivity_days * MOMENTUM_INACTIVITY_PENALTY_PER_DAY,
            MOMENTUM_INACTIVITY_PENALTY_MAX,
        )
    )
    exact_momentum_score = (
        round_points(clamp(raw_momentum_score - momentum_inactivity_penalty, -10.0, 10.0))
        if momentum_ready
        else 0.0
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
        'momentum_score': int(round(exact_momentum_score)),
        'exact_momentum_score': exact_momentum_score,
        'momentum_label': derive_momentum_label(exact_momentum_score),
        'momentum_breakdown': {
            'attempts': {
                'points': momentum_attempts_score,
                'max_abs_points': MOMENTUM_ATTEMPTS_POINTS_ABS,
                'raw': recent_attempts,
                'goal': MOMENTUM_ATTEMPTS_GOAL,
            },
            'consistency': {
                'points': momentum_consistency_score,
                'max_abs_points': MOMENTUM_ACTIVE_DAYS_POINTS_ABS,
                'raw': recent_active_days,
                'goal': MOMENTUM_ACTIVE_DAYS_GOAL,
            },
            'accuracy': {
                'points': momentum_accuracy_score,
                'max_abs_points': MOMENTUM_ACCURACY_POINTS_ABS,
                'raw': recent_accuracy_percent,
                'sample_size': recent_accuracy_sample_size,
                'sample_goal': MOMENTUM_ACCURACY_SAMPLE_SIZE,
                'floor': MOMENTUM_ACCURACY_FLOOR,
                'ceiling': MOMENTUM_ACCURACY_CEILING,
            },
            'simulations': {
                'points': momentum_simulations_score,
                'max_points': MOMENTUM_SIMULATION_POINTS_MAX,
                'raw': recent_completed_sessions,
                'goal': MOMENTUM_SIMULATION_GOAL,
            },
            'streak': {
                'points': momentum_streak_score,
                'max_points': MOMENTUM_STREAK_POINTS_MAX,
                'raw': current_correct_streak,
                'cap': MOMENTUM_STREAK_CAP,
            },
            'latest_session_delta': {
                'points': momentum_session_score,
                'max_abs_points': MOMENTUM_SESSION_POINTS_ABS,
                'raw_delta': session_accuracy_delta_percent,
                'neutral_delta': MOMENTUM_SESSION_DELTA_NEUTRAL,
                'delta_for_max': MOMENTUM_SESSION_DELTA_FOR_MAX,
            },
            'activation': {
                'ready': momentum_ready,
                'completed_sessions': total_completed_sessions,
                'raw_score': raw_momentum_score,
            },
            'inactivity': {
                'days': inactivity_days,
                'grace_days': INACTIVITY_GRACE_DAYS,
                'penalized_days': penalized_inactivity_days,
                'penalty': momentum_inactivity_penalty,
                'max_penalty': MOMENTUM_INACTIVITY_PENALTY_MAX,
            },
        },
    }
