from enum import StrEnum

from pydantic import Field, HttpUrl, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AegisEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class AegisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    AEGIS_ENV: AegisEnvironment = AegisEnvironment.DEVELOPMENT
    LOG_LEVEL: LogLevel = LogLevel.INFO

    POSTGRES_HOST: str
    POSTGRES_PORT: int = Field(ge=1, le=65535)
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    REDIS_URL: RedisDsn

    S3_ENDPOINT: HttpUrl
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str

    API_PORT: int = Field(ge=1, le=65535, default=8000)
    WEB_PORT: int = Field(ge=1, le=65535, default=3000)

    AEGIS_WS_PATH: str = "/ws/v1/realtime"
    AEGIS_WS_ENABLED: bool = True
    AEGIS_WS_MAX_CONNECTIONS: int = Field(ge=1, default=1000)
    AEGIS_WS_MAX_QUEUE_DEPTH: int = Field(ge=1, default=256)
    AEGIS_WS_MAX_MESSAGE_BYTES: int = Field(ge=1024, default=65536)
    AEGIS_WS_HEARTBEAT_INTERVAL_SECONDS: int = Field(ge=1, default=15)
    AEGIS_WS_IDLE_TIMEOUT_SECONDS: int = Field(ge=1, default=45)
    AEGIS_WS_DEV_AUTH_ENABLED: bool = True
    AEGIS_WS_DEV_AUTH_TOKEN: str = "aegis-dev-token"
    AEGIS_WS_GATEWAY_CONSUMER_GROUP: str = "aegis-ws-gateway"
    AEGIS_WS_SNAPSHOT_GAP_THRESHOLD: int = Field(ge=1, default=500)

    AEGIS_DEV_AUTH_ENABLED: bool = True
    AEGIS_SESSION_COOKIE_NAME: str = "aegis_session"
    AEGIS_CSRF_COOKIE_NAME: str = "aegis_csrf"
    AEGIS_CSRF_HEADER_NAME: str = "X-CSRF-Token"
    AEGIS_SESSION_TTL_SECONDS: int = Field(ge=60, default=28800)
    AEGIS_CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"
    AEGIS_OIDC_ENABLED: bool = False
    AEGIS_OIDC_ISSUER: str = ""
    AEGIS_OIDC_CLIENT_ID: str = ""
    AEGIS_OIDC_CLIENT_SECRET: str = ""
    AEGIS_OIDC_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback"
    AEGIS_OIDC_SCOPES: str = "openid profile email"
    AEGIS_WEB_BASE_URL: str = "http://localhost:3000"

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.AEGIS_CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def postgres_dsn(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @property
    def postgres_async_dsn(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @field_validator("POSTGRES_PASSWORD")
    @classmethod
    def password_not_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "POSTGRES_PASSWORD must not be blank"
            raise ValueError(msg)
        return value


def load_settings() -> AegisSettings:
    return AegisSettings()
