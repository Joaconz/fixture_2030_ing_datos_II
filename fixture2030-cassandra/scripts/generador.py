"""
Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)
ARCHIVO: scripts/generador.py
PROPÓSITO: generador DETERMINISTA de comentarios sintéticos, compartido por
           la muestra (generar_muestra.py) y la carga masiva (carga_masiva.py).

DETERMINISMO (RNF7 — idempotencia)
----------------------------------
Todo valor sale de random.Random(semilla) y de fórmulas sobre índices. No se usa
uuid4(), time.time() ni datetime.now(). Consecuencia: el mismo comentario tiene
siempre la misma clave primaria completa, así que volver a cargar hace UPSERT
sobre las mismas filas y no duplica nada. Es la misma estrategia que el Hito 4
(bulkWrite + upsert) y el Hito 5 (MERGE por clave natural).

COHERENCIA CON EL HITO 5 (Neo4j)
--------------------------------
Los 112 partidos, sus identificadores y sus fechas replican EXACTAMENTE las
fórmulas de fixture2030-neo4j/queries/carga.cypher (pasos 6 y 13):
  - Grupos: 'PAR-{A..P}-{1..6}', 2030-06-09T13:00Z + días/horas por jornada.
  - Dieciseisavos: 'PAR-D16-01..16', 2030-06-29T16:00Z + días/horas por índice.
La relación entre módulos es semántica (por partido_id), no por código.
"""
from __future__ import annotations

import random
import zlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator

UTC = timezone.utc
GRUPOS = "ABCDEFGHIJKLMNOP"

# ---------------------------------------------------------------------------
# Parámetros del modelo (documentados en docs/decisiones_de_particionamiento.md)
# ---------------------------------------------------------------------------
VENTANA_MINUTOS = 10                 # ancho de la ventana temporal de partición
FILAS_OBJETIVO_POR_PARTICION = 20_000  # techo de diseño por partición (~7 MB)
MINUTO_DESDE = -15                   # los comentarios arrancan 15' antes del inicio
MINUTO_HASTA = 125                   # y terminan 125' después (90 + ET + post)
ESTADOS = [("PUBLICADO", 93), ("PENDIENTE", 4), ("OCULTO", 2), ("ELIMINADO", 1)]
IDIOMAS = [("es", 55), ("pt", 15), ("en", 15), ("fr", 8), ("ar", 7)]
HINCHADAS = [("LOCAL", 45), ("VISITANTE", 40), ("NEUTRAL", 15)]
USUARIOS_TOTALES = 250_000

# Audiencia y volumen de la carga masiva (1.050.000 comentarios en total)
#   MAXIMA : 1 partido  x 300.000  = 300.000
#   ALTA   : 15 partidos x 20.000  = 300.000
#   NORMAL : 96 partidos x ~4.687  = 450.000
VOLUMEN_POR_AUDIENCIA = {"MAXIMA": 300_000, "ALTA": 20_000}
TOTAL_NORMAL = 450_000

FRASES = [
    "Vamos {eq}! Hoy se gana", "Qué golazo, no lo puedo creer", "Árbitro, era penal clarísimo",
    "Esa defensa está dormida", "Cambio ya, el 9 no la toca", "Partidazo, se viene la remontada",
    "Qué atajada del arquero!!", "Tarjeta roja, se va a las duchas", "Con esta hinchada no se puede perder",
    "El VAR está mirando, esperemos", "Faltan 5 minutos, aguanten", "Se nos escapa el partido",
    "Joga bonito, que time", "What a save!", "Allez les bleus", "Increíble lo de este partido",
    "Tiki taka puro", "Primer tiempo aburrido, a ver el segundo", "Ese pase fue de otro planeta",
    "Nos vemos en la próxima ronda",
]
EQUIPO_GENERICO = ["campeón", "equipo", "selección", "muchachos"]


@dataclass(frozen=True)
class Partido:
    partido_id: str
    fase: str
    inicio: datetime
    audiencia: str   # NORMAL | ALTA | MAXIMA
    buckets: int


def _elegir(rng: random.Random, pares: list[tuple[str, int]]) -> str:
    valores, pesos = zip(*pares)
    return rng.choices(valores, weights=pesos, k=1)[0]


def calcular_buckets(volumen_partido: int) -> int:
    """Regla de diseño: buckets = potencia de 2 >= pico_por_ventana / techo.

    Se estima que la ventana más cargada concentra el 20% del volumen del partido
    (goles + minutos finales). Ver decisiones_de_particionamiento.md §3.
    """
    pico = volumen_partido * 0.20
    necesarios = max(1, -(-int(pico) // FILAS_OBJETIVO_POR_PARTICION))  # ceil
    b = 1
    while b < necesarios:
        b *= 2
    return b


def partidos() -> list[Partido]:
    """Los 112 partidos del Hito 5, con fecha idéntica a carga.cypher."""
    lista: list[Partido] = []
    base_grupos = datetime(2030, 6, 9, 13, 0, tzinfo=UTC)
    for orden, g in enumerate(GRUPOS, start=1):
        for k in range(6):
            jornada = k // 2 + 1
            inicio = base_grupos + timedelta(days=(jornada - 1) * 5 + (orden - 1) % 4,
                                             hours=((orden - 1) // 4) * 3)
            lista.append(Partido(f"PAR-{g}-{k + 1}", "GRUPOS", inicio, "NORMAL", 1))
    base_d16 = datetime(2030, 6, 29, 16, 0, tzinfo=UTC)
    for i in range(16):
        inicio = base_d16 + timedelta(days=i // 4, hours=(i % 4) * 3)
        pid = f"PAR-D16-{i + 1:02d}"
        audiencia = "MAXIMA" if i == 0 else "ALTA"
        lista.append(Partido(pid, "DIECISEISAVOS", inicio, audiencia, 1))

    # buckets según volumen esperado (se fija ANTES del partido, ver decisiones §4)
    final = []
    for p in lista:
        vol = volumen_partido(p)
        final.append(Partido(p.partido_id, p.fase, p.inicio, p.audiencia, calcular_buckets(vol)))
    return final


def volumen_partido(p: Partido) -> int:
    if p.audiencia in VOLUMEN_POR_AUDIENCIA:
        return VOLUMEN_POR_AUDIENCIA[p.audiencia]
    # 450.000 repartidos en 96 partidos normales (los primeros reciben el resto)
    idx = int(p.partido_id.split("-")[2]) - 1 + GRUPOS.index(p.partido_id.split("-")[1]) * 6
    base, resto = divmod(TOTAL_NORMAL, 96)
    return base + (1 if idx < resto else 0)


def ventana_de(instante: datetime) -> datetime:
    """Piso del instante a múltiplo de VENTANA_MINUTOS (clave de partición)."""
    minuto = (instante.minute // VENTANA_MINUTOS) * VENTANA_MINUTOS
    return instante.replace(minute=minuto, second=0, microsecond=0)


def bucket_de(comentario_id: str, buckets: int) -> int:
    """Bucket estable: crc32 del id. Igual en cualquier proceso y máquina."""
    return zlib.crc32(comentario_id.encode("utf-8")) % buckets


def _pesos_por_minuto(rng: random.Random) -> tuple[list[int], list[float], list[int]]:
    """Curva de actividad del partido: base + picos en goles + cierre del partido."""
    minutos = list(range(MINUTO_DESDE, MINUTO_HASTA))
    goles = sorted(rng.sample(range(5, 95), k=rng.randint(1, 5)))
    pesos = []
    for m in minutos:
        w = 1.0
        if m < 0:
            w = 0.6                       # previa
        elif 45 <= m < 60:
            w = 0.5                       # entretiempo
        elif 85 <= m <= 100:
            w = 3.0                       # final del partido
        elif m > 100:
            w = 0.8                       # post-partido
        for g in goles:
            if 0 <= m - g <= 3:
                w += 6.0 * (1 - (m - g) / 4)   # explosión tras el gol
        pesos.append(w)
    return minutos, pesos, goles


def comentarios_de_partido(p: Partido, cantidad: int | None = None) -> Iterator[dict]:
    """Genera los comentarios de un partido, de forma determinista."""
    n = volumen_partido(p) if cantidad is None else cantidad
    rng = random.Random(f"fixture2030-{p.partido_id}")
    minutos, pesos, _ = _pesos_por_minuto(rng)
    elegidos = sorted(rng.choices(minutos, weights=pesos, k=n))
    ids_previos: list[str] = []
    for seq, minuto in enumerate(elegidos, start=1):
        segundo = rng.randint(0, 59)
        milis = rng.randint(0, 999)
        creado = p.inicio + timedelta(minutes=minuto, seconds=segundo, milliseconds=milis)
        cid = f"{p.partido_id}-C{seq:07d}"
        u = int(USUARIOS_TOTALES * (rng.random() ** 1.5)) + 1  # sesgo moderado: pocos usuarios muy activos
        responde = rng.choice(ids_previos[-200:]) if ids_previos and rng.random() < 0.10 else None
        estado = _elegir(rng, ESTADOS)
        frase = rng.choice(FRASES).format(eq=rng.choice(EQUIPO_GENERICO))
        yield {
            "partido_id": p.partido_id,
            "ventana": ventana_de(creado),
            "bucket": bucket_de(cid, p.buckets),
            "creado_en": creado,
            "comentario_id": cid,
            "usuario_id": f"USR-{u:07d}",
            "alias_usuario": f"hincha_{u}",
            "hinchada": _elegir(rng, HINCHADAS),
            "minuto_partido": max(0, minuto),
            "contenido": frase,
            "idioma": _elegir(rng, IDIOMAS),
            "estado_moderacion": estado,
            "motivo_moderacion": None if estado in ("PUBLICADO", "PENDIENTE") else "LENGUAJE_OFENSIVO",
            "responde_a": responde,
            "mes": creado.strftime("%Y-%m"),
        }
        ids_previos.append(cid)


def estadisticas_particiones(filas: Counter) -> dict:
    """Resumen de filas por partición (evidencia de distribución)."""
    tam = sorted(filas.values())
    if not tam:
        return {}
    def pct(q: float) -> int:
        return tam[min(len(tam) - 1, int(q * (len(tam) - 1)))]
    return {
        "particiones": len(tam),
        "min": tam[0],
        "p50": pct(0.50),
        "p90": pct(0.90),
        "p99": pct(0.99),
        "max": tam[-1],
    }
