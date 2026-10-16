"""CU4: detalle de partido (Neo4j) con cache-aside en Redis (diseño del Hito 7).

    1. GET f30:cache:partido:{id} en Redis → JSON válido: se devuelve ("HIT").
       Redis caído: se sigue a Neo4j y la respuesta sale "BYPASS".
       JSON corrupto o de otra versión del contrato: se trata como MISS y se sobrescribe.
    2. Neo4j: partido inexistente → 404 MATCH_NOT_FOUND (la ausencia NO se cachea);
       Neo4j caído → 503 (sólo se llega acá si no había copia en caché).
    3. SET … EX ttl ("MISS"). Si el SET falla, la respuesta sale igual ("BYPASS"):
       la caché es una optimización, no una fuente.
"""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import ValidationError

from app.core.errors import DependencyUnavailableError, NotFoundError
from app.schemas.partidos import PartidoDetalle
from app.services.ports import Neo4jPort, RedisPort

EstadoCache = Literal["HIT", "MISS", "BYPASS"]
log = logging.getLogger("fixture2030.api")


class PartidosService:
    def __init__(self, neo4j: Neo4jPort, redis: RedisPort, cache_ttl_s: int) -> None:
        self.neo4j = neo4j
        self.redis = redis
        self.cache_ttl_s = cache_ttl_s

    async def get_detalle(self, partido_id: str) -> tuple[PartidoDetalle, EstadoCache]:
        redis_disponible = True
        try:
            en_cache = await self.redis.cache_get_partido(partido_id)
        except DependencyUnavailableError:
            redis_disponible, en_cache = False, None

        if en_cache is not None:
            try:
                return PartidoDetalle.model_validate_json(en_cache), "HIT"
            except ValidationError:
                log.warning("copia en caché inválida: se reconstruye desde Neo4j",
                            extra={"evento": "cache", "cache": "CORRUPTA"})

        detalle = await self.neo4j.get_partido(partido_id)   # 503 si Neo4j no responde
        if detalle is None:
            raise NotFoundError(f"No existe el partido {partido_id}.", code="MATCH_NOT_FOUND")

        if not redis_disponible:
            return detalle, "BYPASS"
        try:
            await self.redis.cache_set_partido(partido_id, detalle.model_dump_json(), self.cache_ttl_s)
        except DependencyUnavailableError:
            return detalle, "BYPASS"
        return detalle, "MISS"
