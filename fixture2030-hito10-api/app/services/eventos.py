"""CU5–CU7: timeline de eventos, alta validada por tipo (N8) y cierre CP del partido (N2)."""
from __future__ import annotations

from app.schemas.eventos import Evento, EventoNuevo, PaginaEventos
from app.schemas.partidos import CambioEstado, PartidoDetalle
from app.services.ports import Neo4jPort, RedisPort


class EventosService:
    def __init__(self, neo4j: Neo4jPort, redis: RedisPort) -> None:
        self.neo4j = neo4j
        self.redis = redis

    async def list_eventos(self, partido_id: str, tipo: str | None, limit: int,
                           cursor: str | None) -> PaginaEventos:
        raise NotImplementedError  # Ola 1 · agente A

    async def registrar(self, partido_id: str, idempotency_key: str,
                        nuevo: EventoNuevo) -> tuple[Evento, bool]:
        """Devuelve (evento, creado). creado=False ⇒ reintento con la misma clave."""
        raise NotImplementedError  # Ola 1 · agente A

    async def cerrar(self, partido_id: str, cambio: CambioEstado) -> PartidoDetalle:
        raise NotImplementedError  # Ola 1 · agente A
