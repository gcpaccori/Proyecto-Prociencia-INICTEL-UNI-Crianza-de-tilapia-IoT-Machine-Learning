from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AQUA_",
        extra="ignore",
    )

    app_name: str = "Aquaculture Digital Twin Backend"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(
        default=(
            "postgresql+psycopg://postgres:postgres"
            "@localhost:5432/aquaculture_digital_twin"
        )
    )
    echo_sql: bool = False
    log_level: str = "INFO"
    enable_docs: bool = True
    enable_unprefixed_api_aliases: bool = True
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    store_backend: str = "memory"
    legacy_database_name: str | None = None
    # Las politicas de alarma son de Laravel y pueden vivir en otra base que
    # las lecturas de sensores: en produccion coinciden, pero un entorno de
    # pruebas lee los datos reales y conserva sus propias politicas. Si no se
    # indica nada se usa la misma base antigua, que es el comportamiento previo.
    policy_database_name: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
