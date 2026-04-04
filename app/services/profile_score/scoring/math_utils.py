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
