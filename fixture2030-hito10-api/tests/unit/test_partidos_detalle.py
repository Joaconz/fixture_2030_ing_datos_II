"""CU4 — detalle de partido con cache-aside (Neo4j + Redis falsos)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.errors import DependencyUnavailableError
from app.schemas.partidos import EquipoEnPartido, PartidoDetalle, Sede
from tests.unit.conftest import FuenteCaida

URL = "/partidos/PAR-A-1"


def detalle_demo() -> PartidoDetalle:
    return PartidoDetalle(
        partidoId="PAR-A-1", fase="GRUPOS", grupo="A", jornada=1,
        fechaHora=datetime(2030, 6, 9, 13, 0, tzinfo=timezone.utc), estado="PROGRAMADO",
        sede=Sede(sedeId="URU-CEN", nombre="Estadio Centenario", ciudad="Montevideo",
                  pais="Uruguay", region="AMERICAS"),
        local=EquipoEnPartido(equipoCodigo="ARG", nombre="Argentina"),
        visitante=EquipoEnPartido(equipoCodigo="SRB", nombre="Serbia"),
        marcador=None, cantidadEventos=2)


class Neo4jFalso:
    def __init__(self, partidos: dict[str, PartidoDetalle] | None = None) -> None:
        self.partidos = partidos if partidos is not None else {"PAR-A-1": detalle_demo()}
        self.lecturas = 0

    async def get_partido(self, partido_id):
        self.lecturas += 1
        return self.partidos.get(partido_id)


class RedisCacheFalso:
    def __init__(self, set_falla: bool = False) -> None:
        self.datos: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.set_falla = set_falla

    async def cache_get_partido(self, partido_id):
        return self.datos.get(partido_id)

    async def cache_set_partido(self, partido_id, valor_json, ttl_s):
        if self.set_falla:
            raise DependencyUnavailableError("redis")
        self.datos[partido_id] = valor_json
        self.ttls[partido_id] = ttl_s


def test_miss_y_despues_hit_con_mismo_cuerpo(make_client):
    neo, redis = Neo4jFalso(), RedisCacheFalso()
    c = make_client(neo4j=neo, redis=redis)
    r1 = c.get(URL)
    assert r1.status_code == 200 and r1.headers["X-Cache"] == "MISS"
    assert redis.ttls["PAR-A-1"] == 60
    r2 = c.get(URL)
    assert r2.status_code == 200 and r2.headers["X-Cache"] == "HIT"
    assert r1.json() == r2.json()
    assert neo.lecturas == 1


def test_redis_caido_bypass_desde_neo4j(make_client):
    c = make_client(neo4j=Neo4jFalso(), redis=FuenteCaida("redis"))
    r = c.get(URL)
    assert r.status_code == 200 and r.headers["X-Cache"] == "BYPASS"
    assert r.json()["partidoId"] == "PAR-A-1"


def test_set_de_cache_falla_bypass_sin_fallar(make_client):
    r = make_client(neo4j=Neo4jFalso(), redis=RedisCacheFalso(set_falla=True)).get(URL)
    assert r.status_code == 200 and r.headers["X-Cache"] == "BYPASS"


def test_partido_inexistente_404_y_no_se_cachea(make_client):
    redis = RedisCacheFalso()
    r = make_client(neo4j=Neo4jFalso(), redis=redis).get("/partidos/PAR-X-9")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "MATCH_NOT_FOUND" and body["requestId"] == r.headers["X-Request-Id"]
    assert "X-Cache" not in r.headers
    assert redis.datos == {}


def test_cache_corrupta_es_miss_y_se_sobrescribe(make_client):
    neo, redis = Neo4jFalso(), RedisCacheFalso()
    redis.datos["PAR-A-1"] = '{"partidoId": "PAR-A-1", "roto": tru'
    r = make_client(neo4j=neo, redis=redis).get(URL)
    assert r.status_code == 200 and r.headers["X-Cache"] == "MISS"
    assert neo.lecturas == 1
    assert PartidoDetalle.model_validate_json(redis.datos["PAR-A-1"]).partidoId == "PAR-A-1"


def test_neo4j_caido_sin_cache_503(make_client):
    r = make_client(neo4j=FuenteCaida("neo4j"), redis=RedisCacheFalso()).get(URL)
    assert r.status_code == 503 and r.json()["code"] == "DEPENDENCY_UNAVAILABLE"


def test_con_cache_vigente_no_consulta_neo4j(make_client):
    redis = RedisCacheFalso()
    redis.datos["PAR-A-1"] = detalle_demo().model_dump_json()
    neo = Neo4jFalso()
    r = make_client(neo4j=neo, redis=redis).get(URL)
    assert r.status_code == 200 and r.headers["X-Cache"] == "HIT"
    assert neo.lecturas == 0


def test_ambas_caidas_503(make_client):
    r = make_client(neo4j=FuenteCaida("neo4j"), redis=FuenteCaida("redis")).get(URL)
    assert r.status_code == 503


class Neo4jCaido:
    def __init__(self):
        self.lecturas = 0

    async def get_partido(self, partido_id):
        self.lecturas += 1
        raise DependencyUnavailableError("neo4j")


def test_neo4j_caido_con_cache_vigente_hit(make_client):
    redis = RedisCacheFalso()
    redis.datos["PAR-A-1"] = detalle_demo().model_dump_json()
    neo = Neo4jCaido()
    r = make_client(neo4j=neo, redis=redis).get(URL)
    assert r.status_code == 200 and r.headers["X-Cache"] == "HIT"
    assert neo.lecturas == 0
