"""Cursor opaco para paginar por una clave entera creciente (dorsal, secuencia).

Formato: base64-url (sin relleno) de un JSON mínimo `{"t": <tipo>, "v": <entero>}`.
  - `v` es la última clave devuelta; la página siguiente pide `clave > v`
    (keyset pagination: estable aunque se inserten filas, sin OFFSET).
  - `t` identifica de qué listado salió el cursor, para que un cursor de
    jugadores no se pueda reutilizar en el timeline de eventos (y viceversa).
El cliente no debe interpretarlo: sólo devolverlo tal cual en `cursor`.
Cualquier cursor que no decodifique a esa forma → 400 INVALID_CURSOR, antes de
tocar la fuente (RNF3).
"""
from __future__ import annotations

import base64
import binascii
import json

from app.core.errors import ValidationApiError


def codificar(tipo: str, valor: int) -> str:
    crudo = json.dumps({"t": tipo, "v": valor}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


def decodificar(tipo: str, cursor: str | None) -> int | None:
    """None si no hay cursor (primera página); el entero si es válido; 400 si no."""
    if cursor is None:
        return None
    try:
        relleno = "=" * (-len(cursor.rstrip("=")) % 4)
        datos = json.loads(base64.urlsafe_b64decode(cursor.rstrip("=") + relleno))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        datos = None
    valor = datos.get("v") if isinstance(datos, dict) and datos.get("t") == tipo else None
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
        raise ValidationApiError(
            "El cursor no es válido para este listado. Volver a pedir la primera página.",
            code="INVALID_CURSOR",
            details=[{"campo": "cursor", "problema": "no corresponde a un nextCursor emitido por este listado"}],
        )
    return valor
