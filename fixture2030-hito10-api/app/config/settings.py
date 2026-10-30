"""Configuración de la API (RF16 / RNF6).

Todo valor de conexión llega por variables de entorno o por un `.env` local
ignorado por git. Las credenciales son `SecretStr`: nunca se imprimen ni se
loguean (RNF7). Ningún default de este archivo es un secreto.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- API ---------------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Timeout general por operación contra una dependencia (RNF8). Cada driver
    # tiene además su propio timeout de conexión, alineado con este valor.
    dep_timeout_s: float = Field(default=2.0, gt=0, le=30)

    # --- Salud (Hito 11 §5.6) ----------------------------------------------
    # Segundos que se reutiliza el resultado del chequeo profundo (0 = sin caché).
    health_cache_s: float = Field(default=5.0, ge=0, le=300)
    # Fuentes sin las cuales la API no está lista (/health/ready → 503 NO_LISTA).
    ready_esenciales: str = "mongodb,neo4j"

    # --- MongoDB (Hito 4) --------------------------------------------------
    mongo_uri: SecretStr = SecretStr("mongodb://localhost:27017")
    mongo_db: str = "fixture2030"

    # --- Neo4j (Hito 5) ----------------------------------------------------
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"

    # --- Cassandra (Hito 6) ------------------------------------------------
    cassandra_hosts: str = "127.0.0.1"
    cassandra_port: int = 9042
    # Hito 12 · optimización medida: segundos que se reutiliza la configuración de partición
    # (Q0) de un partido. 0 = desactivada (comportamiento del Hito 10, línea base).
    comentarios_config_cache_s: float = Field(default=0, ge=0, le=3600)
    cassandra_keyspace: str = "fixture2030_comentarios"
    cassandra_dc: str = "datacenter1"

    # --- Redis (Hito 7) ----------------------------------------------------
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    cache_partido_ttl_s: int = Field(default=60, ge=1, le=3600)

    # --- InfluxDB 3 Core (Hito 8) ------------------------------------------
    influx_url: str = "http://127.0.0.1:8181"
    influx_db: str = "fixture2030_vivo"
    influx_token: SecretStr | None = None
    influx_token_file: Path = API_DIR.parent / "fixture2030-influxdb" / "secrets" / "admin-token.json"

    @field_validator("influx_token_file", mode="after")
    @classmethod
    def _resolver_relativo(cls, v: Path) -> Path:
        return v if v.is_absolute() else (API_DIR / v).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ready_esenciales_list(self) -> tuple[str, ...]:
        return tuple(n.strip() for n in self.ready_esenciales.split(",") if n.strip())

    @property
    def cassandra_host_list(self) -> list[str]:
        return [h.strip() for h in self.cassandra_hosts.split(",") if h.strip()]

    def influx_token_value(self) -> str | None:
        """Token de InfluxDB: variable de entorno o archivo local (fuera del repo)."""
        if self.influx_token and self.influx_token.get_secret_value():
            return self.influx_token.get_secret_value()
        try:
            return json.loads(self.influx_token_file.read_text(encoding="utf-8"))["token"]
        except (OSError, ValueError, KeyError):
            return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
