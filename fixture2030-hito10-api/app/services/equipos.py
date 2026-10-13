"""Casos de uso CU1–CU3: ficha de equipo, plantel paginado, partidos del equipo.

CU1 y CU2 leen MongoDB (Hito 4); CU3 lee Neo4j (Hito 5). La API NO cruza las dos
bases por código de equipo (Hallazgo H1: algunos códigos difieren entre Mongo y
el grafo), así que cada caso de uso responde sólo con lo que sabe su fuente.
"""
from __future__ import annotations

from app.core.errors import NotFoundError
from app.schemas.equipos import Equipo, PaginaJugadores, PartidosDeEquipo
from app.services import cursor_entero
from app.services.ports import MongoPort, Neo4jPort

TIPO_CURSOR = "jug"   # el cursor del plantel lleva el último dorsal devuelto


def _equipo_inexistente(codigo: str) -> NotFoundError:
    return NotFoundError(f"No existe el equipo {codigo}.", code="TEAM_NOT_FOUND")


class EquiposService:
    def __init__(self, mongo: MongoPort, neo4j: Neo4jPort) -> None:
        self.mongo = mongo
        self.neo4j = neo4j

    async def get_equipo(self, codigo: str) -> Equipo:
        """CU1: `equipos.findOne({_id: codigo}, proyección)`; 404 si no existe."""
        equipo = await self.mongo.get_equipo(codigo)
        if equipo is None:
            raise _equipo_inexistente(codigo)
        return equipo

    async def list_jugadores(self, codigo: str, posicion: str | None, limit: int,
                             cursor: str | None) -> PaginaJugadores:
        """CU2: plantel ordenado por dorsal, paginado por keyset sobre el dorsal.

        1. El cursor se valida ANTES de tocar Mongo (400 INVALID_CURSOR).
        2. Se verifica que el equipo exista: un código inexistente es 404
           TEAM_NOT_FOUND, no una lista vacía ambigua (CU2).
        3. Se piden `limit + 1` filas: si vuelve la fila extra hay otra página,
           y el `nextCursor` es el dorsal de la última fila efectivamente devuelta.
        """
        despues = cursor_entero.decodificar(TIPO_CURSOR, cursor)
        if await self.mongo.get_equipo(codigo) is None:
            raise _equipo_inexistente(codigo)
        filas = await self.mongo.list_jugadores(codigo, posicion, despues, limit + 1)
        items = filas[:limit]
        siguiente = (cursor_entero.codificar(TIPO_CURSOR, items[-1].dorsal)
                     if len(filas) > limit else None)
        return PaginaJugadores(equipoCodigo=codigo, items=items, limit=limit, nextCursor=siguiente)

    async def list_partidos(self, codigo: str, limit: int) -> PartidosDeEquipo:
        """CU3: recorrido (:Equipo)-[:PARTICIPA_EN]->(:Partido); 404 si el :Equipo no está."""
        partidos = await self.neo4j.list_partidos_de_equipo(codigo, limit)
        if partidos is None:
            raise _equipo_inexistente(codigo)
        return PartidosDeEquipo(equipoCodigo=codigo, items=partidos, limit=limit)
