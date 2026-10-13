"""Fixtures de las pruebas unitarias: la API real con adaptadores falsos.

No se levanta ninguna base: `app.dependency_overrides` reemplaza cada
`get_<fuente>` por un objeto que implementa el mismo puerto (app/services/ports.py).
Cada agente/módulo define sus fakes en tests/unit/fakes_<fuente>.py.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import deps
from app.core.errors import DependencyUnavailableError
from app.main import create_app


class FuenteCaida:
    """Cualquier método async lanza DependencyUnavailableError (equivale a un 503)."""

    def __init__(self, nombre: str, timeout: bool = False) -> None:
        self.nombre = nombre
        self.timeout = timeout
        self.llamadas: list[str] = []

    def __getattr__(self, metodo: str) -> Callable[..., Any]:
        if metodo.startswith("__"):
            raise AttributeError(metodo)

        async def _falla(*_: Any, **__: Any) -> Any:
            self.llamadas.append(metodo)
            raise DependencyUnavailableError(self.nombre, timeout=self.timeout)
        return _falla


class FuenteNoTocar:
    """Falla el test si el servicio llega a la fuente (para probar RNF3)."""

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre

    def __getattr__(self, metodo: str) -> Callable[..., Any]:
        if metodo.startswith("__"):
            raise AttributeError(metodo)

        async def _nunca(*_: Any, **__: Any) -> Any:
            raise AssertionError(f"{self.nombre}.{metodo} no debía llamarse: la validación tenía que cortar antes")
        return _nunca


_GETTERS = {"mongodb": deps.get_mongo, "neo4j": deps.get_neo4j, "cassandra": deps.get_cassandra,
            "redis": deps.get_redis, "influxdb": deps.get_influx}


@pytest.fixture
def make_client() -> Callable[..., TestClient]:
    """make_client(mongodb=fake, redis=fake, ...) → TestClient. Las fuentes no
    indicadas quedan como FuenteCaida (si se usan por error, el test ve un 503)."""
    def _make(**fakes: Any) -> TestClient:
        app = create_app()
        for nombre, getter in _GETTERS.items():
            fake = fakes.get(nombre, FuenteCaida(nombre))
            app.dependency_overrides[getter] = lambda f=fake: f
        return TestClient(app, raise_server_exceptions=False)
    return _make
