"""Inyección de dependencias: adaptadores (creados en el lifespan) → servicios.

Las pruebas unitarias reemplazan los `get_<fuente>` con adaptadores falsos
mediante `app.dependency_overrides`, sin tocar rutas ni servicios.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.config.settings import Settings, get_settings
from app.services.comentarios import ComentariosService
from app.services.equipos import EquiposService
from app.services.estadisticas import EstadisticasService
from app.services.eventos import EventosService
from app.services.partidos import PartidosService
from app.services.ports import CassandraPort, InfluxPort, MongoPort, Neo4jPort, RedisPort
from app.services.salud import SaludService
from app.services.sesiones import SesionesService


def get_mongo(request: Request) -> MongoPort:
    return request.app.state.adapters["mongodb"]


def get_neo4j(request: Request) -> Neo4jPort:
    return request.app.state.adapters["neo4j"]


def get_cassandra(request: Request) -> CassandraPort:
    return request.app.state.adapters["cassandra"]


def get_redis(request: Request) -> RedisPort:
    return request.app.state.adapters["redis"]


def get_influx(request: Request) -> InfluxPort:
    return request.app.state.adapters["influxdb"]


SettingsDep = Annotated[Settings, Depends(get_settings)]


def equipos_service(mongo: Annotated[MongoPort, Depends(get_mongo)],
                    neo4j: Annotated[Neo4jPort, Depends(get_neo4j)]) -> EquiposService:
    return EquiposService(mongo, neo4j)


def partidos_service(neo4j: Annotated[Neo4jPort, Depends(get_neo4j)],
                     redis: Annotated[RedisPort, Depends(get_redis)],
                     settings: SettingsDep) -> PartidosService:
    return PartidosService(neo4j, redis, settings.cache_partido_ttl_s)


def eventos_service(neo4j: Annotated[Neo4jPort, Depends(get_neo4j)],
                    redis: Annotated[RedisPort, Depends(get_redis)]) -> EventosService:
    return EventosService(neo4j, redis)


def comentarios_service(cassandra: Annotated[CassandraPort, Depends(get_cassandra)]) -> ComentariosService:
    return ComentariosService(cassandra)


def sesiones_service(redis: Annotated[RedisPort, Depends(get_redis)]) -> SesionesService:
    return SesionesService(redis)


def estadisticas_service(influx: Annotated[InfluxPort, Depends(get_influx)]) -> EstadisticasService:
    return EstadisticasService(influx)


def salud_service(mongo: Annotated[MongoPort, Depends(get_mongo)],
                  neo4j: Annotated[Neo4jPort, Depends(get_neo4j)],
                  cassandra: Annotated[CassandraPort, Depends(get_cassandra)],
                  redis: Annotated[RedisPort, Depends(get_redis)],
                  influx: Annotated[InfluxPort, Depends(get_influx)]) -> SaludService:
    return SaludService({"mongodb": mongo, "neo4j": neo4j, "cassandra": cassandra,
                         "redis": redis, "influxdb": influx})
