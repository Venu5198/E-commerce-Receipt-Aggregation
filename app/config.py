from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://mongo:27017"
    MONGO_DB_NAME: str = "ecommerce_receipts"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    JWT_SECRET_KEY: str = "supersecret_ecommerce_receipt_jwt_key_that_is_32_bytes_min"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REDIS_URL: str = "redis://redis:6379/0"
    USE_REDIS_CACHE: bool = False
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    USE_RABBITMQ: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
