from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "FinAgent"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://finagent:finagent123@localhost:5432/finagent_db"
    database_sync_url: str = "postgresql://finagent:finagent123@localhost:5432/finagent_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    llm_provider: str = "groq"
    
    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    
    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()