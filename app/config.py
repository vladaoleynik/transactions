from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://events:events@localhost:5432/events"
    redis_url: str = "redis://localhost:6379/0"
    stream_name: str = "transactions"
    consumer_group: str = "processors"
    consumer_name: str = "worker-1"  # unique per worker replica in the same group
    fx_api_base_url: str = "https://api.frankfurter.app"


settings = Settings()
