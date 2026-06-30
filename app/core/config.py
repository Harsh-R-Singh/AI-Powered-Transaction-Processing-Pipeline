from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/transactions_db"
    REDIS_URL: str = "redis://redis:6379/0"
    GEMINI_API_KEY: str 
    UPLOAD_DIR: str = "/app/uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()