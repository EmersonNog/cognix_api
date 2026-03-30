from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/cognix'
    question_table: str = 'questoes'
    allowed_origins: list[str] = ['*']
    firebase_credentials: str | None = None

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'


settings = Settings()
