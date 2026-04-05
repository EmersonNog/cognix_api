from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    database_url: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/cognix'
    question_table: str = 'questions'
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
    allowed_origins: list[str] = ['*']
    firebase_credentials: str | None = None
    firebase_clock_skew_seconds: int = 5
    gemini_api_key: str | None = None
    gemini_model: str = 'gemini-3-flash-preview'

settings = Settings()