"""
Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)
ARCHIVO: scripts/generar_muestra.py
PROPÓSITO: regenerar scripts/carga_muestra.cql y data/muestra_comentarios.csv
           a partir del MISMO generador determinista de la carga masiva.

POR QUÉ LA MUESTRA SE DERIVA DE LA CARGA MASIVA
-----------------------------------------------
La muestra es un SUBCONJUNTO EXACTO de los 1.050.000 comentarios de la carga
masiva (mismas claves primarias, mismos valores). Si se generara aparte, el
comentario 'PAR-A-1-C0000001' tendría en la muestra un creado_en distinto al de
la carga masiva, y como creado_en es parte de la clave primaria, cargar ambas
dejaría DOS filas para el mismo comentario lógico. Derivándola del mismo flujo,
cargar la muestra y después la masiva (o al revés) converge al mismo estado.

USO (no requiere Cassandra ni librerías externas):
    python3 scripts/generar_muestra.py
"""
from __future__ import annotations

import csv
from pathlib import Path

from generador import comentarios_de_partido, partidos, VENTANA_MINUTOS

RAIZ = Path(__file__).resolve().parent.parent
SALIDA_CQL = RAIZ / "scripts" / "carga_muestra.cql"
SALIDA_CSV = RAIZ / "data" / "muestra_comentarios.csv"

# Partidos de la muestra y paso de submuestreo (1 de cada N comentarios)
MUESTRA = {"PAR-A-1": 200, "PAR-D16-01": 8000}
USUARIO_DEMO = "USR-0000038"   # comenta en ambos partidos -> sirve para el historial

COLUMNAS = ["partido_id", "ventana", "bucket", "creado_en", "comentario_id", "usuario_id",
            "alias_usuario", "hinchada", "minuto_partido", "contenido", "idioma",
            "estado_moderacion", "motivo_moderacion", "responde_a"]


def ts(d) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S.") + f"{d.microsecond // 1000:03d}+0000"


def lit(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, int):
        return str(v)
    if hasattr(v, "strftime"):
        return f"'{ts(v)}'"
    return "'" + str(v).replace("'", "''") + "'"


def main() -> None:
    todos = {p.partido_id: p for p in partidos()}
    filas = []
    for pid, paso in MUESTRA.items():
        for r in comentarios_de_partido(todos[pid]):
            seq = int(r["comentario_id"].rsplit("C", 1)[1])
            if seq % paso == 0 or r["usuario_id"] == USUARIO_DEMO:
                filas.append(r)

    lineas = [
        "-- ============================================================================",
        "--  Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)",
        "--  ARCHIVO: scripts/carga_muestra.cql   (GENERADO por scripts/generar_muestra.py)",
        "--  PROPÓSITO: carga PEQUEÑA para validar esquema, CRUD y consultas en desarrollo.",
        "--",
        "--  EJECUCIÓN (después de esquema.cql):",
        "--      docker compose exec cassandra cqlsh -f /scripts/carga_muestra.cql",
        "--",
        "--  IDEMPOTENCIA (RNF7): en Cassandra INSERT es un UPSERT sobre la clave primaria.",
        "--  Todas las claves son deterministas, así que reejecutar este archivo deja",
        "--  exactamente las mismas filas. No se cargan contadores acá a propósito:",
        "--  un UPDATE ... SET c = c + 1 NO es idempotente (ver decisiones §6).",
        "--  Las columnas sin valor se OMITEN del INSERT (escribir null crea tombstones).",
        "--",
        f"--  CONTENIDO: 112 filas de configuración + {len(filas)} comentarios",
        f"--  ({', '.join(MUESTRA)}), duplicados de forma controlada en",
        "--  comentarios_por_partido y comentarios_por_usuario.",
        "-- ============================================================================",
        "",
        "USE fixture2030_comentarios;",
        "",
        "-- ----------------------------------------------------------------------------",
        "--  1) Configuración de partición de los 112 partidos del Hito 5",
        "--     buckets se fija ANTES del partido según la audiencia esperada.",
        "-- ----------------------------------------------------------------------------",
    ]
    for p in todos.values():
        lineas.append(
            "INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) "
            f"VALUES ({lit(p.partido_id)}, {lit(p.fase)}, {lit(p.audiencia)}, {p.buckets}, "
            f"{VENTANA_MINUTOS}, {lit(p.inicio)});"
        )

    lineas += [
        "",
        "-- ----------------------------------------------------------------------------",
        "--  2) Comentarios: escritura DUAL controlada (vista por partido + vista por usuario)",
        "--     Cada par va en un LOGGED BATCH para que las dos vistas no queden",
        "--     desalineadas si falla una de las escrituras (ver decisiones §5).",
        "-- ----------------------------------------------------------------------------",
    ]
    for r in filas:
        # Las columnas en None NO se escriben: un INSERT con null explícito deja un
        # tombstone de celda por cada null (ver decisiones §6).
        cols = [c for c in COLUMNAS if r[c] is not None]
        v = [lit(r[c]) for c in cols]
        lineas += [
            "BEGIN BATCH",
            "  INSERT INTO comentarios_por_partido (" + ", ".join(cols) + ", editado) "
            "VALUES (" + ", ".join(v) + ", false);",
            "  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, "
            "ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ("
            f"{lit(r['usuario_id'])}, {lit(r['mes'])}, {lit(r['creado_en'])}, {lit(r['comentario_id'])}, "
            f"{lit(r['partido_id'])}, {lit(r['ventana'])}, {r['bucket']}, {r['minuto_partido']}, "
            f"{lit(r['contenido'])}, {lit(r['estado_moderacion'])});",
            "APPLY BATCH;",
        ]

    lineas += [
        "",
        "-- ----------------------------------------------------------------------------",
        "--  3) Verificación: correr este archivo dos veces debe dar los mismos conteos.",
        "-- ----------------------------------------------------------------------------",
        "SELECT count(*) AS config_partidos FROM config_particion_partido;",
        "SELECT count(*) AS comentarios_par_a_1 FROM comentarios_por_partido "
        "WHERE partido_id = 'PAR-A-1' AND ventana IN (" +
        ", ".join(sorted({lit(r['ventana']) for r in filas if r['partido_id'] == 'PAR-A-1'})) +
        ") AND bucket = 0;",
        f"SELECT count(*) AS historial_demo FROM comentarios_por_usuario WHERE usuario_id = '{USUARIO_DEMO}' AND mes = '2030-06';",
        "",
    ]
    SALIDA_CQL.write_text("\n".join(lineas), encoding="utf-8")

    SALIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNAS + ["mes"])
        for r in filas:
            w.writerow([ts(r[c]) if hasattr(r[c], "strftime") else ("" if r[c] is None else r[c])
                        for c in COLUMNAS] + [r["mes"]])

    print(f"{SALIDA_CQL.relative_to(RAIZ)}: 112 configs + {len(filas)} comentarios")
    print(f"{SALIDA_CSV.relative_to(RAIZ)}: {len(filas)} filas")
    for pid in MUESTRA:
        sub = [r for r in filas if r["partido_id"] == pid]
        print(f"  {pid}: {len(sub)} comentarios, ventanas {len({r['ventana'] for r in sub})}, "
              f"buckets {sorted({r['bucket'] for r in sub})}")


if __name__ == "__main__":
    main()
