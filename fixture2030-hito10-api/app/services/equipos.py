"""Casos de uso CU1–CU3: ficha de equipo, plantel paginado, partidos del equipo."""
from __future__ import annotations

from app.schemas.equipos import Equipo, PaginaJugadores, PartidosDeEquipo
from app.services.ports import MongoPort, Neo4jPort


class EquiposService:
    def __init__(self, mongo: MongoPort, neo4j: Neo4jPort) -> None:
        self.mongo = mongo
        self.neo4j = neo4j

    async def get_equipo(self, codigo: str) -> Equipo:
        raise NotImplementedError  # Ola 1 · agente A

    async def list_jugadores(self, codigo: str, posicion: str | None, limit: int,
                             cursor: str | None) -> PaginaJugadores:
        raise NotImplementedError  # Ola 1 · agente A

    async def list_partidos(self, codigo: str, limit: int) -> PartidosDeEquipo:
        raise NotImplementedError  # Ola 1 · agente A
