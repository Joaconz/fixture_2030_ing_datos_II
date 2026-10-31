"""Pruebas de GET /metrics (Hito 13, RF4): métricas de aplicación y de dependencia."""
import asyncio

import pytest
from prometheus_client import REGISTRY

from app.adapters.base import ejecutar
from app.core.errors import DependencyUnavailableError
from tests.unit.conftest import FuenteCaida


def _valor(nombre: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(nombre, labels) or 0.0


def test_metrics_expone_formato_prometheus(make_client):
    r = make_client().get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "fixture2030_http_requests_total" in r.text


def test_metrics_no_esta_en_el_contrato(make_client):
    assert "/metrics" not in make_client().get("/openapi.json").json()["paths"]


def test_request_se_cuenta_por_plantilla_de_ruta(make_client):
    antes = _valor("fixture2030_http_requests_total", metodo="GET", ruta="/health", status="200")
    make_client().get("/health")
    assert _valor("fixture2030_http_requests_total", metodo="GET", ruta="/health", status="200") == antes + 1


def test_503_queda_registrado_con_su_status(make_client):
    ruta = "/equipos/{codigo}"
    antes = _valor("fixture2030_http_requests_total", metodo="GET", ruta=ruta, status="503")
    r = make_client(mongodb=FuenteCaida("mongodb")).get("/equipos/ARG")
    assert r.status_code == 503
    assert _valor("fixture2030_http_requests_total", metodo="GET", ruta=ruta, status="503") == antes + 1


def test_404_sin_ruta_no_abre_una_serie_por_url(make_client):
    antes = _valor("fixture2030_http_requests_total", metodo="GET", ruta="sin_ruta", status="404")
    make_client().get("/no-existe/12345")
    assert _valor("fixture2030_http_requests_total", metodo="GET", ruta="sin_ruta", status="404") == antes + 1
    assert "/no-existe/12345" not in make_client().get("/metrics").text


def test_metrics_no_se_cuenta_a_si_mismo(make_client):
    c = make_client()
    c.get("/metrics")
    assert 'ruta="/metrics"' not in c.get("/metrics").text


def test_ejecutar_registra_la_dependencia_con_su_resultado():
    async def _ok():
        return 1

    async def _caida():
        raise ConnectionError("refused")

    n = "fixture2030_dependencia_duration_seconds_count"
    ok_antes = _valor(n, dependencia="mongodb", operacion="prueba", resultado="ok")
    caida_antes = _valor(n, dependencia="mongodb", operacion="prueba", resultado="no_disponible")

    asyncio.run(ejecutar("mongodb", "prueba", _ok(), timeout_s=1))
    with pytest.raises(DependencyUnavailableError):
        asyncio.run(ejecutar("mongodb", "prueba", _caida(), timeout_s=1,
                             errores_de_disponibilidad=(ConnectionError,)))

    assert _valor(n, dependencia="mongodb", operacion="prueba", resultado="ok") == ok_antes + 1
    assert _valor(n, dependencia="mongodb", operacion="prueba", resultado="no_disponible") == caida_antes + 1
