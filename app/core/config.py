from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
    )
 
    database_url: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/cognix' 
    question_table: str = 'questions' 
    users_table: str = 'users'
    attempts_table: str = 'question_attempts'
    sessions_table: str = 'training_sessions'
    summaries_table: str = 'training_summaries'
    user_summaries_table: str = 'training_summaries_user' 
    allowed_origins: list[str] = ['*'] 
    firebase_credentials: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = 'gemini-3-flash-preview'
 
settings = Settings()