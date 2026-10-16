"""CU13: estado de las cinco dependencias (ping con timeout, en paralelo).

Cada adaptador acota su ping con el timeout general (`app.adapters.base.ejecutar`).
Cualquier excepción del ping cuenta como DOWN; el `detalle` público es genérico
(nunca hosts, URIs ni credenciales). Un adaptador sin ping implementado también es DOWN.
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.core.errors import DependencyUnavailableError
from app.schemas.salud import EstadoDependencia, SaludDependencias
from app.services.ports import Ciclo

log = logging.getLogger("fixture2030.api")


class SaludService:
    def __init__(self, adaptadores: dict[str, Ciclo]) -> None:
        self.adaptadores = adaptadores

    async def _chequear_uno(self, nombre: str, adaptador: Ciclo) -> EstadoDependencia:
        inicio = time.perf_counter()
        detalle: str | None = None
        try:
            await adaptador.ping()
        except NotImplementedError:
            detalle = "no implementado"
        except DependencyUnavailableError as exc:
            detalle = "timeout" if exc.timeout else "no responde"
        except Exception as exc:  # noqa: BLE001 — cualquier falla del ping es DOWN
            log.warning("ping con error inesperado", extra={
                "evento": "dependencia", "dependencia": nombre, "operacion": "ping",
                "tipo": type(exc).__name__})
            detalle = "no responde"
        latencia = round((time.perf_counter() - inicio) * 1000, 1)
        if detalle is None:
            return EstadoDependencia(nombre=nombre, estado="UP", latenciaMs=latencia)
        return EstadoDependencia(nombre=nombre, estado="DOWN", latenciaMs=latencia, detalle=detalle)

    async def chequear(self) -> SaludDependencias:
        estados = await asyncio.gather(
            *(self._chequear_uno(n, a) for n, a in self.adaptadores.items()))
        estado = "OK" if all(e.estado == "UP" for e in estados) else "DEGRADADO"
        return SaludDependencias(estado=estado, dependencias=list(estados))
