def build_writing_feedback_schema() -> dict:
    checklist_item = {
        'type': 'object',
        'properties': {
            'label': {'type': 'string'},
            'completed': {'type': 'boolean'},
            'helper': {'type': 'string'},
        },
        'required': ['label', 'completed', 'helper'],
        'additionalProperties': False,
    }
    competency = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'score': {'type': 'integer'},
            'comment': {'type': 'string'},
        },
        'required': ['title', 'score', 'comment'],
        'additionalProperties': False,
    }
    rewrite_suggestion = {
        'type': 'object',
        'properties': {
            'section': {'type': 'string'},
            'issue': {'type': 'string'},
            'suggestion': {'type': 'string'},
            'example': {'type': 'string'},
        },
        'required': ['section', 'issue', 'suggestion', 'example'],
        'additionalProperties': False,
    }

    return {
        'type': 'object',
        'properties': {
            'estimated_score': {'type': 'integer'},
            'summary': {'type': 'string'},
            'checklist': {'type': 'array', 'items': checklist_item},
            'competencies': {'type': 'array', 'items': competency},
            'rewrite_suggestions': {'type': 'array', 'items': rewrite_suggestion},
        },
        'required': [
            'estimated_score',
            'summary',
            'checklist',
            'competencies',
            'rewrite_suggestions',
        ],
        'additionalProperties': False,
    }
