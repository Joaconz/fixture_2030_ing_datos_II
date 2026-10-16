"""Pieza común a los cinco adaptadores: timeout, traducción de fallas y log.

Cada adaptador envuelve TODA operación de red con `ejecutar(...)`:
  - `asyncio.wait_for` con el timeout configurado (RNF8): una fuente lenta o
    caída nunca deja la request esperando indefinidamente (RNF9);
  - las excepciones de conexión/timeout propias del driver (que cada adaptador
    declara en `errores_de_disponibilidad`) se traducen a
    `DependencyUnavailableError` → HTTP 503. Las `ApiError` de dominio pasan tal cual;
  - se registra una línea de log con dependencia, operación, resultado y
    duración, sin parámetros ni resultados (RNF10 / RNF7).
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable
from typing import TypeVar

from app.core.errors import ApiError, DependencyUnavailableError

T = TypeVar("T")
log = logging.getLogger("fixture2030.adaptador")


async def ejecutar(
    dependencia: str,
    operacion: str,
    awaitable: Awaitable[T],
    *,
    timeout_s: float,
    errores_de_disponibilidad: tuple[type[BaseException], ...] = (),
) -> T:
    inicio = time.perf_counter()
    resultado = "ok"
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_s)
    except (asyncio.TimeoutError, TimeoutError) as exc:
        resultado = "timeout"
        raise DependencyUnavailableError(dependencia, timeout=True) from exc
    except ApiError as exc:
        resultado = f"dominio:{exc.code}"
        raise
    except errores_de_disponibilidad as exc:
        resultado = "no_disponible"
        log.warning("dependencia no disponible", extra={
            "evento": "dependencia", "dependencia": dependencia, "operacion": operacion,
            "resultado": resultado, "tipo": type(exc).__name__})
        raise DependencyUnavailableError(dependencia) from exc
    finally:
        log.info("dependencia", extra={
            "evento": "dependencia", "dependencia": dependencia, "operacion": operacion,
            "resultado": resultado,
            "duracion_ms": round((time.perf_counter() - inicio) * 1000, 1)})
