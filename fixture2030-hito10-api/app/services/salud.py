"""CU13: estado de las cinco dependencias (ping con timeout, en paralelo)."""
from __future__ import annotations

from app.schemas.salud import SaludDependencias
from app.services.ports import Ciclo


class SaludService:
    def __init__(self, adaptadores: dict[str, Ciclo]) -> None:
        self.adaptadores = adaptadores

    async def chequear(self) -> SaludDependencias:
        raise NotImplementedError  # Ola 1 · agente C
