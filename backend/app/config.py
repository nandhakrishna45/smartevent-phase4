from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    secret_key: str = "dev-only-change-me"
    database_url: str = "sqlite:///./smartevent.db"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
