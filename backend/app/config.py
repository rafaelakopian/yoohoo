from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Yoohoo"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-to-a-random-secret-key"
    api_v1_prefix: str = "/api/v1"

    # Platform Branding
    platform_name: str = "Yoohoo"
    platform_name_short: str = "Yoohoo"
    platform_url: str = "https://yoohoo.nl"

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "yoohoo"
    postgres_password: str = "yoohoo_secret"
    postgres_db: str = "ps_core_db"
    postgres_admin_db: str = "postgres"
    tenant_db_prefix: str = "ps_t_"
    tenant_db_suffix: str = "_db"

    # PgBouncer
    pgbouncer_host: str = "pgbouncer"
    pgbouncer_port: int = 6432
    use_pgbouncer: bool = False

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # arq Worker
    arq_redis_db: int = 1
    arq_max_jobs: int = 10
    arq_job_timeout: int = 300

    # JWT
    jwt_secret_key: str = "change-me-jwt-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:1000"

    # Email
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@yoohoo.nl"
    smtp_use_tls: bool = False

    # Email Provider
    email_provider: str = "smtp"
    email_from_name: str = "Yoohoo"
    email_fallback_provider: str = ""
    resend_api_key: str = ""
    brevo_api_key: str = ""

    # Email Senders (per-type, fall back to smtp_from / email_from_name when empty)
    email_account_from: str = ""
    email_account_name: str = ""
    email_security_from: str = ""
    email_security_name: str = ""
    email_notification_from: str = ""
    email_notification_name: str = ""
    email_billing_from: str = ""
    email_billing_name: str = ""

    # Frontend
    frontend_url: str = "http://localhost:2000"

    # Email verification
    email_verification_expire_hours: int = 48
    unverified_cleanup_days: int = 7

    # Invitation
    invitation_expire_hours: int = 72
    invitation_max_pending_per_school: int = 50

    # Password Reset
    password_reset_expire_minutes: int = 30
    password_reset_rate_limit_per_hour: int = 3

    # 2FA / TOTP
    totp_issuer_name: str = ""
    totp_backup_code_count: int = 10

    # Sessions
    max_active_sessions: int = 10

    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_tenant_per_minute: int = 300

    # Request size limit (bytes, default 10MB — defense-in-depth alongside nginx)
    max_request_body_size: int = 10_485_760

    # Brute Force Protection
    login_max_attempts: int = 5
    login_lockout_seconds: int = 900  # 15 minutes

    # Billing
    billing_webhook_base_url: str = "http://localhost:8000/api/v1"
    billing_invoice_prefix: str = "PS"
    billing_default_currency: str = "EUR"
    billing_tax_rate_percent: int = 21  # Dutch BTW
    billing_trial_days: int = 30
    billing_invoice_due_days: int = 14
    mollie_test_mode: bool = True
    stripe_test_mode: bool = True

    # Sentry
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_environment: str = ""

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def db_host(self) -> str:
        """Route through PgBouncer when enabled, otherwise direct to PostgreSQL."""
        return self.pgbouncer_host if self.use_pgbouncer else self.postgres_host

    @property
    def db_port(self) -> int:
        """Route through PgBouncer when enabled, otherwise direct to PostgreSQL."""
        return self.pgbouncer_port if self.use_pgbouncer else self.postgres_port

    @property
    def central_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    @property
    def central_database_url_sync(self) -> str:
        """Sync URL always bypasses PgBouncer (used by Alembic)."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def tenant_db_name(self, slug: str) -> str:
        return f"{self.tenant_db_prefix}{slug}{self.tenant_db_suffix}"

    def tenant_database_url(self, slug: str) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.tenant_db_name(slug)}"
        )

    def tenant_database_url_sync(self, slug: str) -> str:
        """Sync URL always bypasses PgBouncer (used by Alembic)."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.tenant_db_name(slug)}"
        )

    @property
    def postgres_admin_url(self) -> str:
        """Admin URL bypasses PgBouncer (CREATE DATABASE needs direct connection)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_admin_db}"
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
