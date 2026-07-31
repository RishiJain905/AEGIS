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

    # Phase 31 observability
    OTEL_SERVICE_NAME: str = "aegis-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_EXPORTER_OTLP_PROTOCOL: str = "grpc"
    OTEL_TRACES_SAMPLER: str = "parentbased_traceidratio"
    OTEL_TRACES_SAMPLER_ARG: float = Field(default=1.0, ge=0.0, le=1.0)
    OTEL_METRICS_EXPORT_INTERVAL_MS: int = Field(default=15000, ge=1000)
    OTEL_ENABLED: bool = True
    OTEL_EXPORTER_FAILURE_MODE: str = "ignore"
    AEGIS_HEALTH_PROBE_TIMEOUT_MS: int = Field(default=2000, ge=100, le=30000)
    AEGIS_READY_REQUIRE_REDIS: bool = True
    AEGIS_READY_REQUIRE_OBJECT_STORAGE: bool = True
    AEGIS_LOG_JSON: bool = True
    AEGIS_TELEMETRY_RETENTION_HOURS: int = Field(default=168, ge=1)

    # Phase 2 (scenario revamp) — in-process simulation tick engine. The API process
    # owns the single RunCommandService runtime cache, so it is the single writer that
    # periodically advances every RUNNING run. See docs/superpowers/specs.
    AEGIS_SIM_TICK_ENABLED: bool = True
    AEGIS_SIM_TICK_INTERVAL_SECONDS: float = Field(default=2.0, gt=0.0)
    # Steps per run per tick. Operation Silent Relay emits ~1075 events across its full
    # 1500 sim-second horizon; at one step every two seconds that is a ~30-minute wall-clock
    # engagement with a ~30-second wait before the first alert, which reads to an operator
    # as a run that never started. Four steps per tick brings a full run to ~8 minutes and
    # the first alert to under ten seconds. Determinism is untouched: the event sequence is
    # a function of (scenario, seed, actions), and this only changes how fast wall-clock
    # time delivers it.
    AEGIS_SIM_STEPS_PER_TICK: int = Field(default=4, ge=1)
    # Engine-visible completion horizon: the ticker STOPs a run once its virtual clock
    # has advanced this many sim-seconds past the scenario's initial sim time. Sim-time
    # is restart-safe (restored from the checkpoint) and covers the full scripted
    # narrative (Operation Silent Relay: all scripted effects fire by ~00:21:00, hidden
    # reveals by <=720s). Distinct from golden-seeds `simulationSteps`, which is test
    # metadata for the fixed-step determinism harness, not a live horizon.
    AEGIS_SIM_MAX_SIM_SECONDS: int = Field(default=1500, ge=1)
    # Circuit breaker: consecutive failed ticks a single run may take before the tick engine
    # quarantines it (stops it) instead of retrying it forever on the shared loop. Counted
    # in-process and cleared by any successful advance, so it only trips on a run that is
    # genuinely stuck rather than one hitting transient contention.
    AEGIS_SIM_TICK_FAILURE_THRESHOLD: int = Field(default=3, ge=1)
    # Fog of war — threat-tempo saturation window (sim-seconds). An undisclosed, triggered
    # hidden condition reaches full ambient pressure after dwelling undetected this long.
    AEGIS_THREAT_TEMPO_SATURATION_SIM_SECONDS: float = Field(default=600.0, gt=0.0)

    # Phase 7 — autonomous triage loop budgets. The event-driven loop enqueues bounded
    # WATCHTOWER/ORACLE auto-tasks when new alerts land; these cap local-model load so a
    # burst of alerts cannot flood the agent runtime. All env-tunable.
    # Max simultaneously-queued/running autonomy tasks per run.
    AEGIS_AUTONOMY_MAX_CONCURRENT_TASKS: int = Field(default=2, ge=0)
    # Wall-clock seconds a given asset is on cooldown after an autonomy task fires for it.
    AEGIS_AUTONOMY_PER_ASSET_COOLDOWN_SECONDS: float = Field(default=120.0, ge=0.0)
    # Hard ceiling on total autonomy tasks a single run may ever enqueue.
    AEGIS_AUTONOMY_MAX_TASKS_PER_RUN: int = Field(default=50, ge=0)
    # Master switch for the autonomous triage loop (independent of the tick engine).
    AEGIS_AUTONOMY_ENABLED: bool = True
    # How often the autonomy poller scans RUNNING runs for newly-persisted alerts.
    AEGIS_AUTONOMY_POLL_INTERVAL_SECONDS: float = Field(default=3.0, gt=0.0)

    # Phase 32 HTTP trust-boundary hardening
    AEGIS_REQUEST_BODY_MAX_BYTES: int = Field(default=1_048_576, ge=1)
    AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=120, ge=1)
    AEGIS_RATE_LIMIT_BURST: int = Field(default=30, ge=1)
    AEGIS_RATE_LIMIT_MAX_BUCKETS: int = Field(default=10_000, ge=100)
    AEGIS_SECURITY_HSTS_ENABLED: bool = False
    AEGIS_SECURITY_HSTS_MAX_AGE_SECONDS: int = Field(default=31_536_000, ge=1)

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
