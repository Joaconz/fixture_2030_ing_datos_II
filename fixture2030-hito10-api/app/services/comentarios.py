"""CU8–CU9: comentarios paginados por partición y alta idempotente (Cassandra)."""
from __future__ import annotations

from app.schemas.comentarios import Comentario, ComentarioNuevo, PaginaComentarios
from app.services.ports import CassandraPort


class ComentariosService:
    def __init__(self, cassandra: CassandraPort) -> None:
        self.cassandra = cassandra

    async def listar(self, partido_id: str, limit: int, cursor: str | None) -> PaginaComentarios:
        raise NotImplementedError  # Ola 1 · agente B

    async def publicar(self, partido_id: str, idempotency_key: str,
                       nuevo: ComentarioNuevo) -> tuple[Comentario, bool]:
        """Devuelve (comentario, creado). creado=False ⇒ reintento detectado."""
        raise NotImplementedError  # Ola 1 · agente B
