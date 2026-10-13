"""CU4: detalle de partido (Neo4j) con cache-aside en Redis (diseño del Hito 7)."""
from __future__ import annotations

from typing import Literal

from app.schemas.partidos import PartidoDetalle
from app.services.ports import Neo4jPort, RedisPort

EstadoCache = Literal["HIT", "MISS", "BYPASS"]


class PartidosService:
    def __init__(self, neo4j: Neo4jPort, redis: RedisPort, cache_ttl_s: int) -> None:
        self.neo4j = neo4j
        self.redis = redis
        self.cache_ttl_s = cache_ttl_s

    async def get_detalle(self, partido_id: str) -> tuple[PartidoDetalle, EstadoCache]:
        raise NotImplementedError  # Ola 1 · agente C
