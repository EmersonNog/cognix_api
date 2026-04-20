def normalize_writing_feedback(payload: dict) -> dict:
    return {
        'estimated_score': _clamp_int(payload.get('estimated_score'), 0, 1000),
        'summary': _string(payload.get('summary')),
        'checklist': [
            _normalize_checklist_item(item)
            for item in _list(payload.get('checklist'))
        ][:5],
        'competencies': [
            _normalize_competency(item)
            for item in _list(payload.get('competencies'))
        ][:5],
        'rewrite_suggestions': [
            _normalize_rewrite_suggestion(item)
            for item in _list(payload.get('rewrite_suggestions'))
        ][:5],
    }


def _normalize_checklist_item(item: object) -> dict:
    if not isinstance(item, dict):
        item = {}
    return {
        'label': _string(item.get('label')),
        'completed': bool(item.get('completed')),
        'helper': _string(item.get('helper')),
    }


def _normalize_competency(item: object) -> dict:
    if not isinstance(item, dict):
        item = {}
    return {
        'title': _string(item.get('title')),
        'score': _clamp_int(item.get('score'), 0, 200),
        'comment': _string(item.get('comment')),
    }


def _normalize_rewrite_suggestion(item: object) -> dict:
    if not isinstance(item, dict):
        item = {}
    return {
        'section': _string(item.get('section')),
        'issue': _string(item.get('issue')),
        'suggestion': _string(item.get('suggestion')),
        'example': _string(item.get('example')),
    }


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ''


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _clamp_int(value: object, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))
