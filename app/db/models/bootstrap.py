from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text

from .common import metadata
from .schema import ensure_internal_schema
from .tables import (
    get_attempt_history_table,
    get_attempts_table,
    get_coupon_redemptions_table,
    get_flashcard_deck_states_table,
    get_flashcards_table,
    get_google_play_subscriptions_table,
    get_multiplayer_participants_table,
    get_multiplayer_rooms_table,
    get_payment_subscriptions_table,
    get_question_reports_table,
    get_session_history_table,
    get_sessions_table,
    get_summaries_table,
    get_user_avatar_inventory_table,
    get_user_coin_ledger_table,
    get_user_study_plan_table,
    get_user_summaries_table,
    get_users_table,
    get_writing_submission_versions_table,
    get_writing_submissions_table,
    get_writing_themes_table,
)
from .tables.entitlements import get_user_access_grants_table

_POSTGRES_BOOTSTRAP_LOCK_ID = 746113361402687281

@contextmanager
def _schema_bootstrap_lock(engine) -> Iterator[None]:
    if engine.dialect.name != 'postgresql':
        yield
        return

    with engine.connect() as connection:
        connection.execute(
            text('SELECT pg_advisory_lock(:lock_id)'),
            {'lock_id': _POSTGRES_BOOTSTRAP_LOCK_ID},
        )
        try:
            yield
        finally:
            connection.execute(
                text('SELECT pg_advisory_unlock(:lock_id)'),
                {'lock_id': _POSTGRES_BOOTSTRAP_LOCK_ID},
            )

def create_internal_tables(
    engine,
    users_table_name: str,
    attempts_table_name: str,
    attempt_history_table_name: str,
    question_reports_table_name: str,
    multiplayer_rooms_table_name: str,
    multiplayer_participants_table_name: str,
    sessions_table_name: str,
    session_history_table_name: str,
    summaries_table_name: str,
    user_summaries_table_name: str,
    user_coin_ledger_table_name: str,
    user_avatar_inventory_table_name: str,
    study_plan_table_name: str,
    flashcards_table_name: str,
    flashcard_deck_states_table_name: str,
    writing_themes_table_name: str,
    writing_submissions_table_name: str,
    writing_submission_versions_table_name: str,
    coupon_redemptions_table_name: str,
    payment_subscriptions_table_name: str,
    google_play_subscriptions_table_name: str,
    user_access_grants_table_name: str,
) -> None:
    table_specs = [
        (users_table_name, get_users_table),
        (attempts_table_name, get_attempts_table),
        (attempt_history_table_name, get_attempt_history_table),
        (question_reports_table_name, get_question_reports_table),
        (multiplayer_rooms_table_name, get_multiplayer_rooms_table),
        (multiplayer_participants_table_name, get_multiplayer_participants_table),
        (sessions_table_name, get_sessions_table),
        (session_history_table_name, get_session_history_table),
        (summaries_table_name, get_summaries_table),
        (user_summaries_table_name, get_user_summaries_table),
        (user_coin_ledger_table_name, get_user_coin_ledger_table),
        (user_avatar_inventory_table_name, get_user_avatar_inventory_table),
        (study_plan_table_name, get_user_study_plan_table),
        (flashcards_table_name, get_flashcards_table),
        (flashcard_deck_states_table_name, get_flashcard_deck_states_table),
        (writing_themes_table_name, get_writing_themes_table),
        (writing_submissions_table_name, get_writing_submissions_table),
        (
            writing_submission_versions_table_name,
            get_writing_submission_versions_table,
        ),
        (coupon_redemptions_table_name, get_coupon_redemptions_table),
        (payment_subscriptions_table_name, get_payment_subscriptions_table),
        (
            google_play_subscriptions_table_name,
            get_google_play_subscriptions_table,
        ),
        (user_access_grants_table_name, get_user_access_grants_table),
    ]

    for table_name, register_table in table_specs:
        register_table(table_name)

    with _schema_bootstrap_lock(engine):
        metadata.create_all(
            bind=engine,
            tables=[metadata.tables[table_name] for table_name, _ in table_specs],
        )
        ensure_internal_schema(
            engine,
            users_table_name,
            question_reports_table_name,
            multiplayer_rooms_table_name,
            multiplayer_participants_table_name,
            sessions_table_name,
            summaries_table_name,
            user_summaries_table_name,
            payment_subscriptions_table_name,
            google_play_subscriptions_table_name,
            user_access_grants_table_name,
        )
