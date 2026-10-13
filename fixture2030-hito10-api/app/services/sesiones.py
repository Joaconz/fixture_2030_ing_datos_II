"""CU10–CU11: validar e invalidar una sesión (Redis)."""
from __future__ import annotations

from app.schemas.sesiones import Sesion
from app.services.ports import RedisPort


class SesionesService:
    def __init__(self, redis: RedisPort) -> None:
        self.redis = redis

    async def obtener(self, sesion_id: str) -> Sesion:
        raise NotImplementedError  # Ola 1 · agente B

    async def cerrar(self, sesion_id: str) -> None:
        raise NotImplementedError  # Ola 1 · agente B
