"""CU5–CU7 (timeline, alta de evento, cierre) y mapeo del adaptador Neo4j."""
from datetime import datetime, timezone

import pytest
from neo4j.time import DateTime as Neo4jDateTime

from app.adapters.neo4j import (Neo4jAdapter, detalle_desde_registro, evento_desde_registro,
                                partido_de_equipo_desde_mapa)
from app.config.settings import Settings
from app.core.errors import DependencyUnavailableError
from app.schemas.eventos import EventoNuevo
from app.services import cursor_entero
from app.services.eventos import REGLAS, derivar_evento_id, huella_del_cuerpo
from tests.unit.conftest import FuenteCaida, FuenteNoTocar
from tests.unit.fakes_mongo_neo4j import FakeNeo4j, FakeRedisCache

DEMO = "/partidos/PAR-DEMO-API"


def _cliente(make_client, neo4j=None, redis=None):
    return make_client(neo4j=neo4j or FakeNeo4j(), redis=redis or FakeRedisCache())


def _post(c, cuerpo, clave="clave-demo-0001", partido=DEMO):
    return c.post(f"{partido}/eventos", json=cuerpo, headers={"Idempotency-Key": clave})


GOL_VISITANTE = {"tipo": "GOL", "minuto": 40, "condicionEquipo": "VISITANTE", "dorsalProtagonista": 9}
FIN = {"tipo": "FIN_PARTIDO", "minuto": 90}


# --------------------------------------------------------------------------- CU5 timeline
def test_timeline_en_orden_de_secuencia(make_client):
    body = _cliente(make_client).get("/partidos/PAR-A-1/eventos").json()
    assert [e["secuencia"] for e in body["items"]] == list(range(1, 14))
    assert body["items"][0]["tipo"] == "INICIO_PARTIDO" and body["nextCursor"] is None


def test_timeline_filtrado_por_tipo(make_client):
    body = _cliente(make_client).get("/partidos/PAR-A-1/eventos?tipo=GOL").json()
    assert [e["tipo"] for e in body["items"]] == ["GOL", "GOL"]


def test_partido_sin_eventos_da_200_vacio_y_inexistente_404(make_client):
    c = _cliente(make_client)
    vacio = c.get("/partidos/PAR-D16-01/eventos")
    assert vacio.status_code == 200 and vacio.json()["items"] == []
    falta = c.get("/partidos/PAR-X-9/eventos")
    assert falta.status_code == 404 and falta.json()["code"] == "MATCH_NOT_FOUND"


def test_timeline_paginacion_completa_sin_repetidos(make_client):
    c = _cliente(make_client)
    vistos, cursor = [], None
    while True:
        body = c.get("/partidos/PAR-A-1/eventos?limit=4" + (f"&cursor={cursor}" if cursor else "")).json()
        vistos += [e["eventoId"] for e in body["items"]]
        cursor = body["nextCursor"]
        if not cursor:
            break
    assert len(vistos) == 13 == len(set(vistos))


@pytest.mark.parametrize("query", ["tipo=OFFSIDE", "limit=0", "limit=201", "cursor=%24%24"])
def test_timeline_entrada_invalida_400_sin_tocar_neo4j(make_client, query):
    r = make_client(neo4j=FuenteNoTocar("neo4j")).get(f"/partidos/PAR-A-1/eventos?{query}")
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_timeline_cursor_de_otro_listado_400(make_client):
    cursor = cursor_entero.codificar("jug", 3)
    r = make_client(neo4j=FuenteNoTocar("neo4j")).get(f"/partidos/PAR-A-1/eventos?cursor={cursor}")
    assert r.status_code == 400 and r.json()["code"] == "INVALID_CURSOR"


def test_partido_id_invalido_400_sin_tocar_neo4j(make_client):
    r = make_client(neo4j=FuenteNoTocar("neo4j")).get("/partidos/par-a-1/eventos")
    assert r.status_code == 400


def test_timeline_neo4j_caido_503(make_client):
    r = make_client(neo4j=FuenteCaida("neo4j", timeout=True)).get("/partidos/PAR-A-1/eventos")
    assert r.status_code == 503 and r.json()["code"] == "DEPENDENCY_UNAVAILABLE"


# --------------------------------------------------------------------------- CU6 reglas por tipo (N8)
def test_tabla_de_reglas_cubre_el_catalogo():
    from typing import get_args

    from app.schemas.eventos import TipoEvento
    assert set(REGLAS) == set(get_args(TipoEvento))


@pytest.mark.parametrize("cuerpo, campos", [
    ({"tipo": "GOL", "minuto": 10}, {"condicionEquipo", "dorsalProtagonista"}),
    ({"tipo": "TARJETA_ROJA", "minuto": 10, "condicionEquipo": "LOCAL"}, {"dorsalProtagonista"}),
    ({"tipo": "CORNER", "minuto": 10, "dorsalProtagonista": 7}, {"condicionEquipo"}),
    ({"tipo": "INICIO_PARTIDO", "minuto": 0, "condicionEquipo": "LOCAL"}, {"condicionEquipo"}),
    ({"tipo": "INICIO_PARTIDO", "minuto": 3}, {"minuto"}),
    ({"tipo": "FIN_PARTIDO", "minuto": 90, "condicionEquipo": "LOCAL", "dorsalProtagonista": 1},
     {"condicionEquipo", "dorsalProtagonista"}),
])
def test_regla_violada_400_sin_tocar_neo4j(make_client, cuerpo, campos):
    c = make_client(neo4j=FuenteNoTocar("neo4j"), redis=FuenteNoTocar("redis"))
    r = _post(c, cuerpo)
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "EVENT_RULE_VIOLATION"
    assert {d["campo"] for d in body["details"]} == campos


def test_corner_sin_dorsal_es_valido(make_client):
    r = _post(_cliente(make_client), {"tipo": "CORNER", "minuto": 20, "condicionEquipo": "LOCAL"})
    assert r.status_code == 201 and r.json()["dorsalProtagonista"] is None


@pytest.mark.parametrize("cuerpo", [{"tipo": "OFFSIDE", "minuto": 1}, {"tipo": "GOL", "minuto": 131},
                                    {"tipo": "GOL", "minuto": 1, "extra": True}])
def test_cuerpo_fuera_de_contrato_400(make_client, cuerpo):
    r = _post(make_client(neo4j=FuenteNoTocar("neo4j")), cuerpo)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_sin_idempotency_key_400(make_client):
    r = make_client(neo4j=FuenteNoTocar("neo4j")).post(f"{DEMO}/eventos", json=FIN)
    assert r.status_code == 400


# --------------------------------------------------------------------------- CU6 alta e idempotencia
def test_alta_201_y_replay_200_sin_duplicar(make_client):
    neo, redis = FakeNeo4j(), FakeRedisCache()
    c = _cliente(make_client, neo, redis)
    r1 = _post(c, GOL_VISITANTE)
    assert r1.status_code == 201 and "Idempotent-Replayed" not in r1.headers
    ev = r1.json()
    assert ev["secuencia"] == 4 and ev["origen"] == "API"
    assert ev["eventoId"] == derivar_evento_id("PAR-DEMO-API", "clave-demo-0001")
    assert redis.borradas == ["PAR-DEMO-API"]

    r2 = _post(c, GOL_VISITANTE)
    assert r2.status_code == 200 and r2.headers["Idempotent-Replayed"] == "true"
    assert r2.json() == ev
    assert len(neo.partidos["PAR-DEMO-API"].eventos) == 4
    assert redis.borradas == ["PAR-DEMO-API"]       # el replay no vuelve a invalidar


def test_misma_clave_otro_cuerpo_409(make_client):
    c = _cliente(make_client)
    assert _post(c, GOL_VISITANTE).status_code == 201
    r = _post(c, {**GOL_VISITANTE, "minuto": 41})
    assert r.status_code == 409 and r.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_huella_canonica_null_igual_a_ausente():
    a = EventoNuevo(tipo="FIN_PARTIDO", minuto=90)
    b = EventoNuevo.model_validate({"minuto": 90, "condicionEquipo": None, "tipo": "FIN_PARTIDO"})
    assert huella_del_cuerpo(a) == huella_del_cuerpo(b)
    assert huella_del_cuerpo(a) != huella_del_cuerpo(EventoNuevo(tipo="FIN_PARTIDO", minuto=91))


def test_alta_en_partido_inexistente_404(make_client):
    r = _post(_cliente(make_client), FIN, partido="/partidos/PAR-X-9")
    assert r.status_code == 404 and r.json()["code"] == "MATCH_NOT_FOUND"


@pytest.mark.parametrize("partido, cuerpo, code", [
    ("/partidos/PAR-A-1", GOL_VISITANTE, "MATCH_FINALIZED"),
    (DEMO, {"tipo": "INICIO_PARTIDO", "minuto": 0}, "DUPLICATE_UNIQUE_EVENT"),
])
def test_conflictos_de_estado_409(make_client, partido, cuerpo, code):
    r = _post(_cliente(make_client), cuerpo, partido=partido)
    assert r.status_code == 409 and r.json()["code"] == code


def test_evento_despues_de_fin_409(make_client):
    c = _cliente(make_client)
    assert _post(c, FIN, clave="clave-fin-0001").status_code == 201
    r = _post(c, GOL_VISITANTE, clave="clave-gol-0002")
    assert r.status_code == 409 and r.json()["code"] == "EVENT_AFTER_FIN"


def test_tipo_fuera_del_catalogo_del_grafo_409(make_client):
    neo = FakeNeo4j()
    neo.catalogo.discard("ATAJADA")
    r = _post(_cliente(make_client, neo), {"tipo": "ATAJADA", "minuto": 5, "condicionEquipo": "LOCAL",
                                          "dorsalProtagonista": 1})
    assert r.status_code == 409 and r.json()["code"] == "EVENT_TYPE_NOT_IN_CATALOG"


def test_alta_con_neo4j_caido_503(make_client):
    r = _post(make_client(neo4j=FuenteCaida("neo4j"), redis=FakeRedisCache()), FIN)
    assert r.status_code == 503


def test_alta_con_redis_caido_no_falla(make_client):
    r = _post(_cliente(make_client, redis=FakeRedisCache(caida=True)), FIN)
    assert r.status_code == 201


# --------------------------------------------------------------------------- CU7 cierre
def test_flujo_completo_de_demo(make_client):
    neo, redis = FakeNeo4j(), FakeRedisCache()
    c = _cliente(make_client, neo, redis)
    cerrar = lambda: c.patch(f"{DEMO}/estado", json={"estado": "FINALIZADO"})  # noqa: E731

    assert _post(c, GOL_VISITANTE, clave="clave-k1-000001").status_code == 201
    assert _post(c, GOL_VISITANTE, clave="clave-k1-000001").status_code == 200
    r = cerrar()
    assert r.status_code == 409 and r.json()["code"] == "MISSING_FIN_PARTIDO"
    assert _post(c, FIN, clave="clave-k2-000002").status_code == 201
    r = cerrar()
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "FINALIZADO" and body["marcador"] == {"golesLocal": 1, "golesVisitante": 1}
    assert body["cantidadEventos"] == 5
    r = cerrar()
    assert r.status_code == 409 and r.json()["code"] == "INVALID_TRANSITION"
    r = _post(c, {"tipo": "PASE", "minuto": 91, "condicionEquipo": "LOCAL", "dorsalProtagonista": 4},
              clave="clave-k3-000003")
    assert r.status_code == 409 and r.json()["code"] == "MATCH_FINALIZED"
    # replay de una clave vieja después del cierre: sigue siendo 200
    assert _post(c, FIN, clave="clave-k2-000002").status_code == 200
    assert redis.borradas.count("PAR-DEMO-API") == 3   # alta K1, alta K2, cierre


def test_cerrar_inexistente_404(make_client):
    r = _cliente(make_client).patch("/partidos/PAR-X-9/estado", json={"estado": "FINALIZADO"})
    assert r.status_code == 404 and r.json()["code"] == "MATCH_NOT_FOUND"


@pytest.mark.parametrize("cuerpo", [{"estado": "PROGRAMADO"}, {}, {"estado": "FINALIZADO", "golesLocal": 3}])
def test_cerrar_cuerpo_invalido_400_sin_tocar_neo4j(make_client, cuerpo):
    r = make_client(neo4j=FuenteNoTocar("neo4j")).patch(f"{DEMO}/estado", json=cuerpo)
    assert r.status_code == 400


def test_cerrar_con_redis_caido_responde_200(make_client):
    neo = FakeNeo4j()
    c = _cliente(make_client, neo, FakeRedisCache(caida=True))
    _post(c, FIN)
    r = c.patch(f"{DEMO}/estado", json={"estado": "FINALIZADO"})
    assert r.status_code == 200 and r.json()["marcador"] == {"golesLocal": 1, "golesVisitante": 0}


def test_cerrar_con_neo4j_caido_503(make_client):
    r = make_client(neo4j=FuenteCaida("neo4j"), redis=FakeRedisCache()).patch(
        f"{DEMO}/estado", json={"estado": "FINALIZADO"})
    assert r.status_code == 503


# --------------------------------------------------------------------------- adaptador Neo4j (sin Docker)
_TS = Neo4jDateTime(2030, 6, 9, 13, 13, 0, tzinfo=timezone.utc)


def test_mapeo_evento_convierte_datetime_y_origen():
    ev = evento_desde_registro(
        {"eventoId": "PAR-A-1-EV-05", "partidoId": "PAR-A-1", "secuencia": 5, "tipo": "GOL",
         "minuto": 13, "condicionEquipo": "LOCAL", "dorsalProtagonista": 9, "timestamp": _TS,
         "origen": None},
        {"dni": "30000146", "nombre": "Lucas", "apellido": "Silva"})
    assert isinstance(ev.timestamp, datetime) and ev.timestamp == datetime(2030, 6, 9, 13, 13, tzinfo=timezone.utc)
    assert ev.origen == "CARGA" and ev.protagonista.apellido == "Silva"
    api = evento_desde_registro({"eventoId": "x", "partidoId": "PAR-A-1", "secuencia": 1,
                                 "tipo": "FIN_PARTIDO", "minuto": 90, "origen": "API"}, None)
    assert api.origen == "API" and api.protagonista is None and api.timestamp is None


def _registro_detalle(estado):
    return {"partido": {"partidoId": "PAR-D16-01", "fase": "DIECISEISAVOS", "grupo": None,
                        "jornada": 4, "fechaHora": _TS, "estado": estado},
            "local": {"equipoId": "ARG", "nombre": "Argentina"},
            "visitante": {"equipoId": "BRA", "nombre": "Brasil"},
            "sede": {"sedeId": "URU-CEN", "nombre": "Estadio Centenario", "ciudad": "Montevideo",
                     "pais": "Uruguay", "region": "AMERICAS"},
            "cantidadEventos": 0, "golesLocal": 2, "golesVisitante": 1}


def test_mapeo_detalle_marcador_solo_si_finalizado():
    assert detalle_desde_registro(_registro_detalle("PROGRAMADO")).marcador is None
    fin = detalle_desde_registro(_registro_detalle("FINALIZADO"))
    assert fin.marcador.golesLocal == 2 and fin.local.equipoCodigo == "ARG"
    assert fin.sede.region == "AMERICAS" and isinstance(fin.fechaHora, datetime)


def test_mapeo_partido_de_equipo():
    p = partido_de_equipo_desde_mapa({"partidoId": "PAR-D16-01", "fase": "DIECISEISAVOS", "grupo": None,
                                      "fechaHora": _TS, "estado": "PROGRAMADO", "condicion": "LOCAL",
                                      "rivalCodigo": "BRA", "golesLocal": None, "golesVisitante": None})
    assert p.rivalCodigo == "BRA" and p.golesLocal is None


def test_cypher_del_adaptador_es_parametrizado():
    import app.adapters.neo4j as modulo
    consultas = [v for k, v in vars(modulo).items() if k.startswith("CYPHER_")]
    assert consultas and all("{partido_id}" not in q and "%s" not in q for q in consultas)
    assert "$partidoId" in modulo.CYPHER_CREAR_EVENTO and "$tipo" in modulo.CYPHER_EVENTOS


async def test_adaptador_neo4j_arranca_sin_neo4j_y_responde_503():
    a = Neo4jAdapter(Settings(neo4j_uri="bolt://127.0.0.1:1", neo4j_password="x", dep_timeout_s=0.5))
    await a.connect()                      # perezoso: no conecta
    with pytest.raises(DependencyUnavailableError):
        await a.get_partido("PAR-A-1")
    await a.close()
