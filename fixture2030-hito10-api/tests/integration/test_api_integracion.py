"""Integración extremo a extremo: API real ↔ cinco fuentes reales (RF15, RF17, §5.12).

Cada caso verifica el contrato HTTP y, cuando aplica, contrasta el resultado
con el cliente nativo de la fuente. El orden de las pruebas del flujo de
cierre importa (pytest respeta el orden del archivo).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.integration.conftest import (NEO4J_PASSWORD, assert_error, cql, cypher, mongo_eval,
                                        redis_cli)

pytestmark = pytest.mark.integration
RAIZ = Path(__file__).resolve().parents[2]
DEMO = "PAR-DEMO-API"


@pytest.fixture(scope="module", autouse=True)
def preparar_datos_de_demo():
    """Deja PAR-DEMO-API en PROGRAMADO y recarga las sesiones de muestra (TTL 30 min)."""
    seed = (RAIZ / "scripts" / "sembrar_demo_neo4j.cypher").read_bytes()
    subprocess.run(["docker", "exec", "-i", "fixture2030-neo4j", "cypher-shell", "-u", "neo4j",
                    "-p", NEO4J_PASSWORD], input=seed, check=True, capture_output=True, timeout=60)
    subprocess.run(["docker", "exec", "fixture2030-redis", "sh", "/scripts/carga_muestra.sh"],
                   check=True, capture_output=True, timeout=120)
    redis_cli("DEL", f"f30:cache:partido:{DEMO}", "f30:cache:partido:PAR-A-1")


# ------------------------------------------------------------------ salud
def test_health_dependencias_todas_up(api):
    r = api.get("/health/dependencias")
    assert r.status_code == 200, r.text
    estados = {d["nombre"]: d["estado"] for d in r.json()["dependencias"]}
    assert estados == dict.fromkeys(["mongodb", "neo4j", "cassandra", "redis", "influxdb"], "UP")


# ------------------------------------------------------------------ MongoDB
def test_equipo_coincide_con_mongosh(api):
    r = api.get("/equipos/ARG")
    assert r.status_code == 200
    nombre_nativo = mongo_eval('print(db.equipos.findOne({_id:"ARG"}).nombre)')
    assert r.json()["codigo"] == "ARG" and r.json()["nombre"] == nombre_nativo


def test_equipo_inexistente_404(api):
    assert_error(api.get("/equipos/ZZZ"), 404, "TEAM_NOT_FOUND")


def test_equipo_codigo_invalido_400(api):
    assert_error(api.get("/equipos/arg1"), 400, "VALIDATION_ERROR")


def test_plantel_paginado_completo_sin_repetidos(api):
    dnis, cursor = [], None
    while True:
        params = {"limit": 5} | ({"cursor": cursor} if cursor else {})
        r = api.get("/equipos/ARG/jugadores", params=params)
        assert r.status_code == 200
        dnis += [j["dni"] for j in r.json()["items"]]
        cursor = r.json()["nextCursor"]
        if not cursor:
            break
    total = int(mongo_eval('print(db.jugadores.countDocuments({equipoId:"ARG"}))'))
    assert len(dnis) == len(set(dnis)) == total


def test_plantel_limite_fuera_de_rango_400(api):
    assert_error(api.get("/equipos/ARG/jugadores", params={"limit": 500}), 400)


# ------------------------------------------------------------------ Neo4j lecturas
def test_partidos_de_equipo(api):
    r = api.get("/equipos/ARG/partidos")
    assert r.status_code == 200
    nativo = cypher("MATCH (:Equipo {equipoId:'ARG'})-[:PARTICIPA_EN]->(p:Partido) RETURN count(p)")
    assert len(r.json()["items"]) == min(int(nativo[0]), 10)


def test_detalle_partido_miss_luego_hit(api):
    r1 = api.get("/partidos/PAR-A-1")
    r2 = api.get("/partidos/PAR-A-1")
    assert r1.status_code == r2.status_code == 200
    assert r1.headers["X-Cache"] == "MISS" and r2.headers["X-Cache"] == "HIT"
    assert r1.json() == r2.json()
    assert int(redis_cli("TTL", "f30:cache:partido:PAR-A-1")) <= 60


def test_eventos_coinciden_con_cypher(api):
    r = api.get("/partidos/PAR-A-1/eventos", params={"limit": 200})
    assert r.status_code == 200
    secuencias = [e["secuencia"] for e in r.json()["items"]]
    nativo = cypher("MATCH (e:Evento)-[:OCURRE_EN]->(:Partido {partidoId:'PAR-A-1'}) RETURN count(e)")
    assert secuencias == sorted(secuencias) and len(secuencias) == int(nativo[0])


def test_eventos_partido_sin_eventos_200_vacio(api):
    r = api.get("/partidos/PAR-D16-01/eventos")
    assert r.status_code == 200 and r.json()["items"] == []


def test_eventos_partido_inexistente_404(api):
    assert_error(api.get("/partidos/PAR-X-99/eventos"), 404, "MATCH_NOT_FOUND")


def test_eventos_tipo_invalido_400(api):
    assert_error(api.get("/partidos/PAR-A-1/eventos", params={"tipo": "GOLAZO"}), 400)


# ------------------------------------------------------------------ Neo4j escrituras: flujo de cierre
def test_flujo_de_cierre_completo(api, idem_key):
    gol = {"tipo": "GOL", "minuto": 70, "condicionEquipo": "VISITANTE", "dorsalProtagonista": 9}
    r = api.post(f"/partidos/{DEMO}/eventos", json=gol, headers={"Idempotency-Key": idem_key})
    assert r.status_code == 201, r.text
    evento_id = r.json()["eventoId"]

    # Reintento: misma clave → 200, mismo evento, sin duplicar (verificado en el grafo)
    r = api.post(f"/partidos/{DEMO}/eventos", json=gol, headers={"Idempotency-Key": idem_key})
    assert r.status_code == 200 and r.headers.get("Idempotent-Replayed") == "true"
    assert r.json()["eventoId"] == evento_id
    assert cypher(f"MATCH (e:Evento {{eventoId:'{evento_id}'}}) RETURN count(e)") == ["1"]

    # Misma clave con otro cuerpo → 409
    otro = gol | {"minuto": 71}
    assert_error(api.post(f"/partidos/{DEMO}/eventos", json=otro, headers={"Idempotency-Key": idem_key}),
                 409, "IDEMPOTENCY_KEY_REUSED")

    # Regla del tipo GOL violada → 400, sin escribir
    assert_error(api.post(f"/partidos/{DEMO}/eventos", json={"tipo": "GOL", "minuto": 72},
                          headers={"Idempotency-Key": idem_key + "x"}), 400, "EVENT_RULE_VIOLATION")

    # Cierre sin FIN_PARTIDO → 409
    assert_error(api.patch(f"/partidos/{DEMO}/estado", json={"estado": "FINALIZADO"}),
                 409, "MISSING_FIN_PARTIDO")

    api.get(f"/partidos/{DEMO}")  # deja el detalle en caché para comprobar la invalidación
    fin = {"tipo": "FIN_PARTIDO", "minuto": 90}
    r = api.post(f"/partidos/{DEMO}/eventos", json=fin, headers={"Idempotency-Key": idem_key + "fin"})
    assert r.status_code == 201, r.text
    assert redis_cli("EXISTS", f"f30:cache:partido:{DEMO}") == "0"

    r = api.patch(f"/partidos/{DEMO}/estado", json={"estado": "FINALIZADO"})
    assert r.status_code == 200, r.text
    body = r.json()
    goles = cypher(f"MATCH (e:Evento {{tipo:'GOL'}})-[:OCURRE_EN]->(:Partido {{partidoId:'{DEMO}'}}) "
                   "RETURN e.condicionEquipo AS c, count(*) AS n ORDER BY c")
    por_lado = {l.split(",")[0].strip('" '): int(l.split(",")[1]) for l in goles}
    assert body["estado"] == "FINALIZADO"
    assert body["marcador"] == {"golesLocal": por_lado.get("LOCAL", 0),
                                "golesVisitante": por_lado.get("VISITANTE", 0)}

    # Repetir el cierre → 409 documentado; evento en partido FINALIZADO → 409
    assert_error(api.patch(f"/partidos/{DEMO}/estado", json={"estado": "FINALIZADO"}),
                 409, "INVALID_TRANSITION")
    assert_error(api.post(f"/partidos/{DEMO}/eventos", json=gol | {"minuto": 89},
                          headers={"Idempotency-Key": idem_key + "post"}), 409, "MATCH_FINALIZED")


def test_cierre_partido_inexistente_404(api):
    assert_error(api.patch("/partidos/PAR-X-99/estado", json={"estado": "FINALIZADO"}), 404, "MATCH_NOT_FOUND")


def test_cierre_estado_no_permitido_400(api):
    assert_error(api.patch(f"/partidos/{DEMO}/estado", json={"estado": "EN_JUEGO"}), 400, "VALIDATION_ERROR")


def test_alta_sin_idempotency_key_400(api):
    assert_error(api.post(f"/partidos/{DEMO}/eventos", json={"tipo": "PASE", "minuto": 3}), 400)


# ------------------------------------------------------------------ Cassandra
def _todos_los_comentarios(api, partido: str) -> list[dict]:
    items, cursor = [], None
    for _ in range(100):
        params = {"limit": 7} | ({"cursor": cursor} if cursor else {})
        r = api.get(f"/partidos/{partido}/comentarios", params=params)
        assert r.status_code == 200, r.text
        items += r.json()["items"]
        cursor = r.json()["nextCursor"]
        if not cursor:
            return items
    raise AssertionError("la paginación no terminó")


@pytest.mark.parametrize("partido", ["PAR-A-1", "PAR-D16-01"])  # 1 bucket y 4 buckets
def test_comentarios_paginacion_completa_y_ordenada(api, partido):
    items = _todos_los_comentarios(api, partido)
    ids = [c["comentarioId"] for c in items]
    assert len(ids) == len(set(ids))
    fechas = [c["creadoEn"] for c in items]
    assert fechas == sorted(fechas, reverse=True)
    salida = cql("SELECT comentario_id, estado_moderacion FROM fixture2030_comentarios.comentarios_por_usuario;")
    publicados = {l.split("|")[0].strip() for l in salida.splitlines()
                  if l.strip().startswith(partido + "-") and "PUBLICADO" in l}
    assert set(ids) >= publicados - {i for i in publicados if "-API-" in i}


def test_comentarios_partido_inexistente_404(api):
    assert_error(api.get("/partidos/PAR-X-99/comentarios"), 404, "MATCH_NOT_FOUND")


def test_comentarios_cursor_invalido_400(api):
    assert_error(api.get("/partidos/PAR-A-1/comentarios", params={"cursor": "no-es-un-cursor"}), 400)


def test_publicar_comentario_idempotente(api, idem_key):
    body = {"usuarioId": "USR-0000042", "alias": "hincha42", "contenido": "Prueba de integración",
            "creadoEn": "2030-06-09T13:47:00Z", "minutoPartido": 47, "hinchada": "LOCAL"}
    r1 = api.post("/partidos/PAR-A-1/comentarios", json=body, headers={"Idempotency-Key": idem_key})
    r2 = api.post("/partidos/PAR-A-1/comentarios", json=body, headers={"Idempotency-Key": idem_key})
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 200 and r2.headers.get("Idempotent-Replayed") == "true"
    cid = r1.json()["comentarioId"]
    filas = cql("SELECT count(*) FROM fixture2030_comentarios.comentarios_por_usuario "
                f"WHERE usuario_id='USR-0000042' AND mes='2030-06' AND comentario_id='{cid}' ALLOW FILTERING;")
    assert filas.split()[2] == "1"


def test_publicar_comentario_fuera_del_tramo_400(api, idem_key):
    body = {"usuarioId": "USR-0000042", "alias": "x", "contenido": "tarde",
            "creadoEn": "2030-06-10T13:00:00Z"}
    assert_error(api.post("/partidos/PAR-A-1/comentarios", json=body, headers={"Idempotency-Key": idem_key}),
                 400, "COMMENT_OUTSIDE_MATCH_WINDOW")


def test_publicar_comentario_sin_zona_horaria_400(api, idem_key):
    body = {"usuarioId": "USR-0000042", "alias": "x", "contenido": "y", "creadoEn": "2030-06-09T13:47:00"}
    assert_error(api.post("/partidos/PAR-A-1/comentarios", json=body, headers={"Idempotency-Key": idem_key}), 400)


# ------------------------------------------------------------------ Redis
def test_sesion_coincide_con_redis_cli(api):
    r = api.get("/sesiones/demo-ses-0000001-1")
    assert r.status_code == 200, r.text
    assert r.json()["usuarioId"] == redis_cli("HGET", "f30:ses:demo-ses-0000001-1", "usuario_id")
    assert "solicitudes" not in r.json()


def test_sesion_no_renueva_ttl(api):
    redis_cli("EXPIRE", "f30:ses:demo-ses-0000003-1", "500")
    api.get("/sesiones/demo-ses-0000003-1")
    assert int(redis_cli("TTL", "f30:ses:demo-ses-0000003-1")) <= 500


def test_sesion_inexistente_404(api):
    assert_error(api.get("/sesiones/no-existe-123"), 404, "SESSION_NOT_FOUND")


def test_sesion_bloqueada_403(api):
    assert_error(api.get("/sesiones/demo-ses-0000033-1"), 403, "SESSION_BLOCKED")


def test_cerrar_sesion_y_repetir(api):
    assert api.delete("/sesiones/demo-ses-0000002-1").status_code == 204
    assert redis_cli("EXISTS", "f30:ses:demo-ses-0000002-1") == "0"
    assert redis_cli("SISMEMBER", "f30:usr:USR-0000002:sesiones", "demo-ses-0000002-1") == "0"
    assert_error(api.delete("/sesiones/demo-ses-0000002-1"), 404, "SESSION_NOT_FOUND")


# ------------------------------------------------------------------ InfluxDB
def test_estadisticas_raw_y_agregadas(api):
    ventana = {"desde": "2030-06-09T13:00:00Z", "hasta": "2030-06-09T13:30:00Z"}
    raw = api.get("/partidos/PAR-A-1/estadisticas", params=ventana | {"agregacion": "raw", "limit": 100})
    m1 = api.get("/partidos/PAR-A-1/estadisticas", params=ventana | {"agregacion": "1m"})
    assert raw.status_code == m1.status_code == 200, raw.text
    assert raw.json()["cantidad"] == 100 and raw.json()["truncado"] is True
    assert 0 < m1.json()["cantidad"] <= 2 * 31


def test_estadisticas_ventana_sin_datos_200_vacio(api):
    r = api.get("/partidos/PAR-A-1/estadisticas",
                params={"desde": "2030-01-01T00:00:00Z", "hasta": "2030-01-01T01:00:00Z"})
    assert r.status_code == 200 and r.json()["puntos"] == [] and r.json()["cantidad"] == 0


def test_estadisticas_ventana_invertida_400(api):
    assert_error(api.get("/partidos/PAR-A-1/estadisticas",
                         params={"desde": "2030-06-09T14:00:00Z", "hasta": "2030-06-09T13:00:00Z"}),
                 400, "INVALID_TIME_WINDOW")


def test_estadisticas_ventana_mayor_a_3h_400(api):
    assert_error(api.get("/partidos/PAR-A-1/estadisticas",
                         params={"desde": "2030-06-09T10:00:00Z", "hasta": "2030-06-09T14:00:01Z"}),
                 400, "TIME_WINDOW_TOO_LARGE")
