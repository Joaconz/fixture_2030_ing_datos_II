"""Formato de error único de la API (RF11 / RF12 / RNF4).

Toda respuesta de error tiene la forma
    {"code": "...", "message": "...", "requestId": "...", "details": [...]?}
Los servicios y adaptadores lanzan subclases de `ApiError`; los handlers de
este módulo las traducen a HTTP. Ningún mensaje público incluye URIs,
credenciales, consultas internas ni trazas: el detalle técnico va sólo al log.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import get_request_id

log = logging.getLogger("fixture2030.api")


class ApiError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, code: str | None = None,
                 details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details


class ValidationApiError(ApiError):
    """Entrada inválida detectada por una regla del servicio (no por Pydantic)."""
    status_code = 400
    code = "VALIDATION_ERROR"


class ForbiddenError(ApiError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(ApiError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(ApiError):
    """El estado actual del recurso impide la operación (regla de negocio)."""
    status_code = 409
    code = "CONFLICT"


# Motivos internos de una falla de dependencia (Hito 11, RF17). Van al log y a
# /health/dependencias; la respuesta pública sólo distingue timeout (504) del
# resto (503), sin revelar si fue la credencial o el contexto.
MOTIVOS_DEPENDENCIA = ("timeout", "conexion", "autenticacion", "autorizacion", "contexto",
                       "no_configurado", "rechazo")


class DependencyUnavailableError(ApiError):
    """La fuente no se pudo usar. Nunca 200.

    - `timeout` → 504 `DEPENDENCY_TIMEOUT`: la fuente no contestó dentro del límite.
    - cualquier otro motivo → 503 `DEPENDENCY_UNAVAILABLE`: conexión rechazada,
      credencial o permiso rechazado, contexto (database/keyspace/colección)
      inexistente, configuración faltante o respuesta inválida.
    """
    status_code = 503
    code = "DEPENDENCY_UNAVAILABLE"

    def __init__(self, dependency: str, *, timeout: bool = False, motivo: str | None = None) -> None:
        motivo = motivo or ("timeout" if timeout else "conexion")
        if motivo not in MOTIVOS_DEPENDENCIA:
            motivo = "conexion"
        timeout = motivo == "timeout"
        texto = "no respondió dentro del tiempo límite" if timeout else "no está disponible"
        super().__init__(
            f"La fuente '{dependency}' {texto}. Reintentar más tarde.",
            code="DEPENDENCY_TIMEOUT" if timeout else None,
            details=[{"campo": "dependencia", "problema": dependency}],
        )
        self.status_code = 504 if timeout else 503
        self.dependency = dependency
        self.timeout = timeout
        self.motivo = motivo


def error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message, "requestId": get_request_id()}
    if details:
        body["details"] = details
    return body


def _respuesta(status: int, code: str, message: str,
               details: list[dict[str, Any]] | None = None,
               headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_body(code, message, details), headers=headers)


def _detalles_pydantic(exc: RequestValidationError) -> list[dict[str, Any]]:
    detalles = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body",)]
        detalles.append({"campo": ".".join(loc) or "request", "problema": err.get("msg", "inválido")})
    return detalles


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        if isinstance(exc, DependencyUnavailableError):
            return _respuesta(exc.status_code, exc.code, exc.message, exc.details,
                              headers={"Retry-After": "5"})
        return _respuesta(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI responde 422 por defecto: el contrato de esta API usa 400 para
        # toda entrada inválida, y se rechaza ANTES de tocar cualquier fuente (RNF3).
        return _respuesta(400, "VALIDATION_ERROR", "La request no cumple el contrato.",
                          _detalles_pydantic(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codigos = {404: "ROUTE_NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        mensaje = {404: "La ruta no existe.", 405: "Método no permitido para esta ruta."}
        return _respuesta(exc.status_code, codigos.get(exc.status_code, "HTTP_ERROR"),
                          mensaje.get(exc.status_code, str(exc.detail)))


def respuesta_error_interno() -> JSONResponse:
    """500 seguro; lo emite RequestIdMiddleware para conservar el request-id (RNF9)."""
    return _respuesta(500, "INTERNAL_ERROR", "Error interno. Informar el requestId.")
