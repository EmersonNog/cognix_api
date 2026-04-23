from app.core.datetime_utils import to_api_iso


def serialize_flashcard(row: dict) -> dict:
    return {
        'id': int(row['id']),
        'subject': row.get('subject') or '',
        'front_text': row.get('front_text') or '',
        'front_image_base64': row.get('front_image_base64') or '',
        'back_text': row.get('back_text') or '',
        'back_image_base64': row.get('back_image_base64') or '',
        'created_at': serialize_datetime(row.get('created_at')),
        'updated_at': serialize_datetime(row.get('updated_at')),
    }


def serialize_flashcard_deck_state(row: dict) -> dict:
    return {
        'subject': row.get('subject') or '',
        'current_index': int(row.get('current_index') or 0),
        'correct_count': int(row.get('correct_count') or 0),
        'wrong_count': int(row.get('wrong_count') or 0),
        'updated_at': serialize_datetime(row.get('updated_at')),
    }


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
