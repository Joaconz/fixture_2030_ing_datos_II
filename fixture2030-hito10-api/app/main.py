"""Punto de entrada de la API REST integrada del Fixture 2030 (Hito 10).

Capas (RF9): routes (HTTP) → services (casos de uso) → adapters (un driver
por fuente) → bases NoSQL. Este archivo sólo arma la aplicación: clientes en
el lifespan, middleware de request-id y CORS, handlers de error y routers.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.adapters.cassandra import CassandraAdapter
from app.adapters.influx import InfluxAdapter
from app.adapters.mongo import MongoAdapter
from app.adapters.neo4j import Neo4jAdapter
from app.adapters.redis import RedisAdapter
from app.config.settings import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.metricas import RUTA_METRICAS, metricas
from app.core.request_id import RequestIdMiddleware
from app.routes import comentarios, equipos, estadisticas, partidos, salud, sesiones
from app.services.salud import CacheSalud

VERSION = "1.0.0"
DESCRIPCION = """API REST integrada del **Fixture Mundial 2030** (Ingeniería de Datos II, Hito 10).

Cada ruta corresponde a un caso de uso (ver `docs/casos_de_uso.md`) y a una fuente concreta:
MongoDB (equipos y jugadores), Neo4j (partidos, eventos y catálogo de tipos), Cassandra
(comentarios), Redis (sesiones y caché del detalle de partido) e InfluxDB 3 (estadísticas en vivo).
IRIS no forma parte de la arquitectura vigente desde la reentrega del Hito 3 (RF8 documentado como
fuente no cubierta).

Todos los errores usan el mismo formato `{code, message, requestId, details?}`. Toda respuesta
lleva `X-Request-Id`, que también aparece en los logs de la API y de cada adaptador.
"""
TAGS = [
    {"name": "Equipos · MongoDB", "description": "Módulo documental (Hito 4): base `fixture2030`, colecciones `equipos` y `jugadores`."},
    {"name": "Partidos · Neo4j", "description": "Partidos (N2), eventos (N3) y catálogo de tipos (N8) en el grafo del Hito 5; el detalle usa caché Redis."},
    {"name": "Comentarios · Cassandra", "description": "Keyspace `fixture2030_comentarios` (Hito 6): partición (partido, ventana de 10 min, bucket)."},
    {"name": "Sesiones · Redis", "description": "Hash `f30:ses:{id}` con TTL (Hito 7)."},
    {"name": "Estadísticas · InfluxDB", "description": "Tabla `estadisticas_equipo` de la base `fixture2030_vivo` (Hito 8)."},
    {"name": "Salud", "description": "Vida de la API y conectividad de las fuentes."},
]
CABECERAS_EXPUESTAS = ["X-Request-Id", "X-Cache", "Idempotent-Replayed", "Retry-After"]


def crear_adaptadores(settings: Settings) -> dict[str, Any]:
    return {
        "mongodb": MongoAdapter(settings),
        "neo4j": Neo4jAdapter(settings),
        "cassandra": CassandraAdapter(settings),
        "redis": RedisAdapter(settings),
        "influxdb": InfluxAdapter(settings),
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    adapters = crear_adaptadores(settings)
    for a in adapters.values():
        await a.connect()          # no falla si la fuente está caída (ver ports.py)
    app.state.adapters = adapters
    try:
        yield
    finally:
        for a in adapters.values():
            await a.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Fixture 2030 — API REST integrada", version=VERSION,
                  description=DESCRIPCION, openapi_tags=TAGS, lifespan=lifespan)
    install_error_handlers(app)
    app.state.salud_cache = CacheSalud(settings.health_cache_s)
    for r in (equipos.router, partidos.router, comentarios.router, sesiones.router,
              estadisticas.router, salud.router):
        app.include_router(r)
    # Métricas para Prometheus (Hito 13): fuera del contrato OpenAPI.
    app.add_route(RUTA_METRICAS, metricas, methods=["GET"], include_in_schema=False)

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                       allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["Content-Type", "Idempotency-Key", "X-Request-Id"],
                       expose_headers=CABECERAS_EXPUESTAS, max_age=600,
                       # Private Network Access: el front HTTPS de Vercel llama a
                       # http://localhost:8000; el control de origen sigue siendo la lista.
                       allow_private_network=True)
    app.add_middleware(RequestIdMiddleware)  # el más externo: también cubre errores y CORS

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, description=app.description,
                             routes=app.routes, tags=TAGS,
                             servers=[{"url": "http://localhost:8000", "description": "API local (notebook)"}])
        # FastAPI documenta 422 por defecto; esta API responde 400 (ver core/errors.py).
        for ruta in schema.get("paths", {}).values():
            for op in ruta.values():
                respuestas = op.get("responses", {})
                respuestas.pop("422", None)
                # Cabeceras que emite el middleware/handlers en TODA respuesta (RF18) y en los 503.
                for status, resp in respuestas.items():
                    cabeceras = resp.setdefault("headers", {})
                    cabeceras["X-Request-Id"] = {
                        "description": "Identificador de la request (el enviado por el cliente si es seguro, "
                                       "o uno generado); el mismo valor está en `requestId` y en los logs",
                        "schema": {"type": "string"}}
                    if status in ("503", "504"):
                        cabeceras["Retry-After"] = {"description": "Segundos sugeridos antes de reintentar",
                                                    "schema": {"type": "integer"}}
        for nombre in ("HTTPValidationError", "ValidationError"):
            schema.get("components", {}).get("schemas", {}).pop(nombre, None)
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app


app = create_app()
