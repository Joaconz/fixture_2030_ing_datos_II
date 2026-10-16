"""CU12 — estadísticas en ventana temporal (servicio + ruta, InfluxDB falso)."""
from __future__ import annotations

import pytest

from tests.unit.conftest import FuenteCaida, FuenteNoTocar
from tests.unit.fakes_influx import InfluxFalso, puntos_demo

URL = "/partidos/PAR-A-1/estadisticas"
VENTANA = {"desde": "2030-06-09T13:00:00Z", "hasta": "2030-06-09T13:30:00Z"}


@pytest.mark.parametrize("params,code", [
    ({"desde": "2030-06-09T13:30:00Z", "hasta": "2030-06-09T13:00:00Z"}, "INVALID_TIME_WINDOW"),
    ({"desde": "2030-06-09T13:00:00Z", "hasta": "2030-06-09T13:00:00Z"}, "INVALID_TIME_WINDOW"),
    ({"desde": "2030-06-09T13:00:00Z", "hasta": "2030-06-09T16:00:01Z"}, "TIME_WINDOW_TOO_LARGE"),
    ({"desde": "2030-06-09T13:00:00", "hasta": "2030-06-09T13:30:00Z"}, "VALIDATION_ERROR"),
    ({"desde": "2030-06-09T13:00:00Z"}, "VALIDATION_ERROR"),
    ({**VENTANA, "agregacion": "10m"}, "VALIDATION_ERROR"),
    ({**VENTANA, "equipo": "arg"}, "VALIDATION_ERROR"),
    ({**VENTANA, "limit": 2001}, "VALIDATION_ERROR"),
])
def test_ventana_o_parametros_invalidos_400_sin_tocar_influx(make_client, params, code):
    r = make_client(influxdb=FuenteNoTocar("influxdb")).get(URL, params=params)
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == code
    assert body["requestId"] == r.headers["X-Request-Id"]


def test_ventana_de_exactamente_3h_es_valida(make_client):
    fake = InfluxFalso()
    r = make_client(influxdb=fake).get(URL, params={"desde": "2030-06-09T13:00:00Z",
                                                     "hasta": "2030-06-09T16:00:00Z"})
    assert r.status_code == 200


def test_zona_horaria_distinta_de_utc_se_acepta(make_client):
    fake = InfluxFalso(puntos_demo(4))
    r = make_client(influxdb=fake).get(URL, params={"desde": "2030-06-09T10:00:00-03:00",
                                                     "hasta": "2030-06-09T10:30:00-03:00",
                                                     "agregacion": "raw"})
    assert r.status_code == 200 and r.json()["cantidad"] == 4


def test_sin_datos_200_lista_vacia(make_client):
    r = make_client(influxdb=InfluxFalso()).get(URL, params={**VENTANA, "agregacion": "raw"})
    assert r.status_code == 200
    body = r.json()
    assert body["puntos"] == [] and body["cantidad"] == 0 and body["truncado"] is False
    assert body["partidoId"] == "PAR-A-1" and body["agregacion"] == "raw"


def test_pide_limit_mas_uno_y_marca_truncado(make_client):
    fake = InfluxFalso(puntos_demo(20))
    r = make_client(influxdb=fake).get(URL, params={**VENTANA, "agregacion": "raw", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert fake.llamadas[0]["limite"] == 6
    assert body["cantidad"] == 5 and len(body["puntos"]) == 5 and body["truncado"] is True
    assert body["puntos"][0]["equipoCodigo"] == "ARG"


def test_no_truncado_cuando_entra_justo(make_client):
    fake = InfluxFalso(puntos_demo(5))
    body = make_client(influxdb=fake).get(URL, params={**VENTANA, "agregacion": "raw", "limit": 5}).json()
    assert body["cantidad"] == 5 and body["truncado"] is False


def test_filtro_equipo_y_agregacion_llegan_al_adaptador(make_client):
    fake = InfluxFalso(puntos_demo(10))
    r = make_client(influxdb=fake).get(URL, params={**VENTANA, "equipo": "VEN", "agregacion": "5m"})
    assert r.status_code == 200
    assert fake.llamadas[0]["equipo"] == "VEN" and fake.llamadas[0]["agregacion"] == "5m"
    assert all(p["equipoCodigo"] == "VEN" for p in r.json()["puntos"])


def test_influx_caido_503_nunca_vacio(make_client):
    r = make_client(influxdb=FuenteCaida("influxdb")).get(URL, params=VENTANA)
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "DEPENDENCY_UNAVAILABLE" and "puntos" not in body
    assert r.headers["Retry-After"] == "5"
