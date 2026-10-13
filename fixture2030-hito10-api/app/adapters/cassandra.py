"""Adaptador Cassandra (Hito 6) — cassandra-driver, prepared statements.

STUB de la Ola 0: lo implementa el agente B de la Ola 1 contra
`app/services/ports.py`. Todo acceso de red debe pasar por `app.adapters.base.ejecutar`.
"""
from __future__ import annotations

from app.config.settings import Settings


class CassandraAdapter:
    nombre = "cassandra"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ping(self) -> None:
        raise NotImplementedError
