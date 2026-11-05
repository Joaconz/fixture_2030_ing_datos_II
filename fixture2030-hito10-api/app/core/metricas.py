"""Métricas Prometheus de la API (Hito 13, RF4).

Dos familias, para poder separar dónde se va el tiempo:
  - de APLICACIÓN (`fixture2030_http_*`): cada request HTTP, medida en el
    middleware de request-id con la plantilla de la ruta (no el path con
    valores, para no crear una serie por partido o por usuario);
  - de DEPENDENCIA (`fixture2030_dependencia_*`): cada llamada de un
    adaptador a su base, medida en `adapters.base.ejecutar`.
Si la latencia HTTP sube y la de la dependencia no, el problema está en la
API; si suben las dos, en la base.

Se exponen en GET /metrics (fuera del contrato OpenAPI). No guardan
parámetros ni resultados: solo método, ruta, status, dependencia,
operación y resultado (RNF6 del Hito 13).
"""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

# Buckets en segundos: de 5 ms a 5 s (el timeout por defecto de cada fuente está en ese rango).
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

HTTP_REQUESTS = Counter(
    "fixture2030_http_requests_total",
    "Requests HTTP atendidas por la API, por método, plantilla de ruta y status",
    ["metodo", "ruta", "status"],
)
HTTP_DURACION = Histogram(
    "fixture2030_http_request_duration_seconds",
    "Duración de cada request HTTP medida en la API (incluye las dependencias)",
    ["metodo", "ruta"],
    buckets=_BUCKETS,
)
DEPENDENCIA_DURACION = Histogram(
    "fixture2030_dependencia_duration_seconds",
    "Duración de cada llamada de un adaptador a su base, por resultado",
    ["dependencia", "operacion", "resultado"],
    buckets=_BUCKETS,
)

RUTA_METRICAS = "/metrics"
# Paths sin ruta que coincida (404): se agrupan para no abrir una serie por URL.
SIN_RUTA = "sin_ruta"


def registrar_request(metodo: str, ruta: str, status: int, duracion_s: float) -> None:
    if ruta == RUTA_METRICAS:
        return
    HTTP_REQUESTS.labels(metodo, ruta, str(status)).inc()
    HTTP_DURACION.labels(metodo, ruta).observe(duracion_s)


def registrar_dependencia(dependencia: str, operacion: str, resultado: str, duracion_s: float) -> None:
    DEPENDENCIA_DURACION.labels(dependencia, operacion, resultado).observe(duracion_s)


async def metricas(_: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
