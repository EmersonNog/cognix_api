import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from .serializers import theme_value
from .tables import writing_submission_versions_table, writing_submissions_table


def store_writing_analysis(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    payload: dict,
    feedback: dict,
    submission_id: int | None = None,
) -> dict:
    submissions = writing_submissions_table()
    versions = writing_submission_versions_table()
    theme = dict(payload.get('theme') or {})
    now = utc_now()

    submission = _resolve_submission(
        db,
        submissions=submissions,
        user_id=user_id,
        firebase_uid=firebase_uid,
        theme=theme,
        submission_id=submission_id,
        now=now,
    )

    version_number = int(submission.get('current_version') or 0) + 1
    version_insert = _build_version_insert(
        submission_id=submission['id'],
        version_number=version_number,
        payload=payload,
        feedback=feedback,
        now=now,
    )
    version_result = db.execute(versions.insert(), version_insert)
    version_id = int(version_result.inserted_primary_key[0])

    db.execute(
        submissions.update()
        .where(submissions.c.id == submission['id'])
        .values(
            theme_slug=theme_value(theme, 'id'),
            theme_title=theme_value(theme, 'title'),
            theme_category=theme_value(theme, 'category'),
            current_version=version_number,
            latest_version_id=version_id,
            latest_score=version_insert['estimated_score'],
            latest_summary=version_insert['summary'],
            last_analyzed_at=now,
            updated_at=now,
        )
    )

    return {
        **feedback,
        'submission_id': submission['id'],
        'version_id': version_id,
        'version_number': version_number,
    }



def _resolve_submission(
    db: Session,
    *,
    submissions,
    user_id: int,
    firebase_uid: str | None,
    theme: dict,
    submission_id: int | None,
    now,
) -> dict:
    if submission_id is not None:
        existing = db.execute(
            select(submissions).where(
                submissions.c.id == submission_id,
                submissions.c.user_id == user_id,
            )
        ).mappings().first()
        if not existing:
            raise HTTPException(status_code=404, detail='Writing submission not found')
        return dict(existing)

    theme_slug = theme_value(theme, 'id')
    if theme_slug:
        existing = db.execute(
            select(submissions)
            .where(
                submissions.c.user_id == user_id,
                submissions.c.theme_slug == theme_slug,
                submissions.c.status == 'active',
            )
            .order_by(
                submissions.c.last_analyzed_at.desc(),
                submissions.c.updated_at.desc(),
            )
        ).mappings().first()
        if existing:
            return dict(existing)

    insert_payload = {
        'user_id': user_id,
        'firebase_uid': str(firebase_uid or ''),
        'theme_slug': theme_slug,
        'theme_title': theme_value(theme, 'title'),
        'theme_category': theme_value(theme, 'category'),
        'status': 'active',
        'current_version': 0,
        'last_analyzed_at': now,
        'created_at': now,
        'updated_at': now,
    }
    submission_result = db.execute(submissions.insert(), insert_payload)
    submission_pk = int(submission_result.inserted_primary_key[0])
    row = db.execute(
        select(submissions).where(submissions.c.id == submission_pk)
    ).mappings().one()
    return dict(row)



def _build_version_insert(
    *,
    submission_id: int,
    version_number: int,
    payload: dict,
    feedback: dict,
    now,
) -> dict:
    return {
        'submission_id': submission_id,
        'version_number': version_number,
        'thesis': str(payload.get('thesis') or '').strip(),
        'repertoire': str(payload.get('repertoire') or '').strip(),
        'argument_one': str(payload.get('argument_one') or '').strip(),
        'argument_two': str(payload.get('argument_two') or '').strip(),
        'intervention': str(payload.get('intervention') or '').strip(),
        'final_text': str(payload.get('final_text') or '').strip(),
        'estimated_score': int(feedback.get('estimated_score') or 0),
        'summary': str(feedback.get('summary') or '').strip(),
        'checklist_json': json.dumps(feedback.get('checklist') or []),
        'competencies_json': json.dumps(feedback.get('competencies') or []),
        'rewrite_suggestions_json': json.dumps(
            feedback.get('rewrite_suggestions') or [],
        ),
        'analyzed_at': now,
        'created_at': now,
        'updated_at': now,
    }
