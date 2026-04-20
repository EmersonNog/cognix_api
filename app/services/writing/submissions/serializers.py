import json

from app.core.datetime_utils import to_api_iso


def serialize_submission_summary(row: dict) -> dict:
    return {
        'id': int(row['id']),
        'theme': {
            'id': row.get('theme_slug') or '',
            'title': row.get('theme_title') or '',
            'category': row.get('theme_category') or '',
        },
        'status': row.get('status') or 'active',
        'current_version': int(row.get('current_version') or 0),
        'latest_score': row.get('latest_score'),
        'latest_summary': row.get('latest_summary') or '',
        'last_analyzed_at': serialize_datetime(row.get('last_analyzed_at')),
        'created_at': serialize_datetime(row.get('created_at')),
        'updated_at': serialize_datetime(row.get('updated_at')),
    }



def serialize_version(row: dict) -> dict:
    return {
        'id': int(row['id']),
        'version_number': int(row.get('version_number') or 0),
        'thesis': row.get('thesis') or '',
        'repertoire': row.get('repertoire') or '',
        'argument_one': row.get('argument_one') or '',
        'argument_two': row.get('argument_two') or '',
        'intervention': row.get('intervention') or '',
        'final_text': row.get('final_text') or '',
        'estimated_score': int(row.get('estimated_score') or 0),
        'summary': row.get('summary') or '',
        'checklist': load_json_list(row.get('checklist_json')),
        'competencies': load_json_list(row.get('competencies_json')),
        'rewrite_suggestions': load_json_list(row.get('rewrite_suggestions_json')),
        'analyzed_at': serialize_datetime(row.get('analyzed_at')),
        'created_at': serialize_datetime(row.get('created_at')),
    }



def load_json_list(raw: object) -> list:
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return decoded if isinstance(decoded, list) else []



def serialize_datetime(value: object) -> str | None:
    if value is None:
        return None
    serialized = to_api_iso(value)
    if serialized:
        return serialized
    iso = getattr(value, 'isoformat', None)
    if callable(iso):
        return iso()
    return str(value)



def theme_value(theme: dict, key: str) -> str:
    return str(theme.get(key) or '').strip()
