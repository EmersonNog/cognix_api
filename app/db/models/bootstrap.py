from .common import metadata
from .schema import ensure_internal_schema
from .tables import (
    get_attempt_history_table,
    get_attempts_table,
    get_multiplayer_participants_table,
    get_multiplayer_rooms_table,
    get_question_reports_table,
    get_session_history_table,
    get_sessions_table,
    get_summaries_table,
    get_user_avatar_inventory_table,
    get_user_coin_ledger_table,
    get_user_study_plan_table,
    get_user_summaries_table,
    get_users_table,
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
    ]

    for table_name, register_table in table_specs:
        register_table(table_name)

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
    )
