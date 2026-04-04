from ..constants import LEVEL_THRESHOLDS


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
