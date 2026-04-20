from app.core.config import settings
from app.db.models import (
    get_writing_submission_versions_table,
    get_writing_submissions_table,
)


def writing_submissions_table():
    return get_writing_submissions_table(settings.writing_submissions_table)


def writing_submission_versions_table():
    return get_writing_submission_versions_table(
        settings.writing_submission_versions_table,
    )
