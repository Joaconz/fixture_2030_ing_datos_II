"""Adaptador Neo4j (Hito 5) — driver oficial async.

STUB de la Ola 0: lo implementa el agente A de la Ola 1 contra
`app/services/ports.py`. Todo acceso de red debe pasar por `app.adapters.base.ejecutar`.
"""
from __future__ import annotations

from app.config.settings import Settings


class Neo4jAdapter:
    nombre = "neo4j"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ping(self) -> None:
        raise NotImplementedError
