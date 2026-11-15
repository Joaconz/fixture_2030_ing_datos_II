"""
Fixture 2030 — Carga masiva integrada (Hito 11 del PDF del TPO)
ARCHIVO: scripts/comparar.py
PROPÓSITO: comparar corridas del orquestador (paralelo vs. secuencial, antes vs. después
de una optimización) a partir de sus reporte.json. No mide nada nuevo: solo pone lado a
lado lo que cada corrida registró.

USO:
    python scripts/comparar.py evidencia/corridas/<A> evidencia/corridas/<B> [...] --salida evidencia/comparacion_x.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def cargar(carpeta: str) -> dict:
    return json.loads((Path(carpeta) / "reporte.json").read_text(encoding="utf-8"))


def f(x) -> str:
    if isinstance(x, float):
        return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(x, int):
        return f"{x:,}".replace(",", ".")
    return "–" if x is None else str(x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corridas", nargs="+")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--titulo", default="Comparación de corridas")
    a = ap.parse_args()
    rs = [cargar(c) for c in a.corridas]
    nombres = [r["meta"]["corrida"] for r in rs]
    bases = [b for b in ("mongodb", "neo4j", "cassandra", "influxdb", "redis") if any(b in r["bases"] for r in rs)]

    L = [f"# {a.titulo}", "", "| Corrida | Modo | Commit | Parámetros |", "|---|---|---|---|"]
    for r in rs:
        m = r["meta"]
        cupo = f" (de a {m['max_paralelo']})" if m["max_paralelo"] else ""
        L.append(f"| `{m['corrida']}` | {m['modo']}{cupo} | "
                 f"`{m['commit']}` | Cassandra conc. {m['parametros']['cassandra_concurrencia']}, Influx lote "
                 f"{f(m['parametros']['influx_lote'])} / hilos {m['parametros']['influx_hilos']} |")
    L += ["", "## Tiempo de reloj y recursos", "", "| Métrica | " + " | ".join(nombres) + " |",
          "|---|" + "---:|" * len(rs)]
    filas = [
        ("Reloj hasta la última carga (s)", lambda r: r["total"]["reloj_hasta_ultima_carga_s"]),
        ("Reloj total con verificación y apagado (s)", lambda r: r["total"]["segundos_reloj_total"]),
        ("Suma de las cargas (s)", lambda r: r["total"]["suma_segundos_carga"]),
        ("Suma arranque + preparación + carga (s)", lambda r: r["total"]["suma_arranque_preparacion_carga_s"]),
        ("Última carga en terminar", lambda r: r["total"]["termina_ultima"]),
        ("Presupuesto de memoria (MiB)", lambda r: r["meta"]["memoria_inicial"]["presupuesto_mib"]),
        ("Máx. bases simultáneas", lambda r: max((a["simultaneas"] for a in r.get("admisiones", [])), default=None)),
        ("Pico RAM de la prueba (MiB)", lambda r: r["recursos"].get("pico_mem_prueba_mib")),
        ("Pico RAM de toda la VM (MiB)", lambda r: r["recursos"].get("pico_mem_total_vm_mib")),
        ("Pico CPU de la prueba (%)", lambda r: r["recursos"].get("pico_cpu_prueba_pct")),
        ("RAM libre mínima del host (MiB)", lambda r: r["recursos"].get("ram_libre_host_min_mib")),
        ("Chequeos de integridad OK", lambda r: f"{r['validacion'].get('resumen', {}).get('ok')}/"
                                                f"{r['validacion'].get('resumen', {}).get('chequeos')}"),
    ]
    for nombre, fn in filas:
        L.append(f"| {nombre} | " + " | ".join(f(fn(r)) for r in rs) + " |")
    for fase in ("arranque", "preparacion", "carga", "verificacion"):
        L += ["", f"## Fase: {fase} (segundos)", "", "| Base | " + " | ".join(nombres) + " |",
              "|---|" + "---:|" * len(rs)]
        for b in bases:
            L.append(f"| {b} | " + " | ".join(f(r["bases"].get(b, {}).get("fases", {}).get(fase, {}).get("segundos"))
                                            for r in rs) + " |")
    L += ["", "## Throughput de la carga", "", "| Base | " + " | ".join(nombres) + " |", "|---|" + "---:|" * len(rs)]
    for b in bases:
        L.append(f"| {b} | " + " | ".join(
            f"{f(r['bases'].get(b, {}).get('por_segundo'))} {r['bases'].get(b, {}).get('unidad', '')}/s" for r in rs) + " |")
    L += ["", "## Tasa medida por el propio cargador", "", "| Base | " + " | ".join(nombres) + " |", "|---|" + "---:|" * len(rs)]
    for b in ("cassandra", "influxdb"):
        L.append(f"| {b} | " + " | ".join(f(r["bases"].get(b, {}).get("tasa_propia")) for r in rs) + " |")
    salida = Path(a.salida)
    salida.write_text("\n".join(L) + "\n", encoding="utf-8")
    datos = {"corridas": nombres, "filas": {n: [fn(r) for r in rs] for n, fn in filas}}
    salida.with_suffix(".json").write_text(json.dumps(datos, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
