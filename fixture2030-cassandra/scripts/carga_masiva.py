"""
Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)
ARCHIVO: scripts/carga_masiva.py
PROPÓSITO: carga del volumen objetivo (1.050.000 comentarios) y MEDICIÓN de la
           tasa de escritura obtenida.   CUBRE: RF11, RF12, RF13, RNF7, RNF9.

EJECUCIÓN (corre en un contenedor Python del mismo compose, no hace falta
instalar nada en la notebook):
    docker compose --profile carga run --rm cargador                      # 1.050.000
    docker compose --profile carga run --rm cargador --limite 100000      # prueba corta
    docker compose --profile carga run --rm cargador --concurrencia 64    # otra concurrencia

QUÉ MIDE
--------
- Solo el tiempo de ESCRITURA contra Cassandra. La generación de datos se mide
  aparte y se descuenta, para no atribuirle a Cassandra el costo de Python.
- Escrituras = filas escritas. Cada comentario son 2 escrituras (vista por
  partido + vista por usuario), salvo con --solo-principal.
- Consistencia ONE (W=1), la definida en el Hito 3 para comentarios.

POR QUÉ ACÁ NO SE USA LOGGED BATCH (a diferencia de la aplicación)
-----------------------------------------------------------------
La aplicación escribe las dos vistas en un LOGGED BATCH para que no queden
desalineadas ante una falla. En la carga masiva eso no hace falta: la carga es
idempotente (claves deterministas), así que si alguna escritura falla, se
vuelve a correr el script y converge. Pagar el batchlog en 2.100.000 escrituras
mediría el costo del batchlog, no el de la escritura.

IDEMPOTENCIA (RNF7): los datos salen de scripts/generador.py (determinista).
Reejecutar hace UPSERT sobre las mismas claves: no duplica comentarios.

SALIDA: docs/evidencia/carga_masiva_<fecha>.md y .json con fecha, versión de
Cassandra, recursos del ambiente, filas, tiempos, tasas y distribución (RNF9).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from cassandra import ConsistencyLevel
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile
from cassandra.concurrent import execute_concurrent
from cassandra.policies import DCAwareRoundRobinPolicy
from cassandra.query import UNSET_VALUE

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generador import (VENTANA_MINUTOS, comentarios_de_partido,  # noqa: E402
                       estadisticas_particiones, partidos, volumen_partido)

KEYSPACE = "fixture2030_comentarios"
SQL_PARTIDO = f"""
INSERT INTO {KEYSPACE}.comentarios_por_partido
  (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario,
   hinchada, minuto_partido, responde_a, contenido, idioma, editado,
   estado_moderacion, motivo_moderacion)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, false, ?, ?)"""
SQL_USUARIO = f"""
INSERT INTO {KEYSPACE}.comentarios_por_usuario
  (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket,
   minuto_partido, contenido, estado_moderacion)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
SQL_CONFIG = f"""
INSERT INTO {KEYSPACE}.config_particion_partido
  (partido_id, fase, audiencia, buckets, ventana_minutos, inicio)
VALUES (?, ?, ?, ?, ?, ?)"""


def u(valor):
    """None -> UNSET_VALUE: la columna no se escribe. Bindear None escribiría un
    null explícito, que en Cassandra es un tombstone de celda por cada fila."""
    return UNSET_VALUE if valor is None else valor


def conectar(host: str, port: int, intentos: int = 30):
    perfil = ExecutionProfile(
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
        consistency_level=ConsistencyLevel.ONE,
        request_timeout=30,
    )
    for i in range(1, intentos + 1):
        try:
            cluster = Cluster([host], port=port, execution_profiles={EXEC_PROFILE_DEFAULT: perfil})
            return cluster, cluster.connect()
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{intentos}] Cassandra todavía no responde ({e.__class__.__name__}); reintento en 5 s")
            time.sleep(5)
    raise SystemExit("No se pudo conectar a Cassandra. ¿Corriste docker compose up -d y esquema.cql?")


def memoria_total_gb() -> float | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            kb = int(f.readline().split()[1])
        return round(kb / 1024 / 1024, 1)
    except OSError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga masiva + medición de escrituras")
    ap.add_argument("--host", default=os.getenv("CASSANDRA_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("CASSANDRA_PORT", "9042")))
    ap.add_argument("--limite", type=int, default=None, help="cortar después de N comentarios")
    ap.add_argument("--concurrencia", type=int, default=128, help="escrituras en vuelo simultáneas")
    ap.add_argument("--lote", type=int, default=10_000, help="comentarios por lote de medición")
    ap.add_argument("--solo-principal", action="store_true", help="no escribir la vista por usuario")
    ap.add_argument("--salida", default=os.getenv("EVIDENCIA_DIR", "docs/evidencia"))
    args = ap.parse_args()

    cluster, session = conectar(args.host, args.port)
    version = session.execute("SELECT release_version FROM system.local").one().release_version
    st_partido = session.prepare(SQL_PARTIDO)
    st_usuario = session.prepare(SQL_USUARIO)
    st_config = session.prepare(SQL_CONFIG)

    lista = partidos()
    session.execute("USE " + KEYSPACE)
    for p in lista:
        session.execute(st_config, (p.partido_id, p.fase, p.audiencia, p.buckets, VENTANA_MINUTOS, p.inicio))

    objetivo = sum(volumen_partido(p) for p in lista)
    if args.limite:
        objetivo = min(objetivo, args.limite)
    print(f"Cassandra {version} · objetivo {objetivo:,} comentarios · concurrencia {args.concurrencia}")

    filas_particion: Counter = Counter()
    filas_usuario: Counter = Counter()
    tasas_lote: list[float] = []
    t_escritura = t_generacion = 0.0
    comentarios = escrituras = errores = 0
    primer_error = None
    inicio_total = time.perf_counter()

    def volcar(buffer: list[tuple]) -> None:
        nonlocal t_escritura, escrituras, errores, primer_error
        t0 = time.perf_counter()
        res = execute_concurrent(session, buffer, concurrency=args.concurrencia,
                                 raise_on_first_error=False, results_generator=True)
        ok = 0
        for exito, r in res:
            if exito:
                ok += 1
            else:
                errores += 1
                primer_error = primer_error or repr(r)
        dt = time.perf_counter() - t0
        t_escritura += dt
        escrituras += ok
        tasas_lote.append(ok / dt if dt else 0.0)

    buffer: list[tuple] = []
    tg = time.perf_counter()
    for p in lista:
        if comentarios >= objetivo:
            break
        for r in comentarios_de_partido(p):
            if comentarios >= objetivo:
                break
            buffer.append((st_partido, (
                r["partido_id"], r["ventana"], r["bucket"], r["creado_en"], r["comentario_id"],
                r["usuario_id"], r["alias_usuario"], r["hinchada"], r["minuto_partido"],
                u(r["responde_a"]), r["contenido"], r["idioma"], r["estado_moderacion"],
                u(r["motivo_moderacion"]))))
            if not args.solo_principal:
                buffer.append((st_usuario, (
                    r["usuario_id"], r["mes"], r["creado_en"], r["comentario_id"], r["partido_id"],
                    r["ventana"], r["bucket"], r["minuto_partido"], r["contenido"],
                    r["estado_moderacion"])))
                filas_usuario[(r["usuario_id"], r["mes"])] += 1
            filas_particion[(r["partido_id"], r["ventana"].isoformat(), r["bucket"])] += 1
            comentarios += 1
            if comentarios % args.lote == 0:
                t_generacion += time.perf_counter() - tg
                volcar(buffer)
                buffer = []
                print(f"  {comentarios:>9,} comentarios · lote {tasas_lote[-1]:>9,.0f} escr/s · "
                      f"acumulado {escrituras / t_escritura:>9,.0f} escr/s · errores {errores}")
                tg = time.perf_counter()
    if buffer:
        t_generacion += time.perf_counter() - tg
        volcar(buffer)
    duracion_total = time.perf_counter() - inicio_total
    cluster.shutdown()

    top = filas_particion.most_common(5)
    informe = {
        "fecha_ejecucion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cassandra_release_version": version,
        "ambiente": {
            "nodos": 1,
            "replication_factor": 1,
            "consistencia_escritura": "ONE",
            "cpus_visibles": os.cpu_count(),
            "memoria_total_gb": memoria_total_gb(),
            "python": platform.python_version(),
            "plataforma": platform.platform(),
            "nota": "cliente y servidor en la misma notebook: compiten por CPU",
        },
        "parametros": {"concurrencia": args.concurrencia, "lote": args.lote,
                       "solo_principal": args.solo_principal, "limite": args.limite},
        "resultado": {
            "comentarios": comentarios,
            "escrituras_ok": escrituras,
            "errores": errores,
            "primer_error": primer_error,
            "segundos_escritura": round(t_escritura, 2),
            "segundos_generacion": round(t_generacion, 2),
            "segundos_totales": round(duracion_total, 2),
            "escrituras_por_segundo": round(escrituras / t_escritura, 1) if t_escritura else 0,
            "comentarios_por_segundo": round(comentarios / t_escritura, 1) if t_escritura else 0,
            "tasa_por_lote": {
                "min": round(min(tasas_lote), 1),
                "mediana": round(statistics.median(tasas_lote), 1),
                "max": round(max(tasas_lote), 1),
            } if tasas_lote else {},
            "objetivo_10000_escrituras_s": (escrituras / t_escritura) >= 10_000 if t_escritura else False,
        },
        "distribucion": {
            "comentarios_por_particion": estadisticas_particiones(filas_particion),
            "top5_particiones": [{"particion": list(k), "filas": v} for k, v in top],
            "filas_por_particion_usuario": estadisticas_particiones(filas_usuario),
        },
    }

    carpeta = Path(args.salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    sello = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (carpeta / f"carga_masiva_{sello}.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False),
                                                        encoding="utf-8")
    res, dist = informe["resultado"], informe["distribucion"]["comentarios_por_particion"]
    md = [
        f"# Carga masiva — {informe['fecha_ejecucion']}",
        "",
        "| Dato | Valor |", "|---|---|",
        f"| Versión de Cassandra | {version} |",
        f"| CPUs visibles / RAM | {os.cpu_count()} / {memoria_total_gb()} GB |",
        f"| Concurrencia | {args.concurrencia} |",
        f"| Comentarios cargados | {comentarios:,} |",
        f"| Escrituras OK / errores | {escrituras:,} / {errores} |",
        f"| Tiempo de escritura | {res['segundos_escritura']} s |",
        f"| **Tasa de escritura** | **{res['escrituras_por_segundo']:,} escrituras/s** |",
        f"| Tasa por lote (mín / mediana / máx) | {res['tasa_por_lote'].get('min')} / "
        f"{res['tasa_por_lote'].get('mediana')} / {res['tasa_por_lote'].get('max')} |",
        f"| ¿Alcanza 10.000 escr/s? | {'Sí' if res['objetivo_10000_escrituras_s'] else 'No'} |",
        "",
        "## Distribución (filas por partición de comentarios_por_partido)",
        "",
        f"particiones {dist.get('particiones')} · mín {dist.get('min')} · p50 {dist.get('p50')} · "
        f"p90 {dist.get('p90')} · p99 {dist.get('p99')} · máx {dist.get('max')}",
        "",
        "Top 5: " + "; ".join(f"{k} = {v:,}" for k, v in top),
    ]
    (carpeta / f"carga_masiva_{sello}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\nEvidencia guardada en {carpeta}/carga_masiva_{sello}.(md|json)")


if __name__ == "__main__":
    main()
