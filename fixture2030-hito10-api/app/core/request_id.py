"""Identificador de request (RF18) y log de acceso (RNF10).

Si el cliente manda `X-Request-Id` con un formato seguro se respeta (permite
correlacionar desde Postman o el front); si no, se genera uno. El mismo valor
viaja en la respuesta, en el cuerpo de los errores y en cada línea de log del
servicio y de los adaptadores.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Request-Id"
_PATRON = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_request_id: ContextVar[str] = ContextVar("request_id", default="-")

log = logging.getLogger("fixture2030.acceso")


def get_request_id() -> str:
    return _request_id.get()


def nuevo_request_id() -> str:
    return "req-" + uuid.uuid4().hex[:16]


class RequestIdMiddleware:
    """Middleware ASGI puro (no BaseHTTPMiddleware) para no romper el contextvar."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        recibido = None
        for k, v in scope.get("headers", []):
            if k.decode("latin-1").lower() == HEADER.lower():
                recibido = v.decode("latin-1")
                break
        rid = recibido if recibido and _PATRON.match(recibido) else nuevo_request_id()
        token = _request_id.set(rid)
        inicio = time.perf_counter()
        estado: dict[str, int] = {"status": 500}

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                estado["status"] = message["status"]
                estado["enviado"] = 1
                headers = list(message.get("headers", []))
                headers.append((HEADER.encode("latin-1"), rid.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as exc:  # noqa: BLE001 — último recurso: 500 seguro con request-id
            log.error("error inesperado", exc_info=exc,
                      extra={"evento": "error_inesperado", "tipo": type(exc).__name__})
            if estado.get("enviado"):
                raise
            from app.core.errors import respuesta_error_interno
            await respuesta_error_interno()(scope, receive, _send)
        finally:
            ruta = scope.get("route")
            log.info(
                "request",
                extra={
                    "evento": "request",
                    "metodo": scope.get("method"),
                    # plantilla de la ruta (sin valores) cuando existe, para agrupar
                    "ruta": getattr(ruta, "path", None) or scope.get("path"),
                    "path": scope.get("path"),
                    "status": estado["status"],
                    "duracion_ms": round((time.perf_counter() - inicio) * 1000, 1),
                },
            )
            _request_id.reset(token)
