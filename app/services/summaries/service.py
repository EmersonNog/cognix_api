from app.services.summaries.auth import (
    require_authenticated_user,
    require_user_id,
)
from app.services.summaries.generation import (
    gemini_available,
    generate_personalized_summary,
)
from app.services.summaries.payloads import (
    attach_stats,
    default_summary,
    load_summary_payload,
    locked_summary,
    normalize_required_summary_fields,
    normalize_summary_payload,
)
from app.services.summaries.repository import (
    has_completed_session,
    insert_base_summary_if_missing,
    upsert_base_summary,
    upsert_user_summary,
)
from app.services.summaries.stats import (
    fetch_question_total,
    fetch_user_stats,
    latest_attempt_at,
)

__all__ = [
    'attach_stats',
    'default_summary',
    'fetch_question_total',
    'fetch_user_stats',
    'gemini_available',
    'generate_personalized_summary',
    'has_completed_session',
    'insert_base_summary_if_missing',
    'latest_attempt_at',
    'load_summary_payload',
    'locked_summary',
    'normalize_required_summary_fields',
    'normalize_summary_payload',
    'require_authenticated_user',
    'require_user_id',
    'upsert_base_summary',
    'upsert_user_summary',
]
