"""
Fixture 2030 — Carga masiva integrada (Hito 11 del PDF del TPO)
ARCHIVO: scripts/distribucion.py
PROPÓSITO: ANÁLISIS DE DISTRIBUCIÓN de los datos ya cargados en las 5 bases f30cm-*:
  - MongoDB:   jugadores por equipo, por confederación y por posición; tamaños (collStats)
  - Neo4j:     nodos por etiqueta, relaciones por tipo, grados por etiqueta, nodos más conectados
  - Cassandra: nodetool tablestats / tablehistograms + filas por partición y por partido
  - Redis:     claves por tipo y por prefijo, memoria (redis-cli --memkeys, INFO)
  - InfluxDB:  series y puntos por partido y por tabla, tamaño en disco

USO SUELTO (con las bases cargadas):  python scripts/distribucion.py
Lo llama orquestador.py; el texto que interpreta estos números está en
docs/distribucion_y_escalabilidad.md.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import Cassandra, InfluxDB, MongoDB, Redis, cypher, dexec, influx_por_dia, log, mongo_json  # noqa: E402
from validacion import leer_cassandra  # noqa: E402


def resumen_numeros(v: list[int]) -> dict:
    v = sorted(v)
    if not v:
        return {}
    return {"n": len(v), "min": v[0], "p50": v[len(v) // 2], "p90": v[int(.9 * (len(v) - 1))],
            "max": v[-1], "prom": round(statistics.mean(v), 1),
            "max_sobre_prom": round(v[-1] / statistics.mean(v), 1) if statistics.mean(v) else None}


def dist_mongodb() -> dict:
    return mongo_json(MongoDB.contenedor, """({
      por_equipo: db.jugadores.aggregate([{$group: {_id: "$equipoId", n: {$sum: 1}}},
                    {$group: {_id: null, equipos: {$sum: 1}, min: {$min: "$n"}, max: {$max: "$n"}, prom: {$avg: "$n"}}}]).toArray()[0],
      por_confederacion: db.jugadores.aggregate([
                    {$lookup: {from: "equipos", localField: "equipoId", foreignField: "_id", as: "e"}},
                    {$group: {_id: {$first: "$e.confederacion"}, jugadores: {$sum: 1}, equipos: {$addToSet: "$equipoId"}}},
                    {$project: {jugadores: 1, equipos: {$size: "$equipos"}}}, {$sort: {jugadores: -1}}]).toArray(),
      por_posicion: db.jugadores.aggregate([{$group: {_id: "$posicion", n: {$sum: 1}}}, {$sort: {n: -1}}]).toArray(),
      tamanos: ["equipos", "jugadores"].map(c => { const s = db.getCollection(c).stats();
                 return {coleccion: c, documentos: s.count, bytes_datos: s.size, bytes_promedio_doc: s.avgObjSize,
                         bytes_almacenados: s.storageSize, indices: s.nindexes, bytes_indices: s.totalIndexSize}; })
    })""")


def dist_neo4j() -> dict:
    etiquetas = cypher("MATCH (n) UNWIND labels(n) AS l RETURN l AS etiqueta, count(*) AS n ORDER BY n DESC")
    tipos = cypher("MATCH ()-[r]->() RETURN type(r) AS tipo, count(*) AS n ORDER BY n DESC")
    grados = []
    for e in etiquetas:
        g = cypher(f"MATCH (n:`{e['etiqueta']}`) WITH COUNT {{ (n)--() }} AS g "
                   "RETURN min(g) AS min, percentileDisc(g, 0.5) AS p50, percentileDisc(g, 0.99) AS p99, "
                   "max(g) AS max, round(avg(g), 1) AS prom")[0]
        grados.append({"etiqueta": e["etiqueta"], **g})
    top = cypher("MATCH (n) WITH n, COUNT { (n)--() } AS g ORDER BY g DESC LIMIT 5 "
                 "RETURN labels(n)[0] AS etiqueta, coalesce(n.partidoId, n.equipoId, n.dni, n.sedeId, "
                 "n.grupoId, n.tipoEventoId, n.eventoId) AS id, g AS grado")
    eventos_partido = cypher("MATCH (p:Partido) RETURN p.fase AS fase, count(p) AS partidos, "
                             "sum(COUNT { (p)--(:Evento) }) AS eventos ORDER BY partidos DESC")
    return {"nodos_por_etiqueta": etiquetas, "relaciones_por_tipo": tipos, "grados": grados,
            "mas_conectados": top, "eventos_por_fase": eventos_partido}


_TABLESTATS = ["Space used (live)", "Space used (total)", "SSTable count", "Number of partitions (estimate)",
               "Compacted partition minimum bytes", "Compacted partition maximum bytes",
               "Compacted partition mean bytes", "Local write count", "Memtable data size"]


def dist_cassandra() -> dict:
    ks = "fixture2030_comentarios"
    # flush: las filas que siguen en memtable no aparecen en las estadísticas por SSTable
    dexec(Cassandra.contenedor, "nodetool", "flush", ks, timeout=600)
    tablas = {}
    actual = None
    for linea in dexec(Cassandra.contenedor, "nodetool", "tablestats", ks).splitlines():
        m = re.match(r"\s*Table: (\S+)", linea)
        if m:
            actual = tablas.setdefault(m.group(1), {})
            continue
        if actual is not None and ":" in linea:
            k, v = [x.strip() for x in linea.split(":", 1)]
            if k in _TABLESTATS:
                actual[k] = v
    histos = {t: dexec(Cassandra.contenedor, "nodetool", "tablehistograms", ks, t).strip()
              for t in ("comentarios_por_partido", "comentarios_por_usuario")}
    scan = leer_cassandra()
    por_partido = scan["filas_por_partido"]
    top = sorted(por_partido.items(), key=lambda kv: -kv[1])
    return {"tablestats": {t: v for t, v in tablas.items() if t in ("comentarios_por_partido", "comentarios_por_usuario",
                                                                     "config_particion_partido")},
            "tablehistograms": histos,
            "filas_por_particion": {"comentarios_por_partido": scan["comentarios_por_partido"]["filas_por_particion"],
                                    "particiones_comentarios_por_partido": scan["comentarios_por_partido"]["particiones"],
                                    "comentarios_por_usuario": scan["comentarios_por_usuario"]["filas_por_particion"],
                                    "particiones_comentarios_por_usuario": scan["comentarios_por_usuario"]["particiones"]},
            "top_particiones": scan["comentarios_por_partido"]["top_particiones"],
            "comentarios_por_partido": resumen_numeros(list(por_partido.values())),
            "partidos_mas_comentados": top[:5], "partidos_menos_comentados": top[-3:]}


def dist_redis() -> dict:
    tipos = {}
    for m in re.finditer(r"(\d+) (\w+?)s? with (\d+) bytes", dexec(Redis.contenedor, "redis-cli", "--memkeys",
                                                                     timeout=900)):
        tipos[m.group(2)] = {"claves": int(m.group(1)), "bytes": int(m.group(3))}
    claves = dexec(Redis.contenedor, "redis-cli", "--scan", "--count", "1000").split()
    prefijos: dict[str, int] = {}
    for k in claves:
        p = k.split(":")
        nombre = ":".join(p[:2]) if p[1] != "cache" else ":".join(p[:3])
        nombre += ":…:" + p[-1] if p[1] in ("usr", "cache") and len(p) > 3 else ""
        prefijos[nombre] = prefijos.get(nombre, 0) + 1
    info = {}
    for seccion in ("memory", "keyspace", "stats"):
        for linea in dexec(Redis.contenedor, "redis-cli", "INFO", seccion).splitlines():
            if ":" in linea:
                k, v = linea.strip().split(":", 1)
                if k in ("used_memory", "used_memory_human", "used_memory_peak_human", "maxmemory_human",
                         "maxmemory_policy", "mem_fragmentation_ratio", "used_memory_dataset", "db0",
                         "evicted_keys", "expired_keys"):
                    info[k] = v
    muestras = {}
    for nombre, patron in (("sesion (HASH)", "f30:ses:vol-ses-000000000000"),
                           ("indice de sesiones (SET)", "f30:usr:USR-1000000:sesiones"),
                           ("perfil en cache (HASH)", "f30:cache:usuario:USR-1000000:perfil")):
        v = dexec(Redis.contenedor, "redis-cli", "MEMORY", "USAGE", patron).strip()
        muestras[nombre] = int(v) if v.isdigit() else None
    return {"por_tipo": tipos, "por_prefijo": dict(sorted(prefijos.items(), key=lambda kv: -kv[1])),
            "info": info, "bytes_por_clave_muestra": muestras}


def dist_influxdb() -> dict:
    series = {
        "estadisticas_equipo": "partido_id, equipo_id, condicion, fase, sede_id",
        "audiencia_partido": "partido_id, region, fase",
        "operacion_plataforma": "servicio",
    }
    res: dict = {"series_por_tabla": {}, "puntos_por_partido": {}}
    # Todo por día (influx_por_dia): una serie es una combinación de tags; se juntan las de cada día
    for t, tags in series.items():
        filas = influx_por_dia(f"SELECT DISTINCT {tags} FROM {t} WHERE {{filtro}}")
        res["series_por_tabla"][t] = len({tuple(sorted(f.items())) for f in filas})
    for t in ("estadisticas_equipo", "audiencia_partido"):
        v: dict[str, int] = {}
        for f in influx_por_dia(f"SELECT partido_id, count(*) AS n FROM {t} WHERE {{filtro}} GROUP BY partido_id"):
            v[f["partido_id"]] = v.get(f["partido_id"], 0) + f["n"]
        res["puntos_por_partido"][t] = {**resumen_numeros(list(v.values())),
                                        "top": sorted(v.items(), key=lambda kv: -kv[1])[:3]}
    manifiesto = json.loads(InfluxDB().manifiesto().read_text(encoding="utf-8"))
    res["partidos_por_audiencia"] = {}
    for p in manifiesto["partidos"]:
        res["partidos_por_audiencia"][p["audiencia"]] = res["partidos_por_audiencia"].get(p["audiencia"], 0) + 1
    res["disco"] = dexec(InfluxDB.contenedor, "sh", "-c",
                         "du -sh /var/lib/influxdb3/data | cut -f1; "
                         "find /var/lib/influxdb3/data -name '*.parquet' | wc -l; "
                         "find /var/lib/influxdb3/data -name '*.wal' | wc -l").split()
    res["disco"] = dict(zip(["tamano", "archivos_parquet", "archivos_wal"], res["disco"]))
    return res


FUNCIONES = {"mongodb": dist_mongodb, "neo4j": dist_neo4j, "cassandra": dist_cassandra,
             "redis": dist_redis, "influxdb": dist_influxdb}


def distribuir(bases: list[str]) -> dict:
    res = {}
    for b in bases:
        log(f"distribución · {b}")
        try:
            res[b] = FUNCIONES[b]()
        except Exception as e:  # noqa: BLE001 — se informa, no corta el reporte
            res[b] = {"error": f"{e.__class__.__name__}: {e}"}
    return res


if __name__ == "__main__":
    from comun import ORDEN
    print(json.dumps(distribuir(sys.argv[1:] or ORDEN), indent=2, ensure_ascii=False, default=str))
