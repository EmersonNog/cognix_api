from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .serializers import serialize_submission_summary, serialize_version
from .tables import writing_submission_versions_table, writing_submissions_table


def count_writing_submissions(db: Session, *, user_id: int) -> int:
    submissions = writing_submissions_table()
    return int(
        db.execute(
            select(func.count()).select_from(submissions).where(
                submissions.c.user_id == user_id,
            )
        ).scalar_one()
        or 0
    )



def list_writing_submissions(
    db: Session,
    *,
    user_id: int,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    submissions = writing_submissions_table()
    rows = db.execute(
        select(submissions)
        .where(submissions.c.user_id == user_id)
        .order_by(
            submissions.c.last_analyzed_at.desc(),
            submissions.c.updated_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).mappings().all()
    return [serialize_submission_summary(row) for row in rows]



def get_writing_submission_detail(
    db: Session,
    *,
    user_id: int,
    submission_id: int,
    versions_limit: int = 5,
    versions_offset: int = 0,
) -> dict:
    submissions = writing_submissions_table()
    versions = writing_submission_versions_table()
    submission = db.execute(
        select(submissions).where(
            submissions.c.id == submission_id,
            submissions.c.user_id == user_id,
        )
    ).mappings().first()
    if not submission:
        raise HTTPException(status_code=404, detail='Writing submission not found')

    versions_total = int(
        db.execute(
            select(func.count()).select_from(versions).where(
                versions.c.submission_id == submission_id,
            )
        ).scalar_one()
        or 0
    )
    version_rows = db.execute(
        select(versions)
        .where(versions.c.submission_id == submission_id)
        .order_by(versions.c.version_number.desc())
        .limit(versions_limit)
        .offset(versions_offset)
    ).mappings().all()
    return {
        **serialize_submission_summary(submission),
        'versions': [serialize_version(row) for row in version_rows],
        'versions_total': versions_total,
        'versions_limit': versions_limit,
        'versions_offset': versions_offset,
        'versions_has_more': versions_offset + versions_limit < versions_total,
    }
