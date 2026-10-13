"""CU8–CU9 (Cassandra) con FakeCassandra: paginación por partición y alta idempotente."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.adapters import cassandra as ad
from app.schemas.comentarios import Comentario
from app.services import comentarios as svc
from tests.unit.conftest import FuenteCaida, FuenteNoTocar
from tests.unit.fakes_cassandra_redis import INICIO, FakeCassandra

UTC = timezone.utc
PID = "PAR-A-1"
CLAVE = "clave-idem-0001"


def _recorrer(client, partido_id=PID, limit=7, max_paginas=500):
    vistos, cursor, paginas = [], None, 0
    while True:
        params = {"limit": limit} | ({"cursor": cursor} if cursor else {})
        r = client.get(f"/partidos/{partido_id}/comentarios", params=params)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["items"]) <= limit
        vistos += body["items"]
        cursor = body["nextCursor"]
        paginas += 1
        assert paginas < max_paginas
        if cursor is None:
            return vistos, paginas
        assert len(cursor) <= 200


def _orden(c: dict) -> tuple:
    return (-datetime.fromisoformat(c["creadoEn"]).timestamp(), c["comentarioId"])


# --------------------------------------------------------------------------- CU8
@pytest.mark.parametrize("buckets", [1, 4])
@pytest.mark.parametrize("limit", [1, 7, 50])
def test_paginacion_completa_sin_repetidos_ni_saltos(make_client, buckets, limit):
    fake = FakeCassandra()
    fake.agregar_partido(PID, buckets=buckets)
    sembrados = fake.sembrar(PID, 230, mismo_instante_cada=5)   # incluye empates de creado_en
    vistos, _ = _recorrer(make_client(cassandra=fake), limit=limit)

    ids = [c["comentarioId"] for c in vistos]
    assert len(ids) == len(set(ids)), "hay repetidos"
    assert set(ids) == {c.comentarioId for c in sembrados}, "faltan comentarios"
    assert vistos == sorted(vistos, key=_orden), "el orden global no es descendente"
    assert len({datetime.fromisoformat(c["creadoEn"]).replace(second=0, microsecond=0, minute=0)
                for c in vistos}) > 1   # abarcó varias horas → varias ventanas


def test_solo_se_devuelven_publicados(make_client):
    fake = FakeCassandra()
    fake.agregar_partido(PID, buckets=4)
    estados = ["PUBLICADO", "PENDIENTE", "PUBLICADO", "OCULTO", "ELIMINADO", "PUBLICADO"]
    sembrados = fake.sembrar(PID, 120, estados=estados)
    vistos, _ = _recorrer(make_client(cassandra=fake), limit=10)
    assert {c["estadoModeracion"] for c in vistos} == {"PUBLICADO"}
    assert {c["comentarioId"] for c in vistos} == {
        c.comentarioId for c in sembrados if c.estadoModeracion == "PUBLICADO"}
    assert vistos == sorted(vistos, key=_orden)


def test_primera_pagina_trae_lo_mas_reciente(make_client):
    fake = FakeCassandra()
    fake.agregar_partido(PID, buckets=4)
    sembrados = fake.sembrar(PID, 60)
    r = make_client(cassandra=fake).get(f"/partidos/{PID}/comentarios", params={"limit": 5})
    esperados = sorted(sembrados, key=svc.clave_orden)[:5]
    assert [c["comentarioId"] for c in r.json()["items"]] == [c.comentarioId for c in esperados]
    assert r.json()["nextCursor"]


def test_partido_sin_comentarios_200_vacio_y_lecturas_acotadas(make_client):
    fake = FakeCassandra()
    fake.agregar_partido(PID, buckets=4)
    r = make_client(cassandra=fake).get(f"/partidos/{PID}/comentarios")
    assert r.status_code == 200
    assert r.json() == {"partidoId": PID, "items": [], "limit": 20, "nextCursor": None}
    # 15 ventanas × 4 buckets como máximo: nunca un scan
    assert fake.lecturas_particion == len(svc.ventanas_del_partido(fake.configs[PID])) * 4 <= 64


def test_partido_sin_q0_da_404(make_client):
    r = make_client(cassandra=FakeCassandra()).get("/partidos/PAR-Z-9/comentarios")
    assert r.status_code == 404 and r.json()["code"] == "MATCH_NOT_FOUND"


@pytest.mark.parametrize("cursor", ["nobase64json", "W10", base64.urlsafe_b64encode(b'[1,"x",1,null,null]').decode().rstrip("=")])
def test_cursor_invalido_da_400(make_client, cursor):
    fake = FakeCassandra()
    fake.agregar_partido(PID)
    r = make_client(cassandra=fake).get(f"/partidos/{PID}/comentarios", params={"cursor": cursor})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_CURSOR"


def test_cursor_de_otro_partido_da_400(make_client):
    fake = FakeCassandra()
    fake.agregar_partido(PID)
    fake.agregar_partido("PAR-A-2")
    fake.sembrar(PID, 30)
    c = make_client(cassandra=fake)
    cursor = c.get(f"/partidos/{PID}/comentarios", params={"limit": 2}).json()["nextCursor"]
    r = c.get("/partidos/PAR-A-2/comentarios", params={"cursor": cursor})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_CURSOR"


def test_cursor_con_ventana_fuera_del_partido_da_400(make_client):
    fake = FakeCassandra()
    cfg = fake.agregar_partido(PID)
    fuera = svc.codificar_cursor(PID, cfg.inicio + timedelta(days=1), None)
    r = make_client(cassandra=fake).get(f"/partidos/{PID}/comentarios", params={"cursor": fuera})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_CURSOR"


def test_listar_con_cassandra_caida_da_503(make_client):
    r = make_client(cassandra=FuenteCaida("cassandra")).get(f"/partidos/{PID}/comentarios")
    assert r.status_code == 503 and r.json()["code"] == "DEPENDENCY_UNAVAILABLE"


def test_limit_fuera_de_rango_400_sin_tocar_la_fuente(make_client):
    r = make_client(cassandra=FuenteNoTocar("cassandra")).get(f"/partidos/{PID}/comentarios", params={"limit": 51})
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------- CU9
def _cuerpo(**cambios):
    base = {"usuarioId": "USR-0000042", "alias": "hincha42", "contenido": "¡Qué golazo!",
            "creadoEn": "2030-06-09T13:47:00.123456Z", "hinchada": "LOCAL", "minutoPartido": 47}
    return base | cambios


def test_publicar_y_reintento_idempotente(make_client):
    fake = FakeCassandra()
    fake.agregar_partido(PID, buckets=4)
    c = make_client(cassandra=fake)
    r1 = c.post(f"/partidos/{PID}/comentarios", json=_cuerpo(), headers={"Idempotency-Key": CLAVE})
    assert r1.status_code == 201, r1.text
    body = r1.json()
    assert body["comentarioId"].startswith(f"{PID}-API-") and len(body["comentarioId"]) == len(PID) + 5 + 16
    assert body["estadoModeracion"] == "PUBLICADO"
    assert body["creadoEn"].startswith("2030-06-09T13:47:00.123")   # truncado a ms
    assert "Idempotent-Replayed" not in r1.headers

    r2 = c.post(f"/partidos/{PID}/comentarios", json=_cuerpo(), headers={"Idempotency-Key": CLAVE})
    assert r2.status_code == 200
    assert r2.headers["Idempotent-Replayed"] == "true"
    assert r2.json() == body
    assert fake.total_filas() == 1 and fake.inserciones == 1
    assert sum(len(p) for p in fake.por_usuario.values()) == 1

    # el comentario nuevo aparece en la lectura
    items = c.get(f"/partidos/{PID}/comentarios").json()["items"]
    assert [i["comentarioId"] for i in items] == [body["comentarioId"]]


def test_misma_clave_otro_usuario_es_otro_comentario(make_client):
    fake = FakeCassandra()
    fake.agregar_partido(PID)
    c = make_client(cassandra=fake)
    a = c.post(f"/partidos/{PID}/comentarios", json=_cuerpo(), headers={"Idempotency-Key": CLAVE})
    b = c.post(f"/partidos/{PID}/comentarios", json=_cuerpo(usuarioId="USR-0000043"),
               headers={"Idempotency-Key": CLAVE})
    assert a.status_code == b.status_code == 201
    assert a.json()["comentarioId"] != b.json()["comentarioId"]


@pytest.mark.parametrize("creado", ["2030-06-09T12:44:59.999Z", "2030-06-09T15:05:00Z", "2030-06-10T13:47:00Z"])
def test_creado_fuera_del_tramo_400_sin_escribir(make_client, creado):
    fake = FakeCassandra()
    fake.agregar_partido(PID)
    r = make_client(cassandra=fake).post(f"/partidos/{PID}/comentarios", json=_cuerpo(creadoEn=creado),
                                         headers={"Idempotency-Key": CLAVE})
    assert r.status_code == 400 and r.json()["code"] == "COMMENT_OUTSIDE_MATCH_WINDOW"
    assert fake.total_filas() == 0


@pytest.mark.parametrize("creado", ["2030-06-09T12:45:00Z", "2030-06-09T15:04:59.999Z"])
def test_bordes_del_tramo_se_aceptan(make_client, creado):
    fake = FakeCassandra()
    fake.agregar_partido(PID)
    r = make_client(cassandra=fake).post(f"/partidos/{PID}/comentarios", json=_cuerpo(creadoEn=creado),
                                         headers={"Idempotency-Key": CLAVE})
    assert r.status_code == 201


def test_publicar_sin_q0_da_404(make_client):
    r = make_client(cassandra=FakeCassandra()).post(f"/partidos/{PID}/comentarios", json=_cuerpo(),
                                                    headers={"Idempotency-Key": CLAVE})
    assert r.status_code == 404 and r.json()["code"] == "MATCH_NOT_FOUND"


@pytest.mark.parametrize("cuerpo,headers", [
    (_cuerpo(usuarioId="juan"), {"Idempotency-Key": CLAVE}),
    (_cuerpo(contenido=""), {"Idempotency-Key": CLAVE}),
    (_cuerpo(creadoEn="2030-06-09T13:47:00"), {"Idempotency-Key": CLAVE}),   # sin zona horaria
    (_cuerpo(campoExtra=1), {"Idempotency-Key": CLAVE}),
    (_cuerpo(), {}),                                                         # sin Idempotency-Key
    (_cuerpo(), {"Idempotency-Key": "corta"}),
])
def test_cuerpo_invalido_400_sin_tocar_la_fuente(make_client, cuerpo, headers):
    r = make_client(cassandra=FuenteNoTocar("cassandra")).post(
        f"/partidos/{PID}/comentarios", json=cuerpo, headers=headers)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_publicar_con_cassandra_caida_da_503(make_client):
    r = make_client(cassandra=FuenteCaida("cassandra")).post(
        f"/partidos/{PID}/comentarios", json=_cuerpo(), headers={"Idempotency-Key": CLAVE})
    assert r.status_code == 503


# --------------------------------------------------------------------------- utilidades puras
def test_ventanas_del_partido_cubren_el_tramo():
    cfg = FakeCassandra().agregar_partido(PID)   # inicio 13:00, ventanas de 10′
    v = svc.ventanas_del_partido(cfg)
    assert v[0] == INICIO + timedelta(minutes=120) and v[-1] == INICIO - timedelta(minutes=20)
    assert len(v) == 15 and v == sorted(v, reverse=True)


def test_piso_y_bucket_igual_que_el_hito6():
    import zlib
    t = datetime(2030, 6, 9, 13, 47, 31, 123000, tzinfo=UTC)
    assert svc.piso_ventana(t, 10) == datetime(2030, 6, 9, 13, 40, tzinfo=UTC)
    assert svc.bucket_de("PAR-A-1-C0000001", 4) == zlib.crc32(b"PAR-A-1-C0000001") % 4


def test_cursor_ida_y_vuelta_y_corto():
    cfg = FakeCassandra().agregar_partido("PAR-D16-01")
    ventanas = svc.ventanas_del_partido(cfg)
    pos = svc.PosicionLectura(ventanas[3] + timedelta(seconds=5, milliseconds=7), "PAR-D16-01-API-0123456789abcdef")
    cur = svc.codificar_cursor("PAR-D16-01", ventanas[3], pos)
    assert len(cur) <= 200 and "=" not in cur
    assert svc.decodificar_cursor(cur, "PAR-D16-01", cfg, ventanas) == (3, pos)
    assert json.loads(base64.urlsafe_b64decode(cur + "==")) [0] == 1


# --------------------------------------------------------------------------- mapeos del adaptador
def test_mapeo_fila_a_comentario_hace_tz_aware():
    fila = {"partido_id": PID, "comentario_id": "PAR-A-1-C0000001", "usuario_id": "USR-0000001",
            "alias_usuario": "hincha_1", "hinchada": "LOCAL", "minuto_partido": 3, "responde_a": None,
            "contenido": "hola", "idioma": "es", "estado_moderacion": "PUBLICADO",
            "creado_en": datetime(2030, 6, 9, 13, 3, 1, 500000), "ventana": None, "bucket": 0}
    c = ad.fila_a_comentario(fila)
    assert c.creadoEn == datetime(2030, 6, 9, 13, 3, 1, 500000, tzinfo=UTC)
    assert c.alias == "hincha_1" and c.respondeA is None


def test_valores_insert_omiten_none_y_usan_utc_naive():
    c = Comentario(comentarioId="X-API-1", partidoId=PID, usuarioId="USR-0000001", alias="a",
                   contenido="hola", creadoEn=datetime(2030, 6, 9, 10, 3, tzinfo=timezone(timedelta(hours=-3))),
                   estadoModeracion="PUBLICADO")
    v = ad.valores_insert_partido(c, INICIO, 2)
    assert v[3] == datetime(2030, 6, 9, 13, 3) and v[3].tzinfo is None
    assert v[7] is ad.UNSET_VALUE and v[8] is ad.UNSET_VALUE and v[9] is ad.UNSET_VALUE
    u = ad.valores_insert_usuario(c, INICIO, 2)
    assert u[1] == "2030-06" and u[7] is ad.UNSET_VALUE


def test_adaptador_cassandra_connect_no_toca_la_red():
    import asyncio

    from app.config.settings import Settings
    a = ad.CassandraAdapter(Settings(cassandra_hosts="203.0.113.1"))
    asyncio.run(a.connect())
    assert a._session is None and a._cluster is None
