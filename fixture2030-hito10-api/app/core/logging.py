"""Logs estructurados en JSON (RNF10).

Cada línea incluye `request_id`. Las líneas de dependencia agregan
`dependencia`, `operacion`, `resultado` y `duracion_ms`. Nunca se registran
cuerpos de request, valores de sesión, tokens ni URIs con credenciales (RNF7).
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.request_id import get_request_id

_CAMPOS_EXTRA = (
    "evento", "metodo", "ruta", "path", "status", "duracion_ms",
    "dependencia", "operacion", "resultado", "motivo", "tipo", "cache",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "request_id": get_request_id(),
            "mensaje": record.getMessage(),
        }
        for campo in _CAMPOS_EXTRA:
            if hasattr(record, campo):
                data[campo] = getattr(record, campo)
        if record.exc_info and record.exc_info[0] is not None:
            # Sólo el tipo y el mensaje de la excepción: la traza completa puede
            # contener URIs o parámetros; queda en DEBUG.
            data["excepcion"] = f"{record.exc_info[0].__name__}: {record.exc_info[1]}"
        return json.dumps(data, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    raiz = logging.getLogger("fixture2030")
    raiz.handlers = [handler]
    raiz.setLevel(level.upper())
    raiz.propagate = False
    # Los drivers son muy verbosos y algunos loguean hosts: sólo advertencias.
    for ruidoso in ("cassandra", "neo4j", "pymongo", "httpx", "httpcore"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True  # reemplazado por el log de acceso propio
