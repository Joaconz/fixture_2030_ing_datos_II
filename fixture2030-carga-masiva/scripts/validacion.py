"""
Fixture 2030 — Carga masiva integrada (Hito 11 del PDF del TPO)
ARCHIVO: scripts/validacion.py
PROPÓSITO: VALIDACIÓN DE INTEGRIDAD después de la carga, sobre las 5 bases f30cm-*.
  1. Conteos esperados por base (los volúmenes que pide el PDF).
  2. Duplicados (por clave natural de cada base).
  3. Referencias cruzadas:
     - todo partido_id de Cassandra, Redis e InfluxDB existe en Neo4j (el calendario
       canónico de partidos es el del grafo, `PAR-*`);
     - correspondencia de equipos MongoDB <-> Neo4j. Es el hallazgo abierto H1
       (docs/ESTADO-CANONICO-NECESIDADES.md): acá SOLO se mide, no se corrige.

USO SUELTO (con las bases ya cargadas por el orquestador y sin apagar):
    python scripts/validacion.py
Lo llama orquestador.py al terminar la carga. Cada chequeo queda como
{"chequeo", "esperado", "obtenido", "ok"}; los de H1 son informativos ("medido").
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import ESPERADO, InfluxDB, MongoDB, Redis, cassandra_py, cypher, dexec, influx_por_dia, log  # noqa: E402

RELACIONES_ENUNCIADO = ["PARTICIPA", "ANOTA", "ASISTE", "RECIBE_TARJETA", "REEMPLAZA"]
TABLAS_INFLUX = ["estadisticas_equipo", "audiencia_partido", "operacion_plataforma"]


def chequeo(lista: list, nombre: str, esperado, obtenido, ok=None) -> None:
    lista.append({"chequeo": nombre, "esperado": esperado, "obtenido": obtenido,
                  "ok": (esperado == obtenido) if ok is None else ok})


# ---------------------------------------------------------------------------
# Lecturas por base (las reutiliza distribucion.py)
# ---------------------------------------------------------------------------
def leer_mongodb() -> dict:
    from comun import mongo_json
    return mongo_json(MongoDB.contenedor, """({
      equipos: db.equipos.countDocuments(),
      jugadores: db.jugadores.countDocuments(),
      dni_duplicados: (db.jugadores.aggregate([{$group: {_id: "$dni", n: {$sum: 1}}},
                         {$match: {n: {$gt: 1}}}, {$count: "c"}]).toArray()[0] || {c: 0}).c,
      dorsal_duplicados: (db.jugadores.aggregate([{$group: {_id: {e: "$equipoId", d: "$dorsal"}, n: {$sum: 1}}},
                         {$match: {n: {$gt: 1}}}, {$count: "c"}]).toArray()[0] || {c: 0}).c,
      huerfanos: (db.jugadores.aggregate([{$lookup: {from: "equipos", localField: "equipoId",
                         foreignField: "_id", as: "e"}}, {$match: {e: {$size: 0}}}, {$count: "c"}]).toArray()[0] || {c: 0}).c,
      equipos_lista: db.equipos.find({}, {nombre: 1, confederacion: 1}).sort({_id: 1}).toArray()
    })""")


def leer_neo4j() -> dict:
    r = cypher("""
      CALL () { MATCH (p:Partido) RETURN count(p) AS partidos, count(DISTINCT p.partidoId) AS partidos_distintos }
      CALL () { MATCH (e:Evento) RETURN count(e) AS eventos, count(DISTINCT e.eventoId) AS eventos_distintos }
      CALL () { MATCH (e:Evento) WHERE NOT EXISTS { (e)--(:Partido) } RETURN count(e) AS eventos_sin_partido }
      CALL () { MATCH (q:Equipo) RETURN count(q) AS equipos, count(DISTINCT q.equipoId) AS equipos_distintos }
      CALL () { MATCH (j:Jugador) RETURN count(j) AS jugadores, count(DISTINCT j.dni) AS jugadores_distintos }
      RETURN *""")[0]
    rels = {f["tipo"]: f["n"] for f in cypher("MATCH ()-[r]->() RETURN type(r) AS tipo, count(r) AS n")}
    r["relaciones_enunciado"] = {t: rels.get(t, 0) for t in RELACIONES_ENUNCIADO}
    r["partido_ids"] = [f["id"] for f in cypher("MATCH (p:Partido) RETURN p.partidoId AS id ORDER BY id")]
    r["equipos_lista"] = cypher("MATCH (q:Equipo) RETURN q.equipoId AS id, q.nombre AS nombre ORDER BY id")
    return r


# Recorrido completo de las dos tablas de comentarios con el driver (dentro del contenedor
# cargador, que ya lo tiene instalado). Paginado de a 5.000 filas: no trae todo a memoria
# de una vez, solo los identificadores y contadores.
_CASSANDRA_SCAN = r"""
from collections import Counter
from cassandra.query import SimpleStatement
def pct(v, q):
    return v[min(len(v) - 1, int(q * len(v)))]
filas = 0; ids = set(); por_particion = Counter(); por_partido = Counter()
for r in s.execute(SimpleStatement("SELECT partido_id, ventana, bucket, comentario_id FROM comentarios_por_partido", fetch_size=5000)):
    filas += 1; ids.add(r.comentario_id)
    por_particion[(r.partido_id, r.ventana, r.bucket)] += 1; por_partido[r.partido_id] += 1
filas_u = 0; ids_u = set(); part_u = Counter()
for r in s.execute(SimpleStatement("SELECT usuario_id, mes, comentario_id FROM comentarios_por_usuario", fetch_size=5000)):
    filas_u += 1; ids_u.add(r.comentario_id); part_u[(r.usuario_id, r.mes)] += 1
config = sorted(r.partido_id for r in s.execute("SELECT partido_id FROM config_particion_partido"))
v = sorted(por_particion.values()); vu = sorted(part_u.values())
print(json.dumps({
  "comentarios_por_partido": {"filas": filas, "comentario_id_distintos": len(ids), "particiones": len(v),
      "filas_por_particion": {"min": v[0], "p50": pct(v, .5), "p90": pct(v, .9), "p99": pct(v, .99), "max": v[-1]} if v else {},
      "top_particiones": [[k[0], k[1].isoformat(), k[2], n] for k, n in por_particion.most_common(5)]},
  "comentarios_por_usuario": {"filas": filas_u, "comentario_id_distintos": len(ids_u), "particiones": len(vu),
      "filas_por_particion": {"min": vu[0], "p50": pct(vu, .5), "p90": pct(vu, .9), "p99": pct(vu, .99), "max": vu[-1]} if vu else {}},
  "solo_en_una_vista": len(ids ^ ids_u),
  "filas_por_partido": dict(sorted(por_partido.items())),
  "config_partido_ids": config,
}))
"""
_cache_cassandra: dict | None = None


def leer_cassandra(refrescar: bool = False) -> dict:
    global _cache_cassandra
    if _cache_cassandra is None or refrescar:
        _cache_cassandra = cassandra_py(_CASSANDRA_SCAN)
    return _cache_cassandra


def leer_redis() -> dict:
    def contar(patron: str) -> int:
        return int(dexec(Redis.contenedor, "sh", "-c",
                         f"redis-cli --scan --count 1000 --pattern '{patron}' | wc -l").strip())
    indices = dexec(Redis.contenedor, "redis-cli", "--scan", "--count", "1000",
                    "--pattern", "f30:usr:USR-1??????:sesiones").split()
    # Cada usuario del volumen tiene exactamente una sesión: SCARD por pipeline (no recorre datos)
    scard = dexec(Redis.contenedor, "redis-cli", entrada="".join(f"SCARD {k}\n" for k in indices)).split()
    claves_partido = dexec(Redis.contenedor, "redis-cli", "--scan", "--count", "1000", "--pattern", "*PAR-*").split()
    rankings = dexec(Redis.contenedor, "redis-cli", "--scan", "--pattern", "f30:rank:tendencia:*").split()
    miembros = []
    for k in rankings:
        miembros += dexec(Redis.contenedor, "redis-cli", "ZRANGE", k, "0", "-1").split()
    ids = set(m for m in miembros if m.startswith("PAR-"))
    for k in claves_partido:
        ids.update(p for p in k.split(":") if p.startswith("PAR-"))
    return {
        "usuarios_volumen": len(indices),
        "usuarios_con_sesiones_distinta_de_1": sum(1 for n in scard if n != "1"),
        "sesiones_volumen": contar("f30:ses:vol-ses-*"),
        "perfiles_volumen": contar("f30:cache:usuario:USR-1??????:perfil"),
        "dbsize": int(dexec(Redis.contenedor, "redis-cli", "DBSIZE").strip()),
        "claves_con_partido": claves_partido,
        "rankings_tendencia": rankings,
        "partido_ids": sorted(ids),
    }


def leer_influxdb() -> dict:
    manifiesto = json.loads(InfluxDB().manifiesto().read_text(encoding="utf-8"))
    # Por día: InfluxDB 3 Core no deja consultar de una vez los ~1.000 Parquet de la carga
    conteos = {t: sum(f.get("n") or 0 for f in influx_por_dia(f"SELECT count(*) AS n FROM {t} WHERE {{filtro}}"))
               for t in TABLAS_INFLUX}
    ids = set()
    for t in ("estadisticas_equipo", "audiencia_partido"):
        ids.update(f["partido_id"] for f in influx_por_dia(f"SELECT DISTINCT partido_id FROM {t} WHERE {{filtro}}"))
    return {"puntos_por_tabla": conteos, "puntos": sum(conteos.values()),
            "manifiesto_por_tabla": manifiesto["puntos_por_tabla"], "manifiesto_total": manifiesto["puntos_totales"],
            "partido_ids": sorted(ids)}


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------
def _norm(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "").lower() if unicodedata.category(c) != "Mn")


def validar_base(nombre: str) -> dict:
    """Chequeos de UNA base, con la base todavía arriba. Devuelve {"chequeos", "datos", "leido"}:
    `leido` guarda lo que hace falta para los cruces (partido_id, equipos), que se calculan
    después con cruzar() aunque la base ya se haya apagado para liberar memoria."""
    res: dict = {"chequeos": [], "bases": {}}
    ch = res["chequeos"]
    leido: dict = {}
    bases = [nombre]

    if "mongodb" in bases:
        log("validación · MongoDB")
        m = leido["mongodb"] = leer_mongodb()
        chequeo(ch, "MongoDB · equipos", ESPERADO["mongodb"]["equipos"], m["equipos"])
        chequeo(ch, "MongoDB · jugadores", ESPERADO["mongodb"]["jugadores"], m["jugadores"])
        chequeo(ch, "MongoDB · dni duplicados", 0, m["dni_duplicados"])
        chequeo(ch, "MongoDB · (equipo, dorsal) duplicados", 0, m["dorsal_duplicados"])
        chequeo(ch, "MongoDB · jugadores sin equipo", 0, m["huerfanos"])
        res["bases"]["mongodb"] = {k: v for k, v in m.items() if k != "equipos_lista"}

    if "neo4j" in bases:
        log("validación · Neo4j")
        n = leido["neo4j"] = leer_neo4j()
        chequeo(ch, "Neo4j · partidos", ESPERADO["neo4j"]["partidos"], n["partidos"])
        chequeo(ch, "Neo4j · eventos", ESPERADO["neo4j"]["eventos"], n["eventos"])
        chequeo(ch, "Neo4j · partidoId duplicados", 0, n["partidos"] - n["partidos_distintos"])
        chequeo(ch, "Neo4j · eventoId duplicados", 0, n["eventos"] - n["eventos_distintos"])
        chequeo(ch, "Neo4j · equipoId / dni duplicados", 0,
                (n["equipos"] - n["equipos_distintos"]) + (n["jugadores"] - n["jugadores_distintos"]))
        chequeo(ch, "Neo4j · eventos sin partido", 0, n["eventos_sin_partido"])
        sin = [t for t, c in n["relaciones_enunciado"].items() if c == 0]
        chequeo(ch, "Neo4j · relaciones del enunciado presentes", "las 5", "las 5" if not sin else f"faltan {sin}")
        res["bases"]["neo4j"] = {k: v for k, v in n.items() if k not in ("partido_ids", "equipos_lista")}

    if "cassandra" in bases:
        log("validación · Cassandra (recorrido completo de las dos tablas)")
        c = leido["cassandra"] = leer_cassandra(refrescar=True)
        p, u = c["comentarios_por_partido"], c["comentarios_por_usuario"]
        esp = ESPERADO["cassandra"]["comentarios"]
        chequeo(ch, "Cassandra · comentarios (comentarios_por_partido)", esp, p["filas"])
        chequeo(ch, "Cassandra · comentarios (comentarios_por_usuario)", esp, u["filas"])
        chequeo(ch, "Cassandra · comentario_id duplicados", 0,
                (p["filas"] - p["comentario_id_distintos"]) + (u["filas"] - u["comentario_id_distintos"]))
        chequeo(ch, "Cassandra · comentarios en una sola de las dos vistas", 0, c["solo_en_una_vista"])
        res["bases"]["cassandra"] = {"comentarios_por_partido": {k: v for k, v in p.items() if k != "top_particiones"},
                                     "comentarios_por_usuario": u, "solo_en_una_vista": c["solo_en_una_vista"],
                                     "partidos_con_comentarios": len(c["filas_por_partido"]),
                                     "partidos_en_config": len(c["config_partido_ids"])}

    if "redis" in bases:
        log("validación · Redis")
        r = leido["redis"] = leer_redis()
        chequeo(ch, "Redis · usuarios del volumen (índice de sesiones, TTL 12 h)",
                ESPERADO["redis"]["usuarios"], r["usuarios_volumen"])
        chequeo(ch, "Redis · usuarios con != 1 sesión (duplicados)", 0, r["usuarios_con_sesiones_distinta_de_1"])
        res["bases"]["redis"] = {k: v for k, v in r.items() if k not in ("claves_con_partido",)}

    if "influxdb" in bases:
        log("validación · InfluxDB")
        i = leido["influxdb"] = leer_influxdb()
        chequeo(ch, "InfluxDB · puntos", ESPERADO["influxdb"]["puntos"], i["puntos"])
        for t in TABLAS_INFLUX:
            # InfluxDB deduplica por serie + timestamp: igual al manifiesto = sin pérdidas ni duplicados
            chequeo(ch, f"InfluxDB · {t} = manifiesto", i["manifiesto_por_tabla"][t], i["puntos_por_tabla"][t])
        res["bases"]["influxdb"] = i

    return {"chequeos": ch, "datos": res["bases"].get(nombre, {}), "leido": leido.get(nombre)}


def cruzar(leido: dict) -> dict:
    """Referencias cruzadas entre bases, sobre lo leído por validar_base()."""
    res: dict = {"chequeos": [], "cruces": {}}
    ch = res["chequeos"]
    # ---- referencias cruzadas: partido_id -> Neo4j --------------------------
    if "neo4j" in leido:
        canon = set(leido["neo4j"]["partido_ids"])
        fuentes = {
            "cassandra": set(leido["cassandra"]["filas_por_partido"]) | set(leido["cassandra"]["config_partido_ids"])
            if "cassandra" in leido else None,
            "redis": set(leido["redis"]["partido_ids"]) if "redis" in leido else None,
            "influxdb": set(leido["influxdb"]["partido_ids"]) if "influxdb" in leido else None,
        }
        for base, ids in fuentes.items():
            if ids is None:
                continue
            faltan = sorted(ids - canon)
            chequeo(ch, f"Cruce · partido_id de {base} que no existen en Neo4j", 0, len(faltan))
            res["cruces"][f"partidos_{base}"] = {
                "partido_ids": len(ids), "inexistentes_en_neo4j": faltan,
                "partidos_de_neo4j_sin_datos_en_esta_base": len(canon - ids)}

    # ---- equipos MongoDB <-> Neo4j (hallazgo H1: se mide, no se corrige) ----
    if "mongodb" in leido and "neo4j" in leido:
        mon = {e["_id"]: e["nombre"] for e in leido["mongodb"]["equipos_lista"]}
        neo = {e["id"]: e["nombre"] for e in leido["neo4j"]["equipos_lista"]}
        solo_m, solo_n = sorted(set(mon) - set(neo)), sorted(set(neo) - set(mon))
        nombres_n = {_norm(v): k for k, v in neo.items()}
        mismo_pais = [{"mongodb": k, "neo4j": nombres_n[_norm(mon[k])], "nombre": mon[k]}
                      for k in solo_m if _norm(mon[k]) in nombres_n]
        emparejados = {x["mongodb"] for x in mismo_pais} | {x["neo4j"] for x in mismo_pais}
        res["cruces"]["equipos_mongodb_neo4j"] = {
            "mongodb": len(mon), "neo4j": len(neo), "codigo_coincide": len(set(mon) & set(neo)),
            "solo_mongodb": [f"{k} {mon[k]}" for k in solo_m],
            "solo_neo4j": [f"{k} {neo[k]}" for k in solo_n],
            "mismo_nombre_distinto_codigo": mismo_pais,
            "sin_par_por_nombre": {"mongodb": [f"{k} {mon[k]}" for k in solo_m if k not in emparejados],
                                   "neo4j": [f"{k} {neo[k]}" for k in solo_n if k not in emparejados]},
        }
        chequeo(ch, "Cruce · equipos MongoDB sin equipoId igual en Neo4j (H1, se mide)", "medido",
                len(solo_m), ok="H1")

    return res


def resumen(ch: list) -> dict:
    return {"chequeos": len(ch), "ok": sum(1 for c in ch if c["ok"] is True),
            "fallidos": [c["chequeo"] for c in ch if c["ok"] is False],
            "informativos": [c["chequeo"] for c in ch if c["ok"] not in (True, False)]}


def validar(bases: list[str]) -> dict:
    """Todas juntas (uso suelto, con las bases arriba)."""
    res: dict = {"chequeos": [], "bases": {}, "cruces": {}}
    leido = {}
    for b in bases:
        v = validar_base(b)
        res["chequeos"] += v["chequeos"]
        res["bases"][b] = v["datos"]
        leido[b] = v["leido"]
    c = cruzar(leido)
    res["chequeos"] += c["chequeos"]
    res["cruces"] = c["cruces"]
    res["resumen"] = resumen(res["chequeos"])
    return res


if __name__ == "__main__":
    from comun import ORDEN
    print(json.dumps(validar(sys.argv[1:] or ORDEN), indent=2, ensure_ascii=False, default=str))
