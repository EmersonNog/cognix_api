from fastapi import HTTPException

QUESTION_REPORT_REASONS = {
    'missing_statement',
    'missing_image',
    'broken_image',
    'alternatives_issue',
    'wrong_answer',
    'other',
}


def normalize_question_report_reason(value: object) -> str:
    reason = str(value or '').strip()
    if not reason:
        raise HTTPException(status_code=400, detail='reason is required')
    if reason not in QUESTION_REPORT_REASONS:
        raise HTTPException(status_code=400, detail='Invalid report reason')
    return reason


def normalize_question_report_reasons(payload: dict) -> list[str]:
    raw_reasons = payload.get('reasons')
    if raw_reasons is None:
        raw_reason = payload.get('reason')
        if raw_reason is None:
            raw_reasons = []
        elif isinstance(raw_reason, str) and ',' in raw_reason:
            raw_reasons = raw_reason.split(',')
        else:
            raw_reasons = [raw_reason]

    if not isinstance(raw_reasons, list):
        raise HTTPException(status_code=400, detail='reasons must be a list')

    reasons: list[str] = []
    for raw_reason in raw_reasons:
        reason = normalize_question_report_reason(raw_reason)
        if reason not in reasons:
            reasons.append(reason)

    if not reasons:
        raise HTTPException(status_code=400, detail='reason is required')
    if 'other' in reasons and len(reasons) > 1:
        raise HTTPException(
            status_code=400,
            detail='other reason cannot be combined with other reasons',
        )
    return reasons


def normalize_optional_report_text(
    field_name: str,
    value: object,
    *,
    max_length: int,
) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f'{field_name} must have at most {max_length} chars',
        )
    return normalized


def parse_question_report_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Invalid report payload')

    reasons = normalize_question_report_reasons(payload)
    details = normalize_optional_report_text(
        'details',
        payload.get('details'),
        max_length=1000,
    )
    if reasons == ['other'] and details is None:
        raise HTTPException(
            status_code=400,
            detail='details is required for other reason',
        )

    return {
        'reason': ','.join(reasons),
        'reasons': reasons,
        'details': details,
        'discipline': normalize_optional_report_text(
            'discipline',
            payload.get('discipline'),
            max_length=255,
        ),
        'subcategory': normalize_optional_report_text(
            'subcategory',
            payload.get('subcategory'),
            max_length=255,
        ),
    }
