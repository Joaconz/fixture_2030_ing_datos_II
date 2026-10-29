"""CU8–CU9: comentarios paginados por partición y alta idempotente (Cassandra).

Modelo del Hito 6 (fixture2030-cassandra/scripts/esquema.cql):
  comentarios_por_partido  PK ((partido_id, ventana, bucket), creado_en, comentario_id)
                           CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC)
  ventana = piso(creado_en) a múltiplo de `ventana_minutos` (10)
  bucket  = crc32(comentario_id) % buckets          (generador.py: bucket_de)
  Q0      = config_particion_partido: buckets, ventana_minutos, inicio

Lectura (Q1/Q3): nunca se recorre el keyspace (RNF12/13). Se parte de Q0, se
calculan las ventanas del tramo del partido (−15′ a +125′ del inicio, el
mismo tramo que usa el generador) y se leen sólo las particiones
(partido_id, ventana, bucket) de esas ventanas, de la más reciente a la más
antigua, con LIMIT por partición y un tope de lecturas por request.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import time
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.settings import get_settings
from app.core.errors import NotFoundError, ValidationApiError
from app.schemas.comentarios import Comentario, ComentarioNuevo, PaginaComentarios
from app.services.ports import CassandraPort, ConfigParticion, PosicionLectura

UTC = timezone.utc
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
UN_MS = timedelta(milliseconds=1)

TRAMO_DESDE = timedelta(minutes=-15)   # generador.py: MINUTO_DESDE
TRAMO_HASTA = timedelta(minutes=125)   # generador.py: MINUTO_HASTA (excluido)
ESTADO_VISIBLE = "PUBLICADO"

# Acotan el trabajo de UNA request (RNF12/13). Si se alcanzan, la página sale
# con menos de `limit` ítems pero con `nextCursor`: el cliente sigue desde ahí.
MAX_LECTURAS_PARTICION = 64            # lecturas de partición por request
MAX_FILAS_EXAMINADAS = 500             # filas leídas (incluye no publicadas)
MAX_FILAS_POR_LECTURA = 100            # LIMIT máximo de cada lectura de partición

CURSOR_VERSION = 1


# --------------------------------------------------------------------------- utilidades puras
def a_ms(instante: datetime) -> int:
    """Milisegundos desde epoch, exactos (sin pasar por float)."""
    return (instante - EPOCH) // UN_MS


def desde_ms(ms: int) -> datetime:
    return EPOCH + ms * UN_MS


def truncar_ms(instante: datetime) -> datetime:
    """Cassandra guarda `timestamp` con precisión de milisegundos: si no se trunca,
    la fila escrita no coincide con la lectura por clave primaria."""
    instante = instante.astimezone(UTC)
    return instante.replace(microsecond=(instante.microsecond // 1000) * 1000)


def piso_ventana(instante: datetime, ventana_minutos: int) -> datetime:
    """Piso a múltiplo de `ventana_minutos` desde epoch (= ventana_de del Hito 6
    para anchos que dividen la hora, como 10)."""
    ancho = timedelta(minutes=ventana_minutos)
    return EPOCH + ((instante.astimezone(UTC) - EPOCH) // ancho) * ancho


def bucket_de(comentario_id: str, buckets: int) -> int:
    """Misma fórmula que generador.py del Hito 6."""
    return zlib.crc32(comentario_id.encode("utf-8")) % buckets


def ventanas_del_partido(cfg: ConfigParticion) -> list[datetime]:
    """Ventanas del tramo [inicio−15′, inicio+125′), de la más reciente a la más antigua."""
    desde = piso_ventana(cfg.inicio + TRAMO_DESDE, cfg.ventana_minutos)
    hasta = piso_ventana(cfg.inicio + TRAMO_HASTA - UN_MS, cfg.ventana_minutos)
    paso = timedelta(minutes=cfg.ventana_minutos)
    ventanas, v = [], hasta
    while v >= desde:
        ventanas.append(v)
        v -= paso
    return ventanas


def clave_orden(c: Comentario) -> tuple[int, str]:
    """Orden de clustering: creado_en DESC, comentario_id ASC."""
    return (-a_ms(c.creadoEn), c.comentarioId)


def clave_posicion(p: PosicionLectura) -> tuple[int, str]:
    return (-a_ms(p.creado_en), p.comentario_id)


def huella_partido(partido_id: str) -> str:
    return f"{zlib.crc32(partido_id.encode('utf-8')):08x}"


# --------------------------------------------------------------------------- cursor
# Diseño: el recorrido es una mezcla de todos los buckets de una ventana en el
# orden TOTAL (creado_en DESC, comentario_id ASC) — comentario_id es único, así
# que no hay empates. En una mezcla ordenada, "todo lo anterior a la última fila
# examinada ya se vio y nada posterior se vio", en CADA bucket a la vez. Por eso
# alcanza con UNA posición por ventana (no una por bucket): cada bucket continúa
# estrictamente después de esa misma (creado_en, comentario_id). Eso mantiene el
# cursor corto con cualquier cantidad de buckets (el contrato lo limita a 200
# caracteres) y no repite ni saltea filas.
#
# Formato: base64-url sin relleno de un JSON compacto
#   [versión, crc32(partido_id) en hex, ventana_ms, creado_en_ms | null, comentario_id | null]
# Posición null = la ventana se empieza desde su fila más reciente.

def codificar_cursor(partido_id: str, ventana: datetime, pos: PosicionLectura | None) -> str:
    datos: list[Any] = [CURSOR_VERSION, huella_partido(partido_id), a_ms(ventana),
                        a_ms(pos.creado_en) if pos else None, pos.comentario_id if pos else None]
    crudo = json.dumps(datos, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(crudo).decode("ascii").rstrip("=")


def _cursor_invalido() -> ValidationApiError:
    return ValidationApiError("El cursor no es válido para este partido.", code="INVALID_CURSOR",
                              details=[{"campo": "cursor", "problema": "cursor inválido o de otro partido"}])


def decodificar_cursor(cursor: str, partido_id: str, cfg: ConfigParticion,
                       ventanas: list[datetime]) -> tuple[int, PosicionLectura | None]:
    """→ (índice de la ventana en `ventanas`, posición dentro de ella)."""
    try:
        crudo = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        datos = json.loads(crudo.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise _cursor_invalido() from exc
    if not (isinstance(datos, list) and len(datos) == 5 and datos[0] == CURSOR_VERSION
            and datos[1] == huella_partido(partido_id)):
        raise _cursor_invalido()
    _, _, v_ms, t_ms, cid = datos
    if not isinstance(v_ms, int) or isinstance(v_ms, bool):
        raise _cursor_invalido()
    ventana = desde_ms(v_ms)
    if ventana not in ventanas:
        raise _cursor_invalido()
    if t_ms is None and cid is None:
        return ventanas.index(ventana), None
    if (not isinstance(t_ms, int) or isinstance(t_ms, bool) or not isinstance(cid, str)
            or not cid or len(cid) > 120):
        raise _cursor_invalido()
    creado = desde_ms(t_ms)
    if not (ventana <= creado < ventana + timedelta(minutes=cfg.ventana_minutos)):
        raise _cursor_invalido()
    return ventanas.index(ventana), PosicionLectura(creado_en=creado, comentario_id=cid)


# --------------------------------------------------------------------------- caché de Q0 (Hito 12)
# La configuración de partición (buckets, ventana, inicio) se fija ANTES del partido (Hito 6)
# y no cambia durante él; sin embargo, el Hito 10 la leía de Cassandra en CADA request
# (GET y POST). Con COMENTARIOS_CONFIG_CACHE_S > 0 se reutiliza en memoria del proceso
# durante esos segundos. Sólo se guardan configuraciones existentes (un 404 no se cachea).
# Es a nivel de módulo porque el servicio se construye en cada request.
_CACHE_CONFIG: dict[str, tuple[float, ConfigParticion]] = {}


# --------------------------------------------------------------------------- servicio
class ComentariosService:
    def __init__(self, cassandra: CassandraPort, config_cache_s: float | None = None) -> None:
        self.cassandra = cassandra
        self.config_cache_s = (get_settings().comentarios_config_cache_s
                               if config_cache_s is None else config_cache_s)

    async def _config(self, partido_id: str) -> ConfigParticion:
        if self.config_cache_s > 0:
            guardado = _CACHE_CONFIG.get(partido_id)
            if guardado and time.monotonic() < guardado[0]:
                return guardado[1]
        cfg = await self.cassandra.get_config(partido_id)
        if cfg is not None and self.config_cache_s > 0:
            _CACHE_CONFIG[partido_id] = (time.monotonic() + self.config_cache_s, cfg)
        if cfg is None:
            raise NotFoundError(f"El partido '{partido_id}' no tiene configuración de comentarios.",
                                code="MATCH_NOT_FOUND")
        return cfg

    async def listar(self, partido_id: str, limit: int, cursor: str | None) -> PaginaComentarios:
        """CU8: comentarios PUBLICADOS, del más reciente al más antiguo.

        Por cada ventana (de la más reciente a la más antigua) se leen sus
        `buckets` particiones en paralelo, empezando estrictamente después de la
        posición actual, y se mezclan por (creado_en DESC, comentario_id ASC).
        Si un bucket devolvió tantas filas como se pidieron, puede tener más: la
        mezcla sólo es segura hasta su última fila (la "frontera"); lo posterior
        se vuelve a pedir en la siguiente vuelta. Agotada la ventana, se sigue
        con la anterior.

        Filtrado de moderación: Cassandra no puede filtrar por `estado_moderacion`
        dentro del rango paginado sin el índice SAI + ALLOW FILTERING, así que se
        filtra en la aplicación (≈93 % de las filas son PUBLICADO) y se lee un
        poco de más para compensar. Las filas no publicadas avanzan el cursor
        igual (nunca se vuelven a leer).

        La última página puede salir vacía con `nextCursor` null si el corte
        anterior coincidió justo con el final de las filas.
        """
        cfg = await self._config(partido_id)
        ventanas = ventanas_del_partido(cfg)
        idx, pos = (decodificar_cursor(cursor, partido_id, cfg, ventanas) if cursor else (0, None))

        items: list[Comentario] = []
        presupuesto = {"lecturas": MAX_LECTURAS_PARTICION, "filas": MAX_FILAS_EXAMINADAS}
        while idx < len(ventanas) and len(items) < limit:
            agotada, pos = await self._leer_ventana(partido_id, cfg, ventanas[idx], pos,
                                                    limit, items, presupuesto)
            if not agotada:
                break           # página completa o presupuesto agotado: seguir aquí
            idx, pos = idx + 1, None

        next_cursor = codificar_cursor(partido_id, ventanas[idx], pos) if idx < len(ventanas) else None
        return PaginaComentarios(partidoId=partido_id, items=items, limit=limit, nextCursor=next_cursor)

    async def _leer_ventana(self, partido_id: str, cfg: ConfigParticion, ventana: datetime,
                            pos: PosicionLectura | None, limit: int, items: list[Comentario],
                            presupuesto: dict[str, int]) -> tuple[bool, PosicionLectura | None]:
        """Agrega a `items` desde `ventana`. → (ventana agotada, última posición examinada)."""
        activos = list(range(cfg.buckets))
        while len(items) < limit:
            ya_leyo = presupuesto["lecturas"] < MAX_LECTURAS_PARTICION   # la 1.ª vuelta siempre se hace
            if ya_leyo and (presupuesto["lecturas"] < len(activos) or presupuesto["filas"] <= 0):
                return False, pos
            falta = limit - len(items)
            pedir = min(falta + falta // 10 + 2, MAX_FILAS_POR_LECTURA)   # sobre-lectura por el filtro
            presupuesto["lecturas"] -= len(activos)
            lotes = await asyncio.gather(*(
                self.cassandra.leer_particion(partido_id, ventana, b, pos, pedir) for b in activos))

            # frontera: la última fila más "temprana" (en orden) entre los buckets truncados
            truncados = [clave_orden(lote[-1]) for lote in lotes if len(lote) >= pedir]
            frontera = min(truncados) if truncados else None
            filas = sorted((c for lote in lotes for c in lote), key=clave_orden)

            consumidas = 0
            for c in filas:
                if frontera is not None and clave_orden(c) > frontera:
                    break
                consumidas += 1
                presupuesto["filas"] -= 1
                pos = PosicionLectura(creado_en=c.creadoEn, comentario_id=c.comentarioId)
                if c.estadoModeracion == ESTADO_VISIBLE:
                    items.append(c)
                    if len(items) == limit:
                        break
            if frontera is None and consumidas == len(filas):
                return True, None            # todos los buckets agotados y todo consumido
            if len(items) == limit:
                return False, pos
            # un bucket que no fue truncado y cuyas filas ya se consumieron está agotado
            p = clave_posicion(pos) if pos else None
            activos = [b for b, lote in zip(activos, lotes)
                       if len(lote) >= pedir or (lote and p is not None and clave_orden(lote[-1]) > p)]
        return False, pos

    async def publicar(self, partido_id: str, idempotency_key: str,
                       nuevo: ComentarioNuevo) -> tuple[Comentario, bool]:
        """CU9 (W1 del Hito 6). Devuelve (comentario, creado). creado=False ⇒ reintento.

        Idempotencia: `comentario_id` se deriva de (usuarioId, Idempotency-Key) y
        `creadoEn` viene en el cuerpo, así que la clave primaria completa
        (partido_id, ventana, bucket, creado_en, comentario_id) es determinista.
        Depende de reenviar LA MISMA request (misma clave + mismo creadoEn): con
        otro creadoEn sería otra fila. Antes de escribir se lee por PK: si existe
        → 200 con la fila guardada. Y como en Cassandra INSERT es upsert, aun la
        carrera de dos reintentos simultáneos (ambos leen "no existe" y ambos
        insertan) termina en UNA sola fila por tabla.
        """
        cfg = await self._config(partido_id)
        creado = truncar_ms(nuevo.creadoEn)
        if not (cfg.inicio + TRAMO_DESDE <= creado < cfg.inicio + TRAMO_HASTA):
            raise ValidationApiError(
                "creadoEn cae fuera del tramo de comentarios del partido (−15′ a +125′ del inicio).",
                code="COMMENT_OUTSIDE_MATCH_WINDOW",
                details=[{"campo": "creadoEn", "problema": "fuera del tramo del partido"}])

        huella = hashlib.sha256(f"{nuevo.usuarioId}:{idempotency_key}".encode("utf-8")).hexdigest()[:16]
        comentario_id = f"{partido_id}-API-{huella}"
        ventana = piso_ventana(creado, cfg.ventana_minutos)
        bucket = bucket_de(comentario_id, cfg.buckets)

        existente = await self.cassandra.get_comentario(partido_id, ventana, bucket, creado, comentario_id)
        if existente is not None:
            return existente, False

        comentario = Comentario(
            comentarioId=comentario_id, partidoId=partido_id, usuarioId=nuevo.usuarioId,
            alias=nuevo.alias, hinchada=nuevo.hinchada, minutoPartido=nuevo.minutoPartido,
            contenido=nuevo.contenido, idioma=nuevo.idioma, creadoEn=creado,
            respondeA=nuevo.respondeA, estadoModeracion=ESTADO_VISIBLE)
        await self.cassandra.insertar_comentario(comentario, ventana, bucket)
        return comentario, True
