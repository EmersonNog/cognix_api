from .entitlements import ensure_user_access_grants_schema
from .multiplayer import ensure_multiplayer_schema
from .payments import ensure_payment_subscriptions_schema
from .question_reports import ensure_question_reports_schema
from .sessions import ensure_sessions_schema
from .summaries import ensure_summary_payload_schema
from .users import ensure_users_schema


def ensure_internal_schema(
    engine,
    users_table_name: str,
    question_reports_table_name: str,
    multiplayer_rooms_table_name: str,
    multiplayer_participants_table_name: str,
    sessions_table_name: str,
    summaries_table_name: str,
    user_summaries_table_name: str,
    payment_subscriptions_table_name: str,
    user_access_grants_table_name: str,
) -> None:
    ensure_users_schema(engine, users_table_name)
    ensure_question_reports_schema(engine, question_reports_table_name)
    ensure_multiplayer_schema(
        engine,
        multiplayer_rooms_table_name,
        multiplayer_participants_table_name,
    )
    ensure_sessions_schema(engine, sessions_table_name)
    ensure_summary_payload_schema(engine, summaries_table_name)
    ensure_summary_payload_schema(engine, user_summaries_table_name)
    ensure_payment_subscriptions_schema(engine, payment_subscriptions_table_name)
    ensure_user_access_grants_schema(engine, user_access_grants_table_name)
