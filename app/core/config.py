from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    database_url: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/cognix'
    question_table: str = 'questions'
    question_reports_table: str = 'question_reports'
    multiplayer_rooms_table: str = 'multiplayer_rooms'
    multiplayer_participants_table: str = 'multiplayer_room_participants'
    users_table: str = 'users'
    attempts_table: str = 'question_attempts'
    attempt_history_table: str = 'question_attempt_history'
    sessions_table: str = 'training_sessions'
    session_history_table: str = 'training_session_history'
    summaries_table: str = 'training_summaries'
    user_summaries_table: str = 'training_summaries_user'
    user_coin_ledger_table: str = 'user_coin_ledger'
    user_avatar_inventory_table: str = 'user_avatar_inventory'
    study_plan_table: str = 'user_study_plans'
    flashcards_table: str = 'user_flashcards'
    flashcard_deck_states_table: str = 'user_flashcard_deck_states'
    writing_themes_table: str = 'writing_themes'
    writing_submissions_table: str = 'writing_submissions'
    writing_submission_versions_table: str = 'writing_submission_versions'
    coupon_redemptions_table: str = 'coupon_redemptions'
    allowed_origins: list[str] = ['*']
    firebase_credentials: str | None = None
    firebase_clock_skew_seconds: int = 5
    gemini_api_key: str | None = None
    gemini_model: str = 'gemini-2.5-flash-lite'
    profile_ai_insight_ttl_minutes: int = 1440
    app_timezone: str = 'America/Sao_Paulo'
    abacatepay_api_key: str | None = None
    abacatepay_api_base_url: str = 'https://api.abacatepay.com/v2'
    abacatepay_app_url: str = 'https://mkt.cognix-hub.com'
    abacatepay_product_id_mensal: str | None = None
    abacatepay_product_id_anual: str | None = None
    abacatepay_coupon_mensal_first_month: str | None = None
    abacatepay_hash_secret: str | None = None

settings = Settings()
