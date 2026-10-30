"""
Fixture 2030 — Hito 12 · comparación línea base vs. optimizada (RF10)
ARCHIVO: scripts/comparar.py
USO: <python> scripts/comparar.py docs/evidencia/resultados_linea_base docs/evidencia/resultados_optimizada
Lee SOLO archivos generados por las corridas (k6_resumen.json, recursos.csv,
lecturas_q0.txt, integridad.json): no hay ninguna cifra cargada a mano (RNF14).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def k6(d: Path) -> dict:
    m = json.load(open(d / "k6_resumen.json", encoding="utf-8"))["metrics"]
    v = lambda k, s: m.get(k, {}).get("values", {}).get(s)  # noqa: E731
    return {
        "requests": v("http_reqs", "count"), "req_s": v("http_reqs", "rate"),
        "error_pct": 100 * (v("http_req_failed", "rate") or 0),
        **{f"get_{s}": v("lat_get_comentarios", s) for s in ("min", "med", "p(95)", "p(99)", "max")},
        **{f"post_{s}": v("lat_post_comentario", s) for s in ("min", "med", "p(95)", "p(99)", "max")},
        "post_201": v("posts_201_creados", "count") or 0, "post_err": v("posts_error", "count") or 0,
    }


def recursos(d: Path) -> dict:
    filas = list(csv.DictReader(open(d / "recursos.csv", encoding="utf-8")))
    def serie(c):
        out = []
        for f in filas:
            try:
                out.append(float(f[c]))
            except (ValueError, TypeError, KeyError):
                pass
        return out
    r = {}
    for c, n in (("cassandra_cpu_pct", "cas_cpu"), ("api_cpu_pct", "api_cpu"), ("api_rss_mb", "api_mb"),
                 ("k6_cpu_pct", "k6_cpu")):
        s = serie(c)
        r[n + "_prom"] = sum(s) / len(s) if s else None
        r[n + "_max"] = max(s) if s else None
    r["muestras"] = len(filas)
    return r


def q0(d: Path) -> int | None:
    try:
        v = dict(l.strip().split("=", 1) for l in open(d / "lecturas_q0.txt") if "=" in l)
        return int(v["lecturas_q0_despues"]) - int(v["lecturas_q0_antes"])
    except Exception:
        return None


def integ(d: Path) -> str:
    try:
        j = json.load(open(d / "integridad.json", encoding="utf-8"))
        return ("✅" if j["ok"] else "❌") + f" {j['filas']} filas · {j['duplicados']} dup · {j['sin_par']} sin par"
    except Exception:
        return "sin validar"


def fmt(x, dec=1):
    return "—" if x is None else f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Entre pares de corridas con el mismo código se vieron variaciones de ±8 % en throughput y de hasta ~20 % en latencias
# (docs/evidencia/pares_sin_limpieza.md):
# una diferencia menor al 15 % no se considera ni mejora ni empeoramiento.
RUIDO_PCT = 15


def delta(a, b, menor_es_mejor=True):
    if a in (None, 0) or b is None:
        return "—"
    p = 100 * (b - a) / a
    mejora = (p < 0) if menor_es_mejor else (p > 0)
    if abs(p) < RUIDO_PCT:
        return f"{p:+.1f} % ≈"
    return f"{p:+.1f} % {'✅' if mejora else '⚠️'}"


base_d, opt_d = Path(sys.argv[1]), Path(sys.argv[2])
b, o = {**k6(base_d), **recursos(base_d)}, {**k6(opt_d), **recursos(opt_d)}
filas = [
    ("Requests totales", "requests", 0, False), ("Throughput (req/s)", "req_s", 1, False),
    ("Requests fallidas (%)", "error_pct", 2, True),
    ("GET p50 (ms)", "get_med", 1, True), ("GET p95 (ms)", "get_p(95)", 1, True),
    ("GET p99 (ms)", "get_p(99)", 1, True), ("GET máx (ms)", "get_max", 1, True),
    ("POST p50 (ms)", "post_med", 1, True), ("POST p95 (ms)", "post_p(95)", 1, True),
    ("POST p99 (ms)", "post_p(99)", 1, True), ("POST 201 confirmados", "post_201", 0, False),
    ("CPU Cassandra prom / máx (%)", "cas_cpu", 1, True), ("CPU API prom / máx (%)", "api_cpu", 1, True),
    ("CPU generador k6 prom / máx (%)", "k6_cpu", 1, True), ("Memoria API máx (MB)", "api_mb_max", 1, True),
]
print("# Comparación línea base vs. optimizada\n")
print("Generado por `scripts/comparar.py` a partir de los archivos de cada corrida (sin cifras a mano).\n")
print("| Métrica | Línea base | Optimizada | Variación |\n|---|---:|---:|---:|")
for nombre, k, dec, menor in filas:
    if k in ("cas_cpu", "api_cpu", "k6_cpu"):
        print(f"| {nombre} | {fmt(b[k+'_prom'])} / {fmt(b[k+'_max'])} | {fmt(o[k+'_prom'])} / {fmt(o[k+'_max'])} | "
              f"{delta(b[k+'_prom'], o[k+'_prom'])} |")
    else:
        print(f"| {nombre} | {fmt(b[k], dec)} | {fmt(o[k], dec)} | {delta(b[k], o[k], menor)} |")
qb, qo = q0(base_d), q0(opt_d)
print(f"| Lecturas de `config_particion_partido` (Q0) | {fmt(qb, 0)} | {fmt(qo, 0)} | {delta(qb, qo)} |")
print(f"| Integridad | {integ(base_d)} | {integ(opt_d)} | |")
print(f"\nMuestras de recursos: {b['muestras']} (base) / {o['muestras']} (optimizada), cada 2 s.")
print(f"\n✅ mejora · ⚠️ empeora · ≈ variación menor al {RUIDO_PCT} % (dentro del ruido entre corridas con el mismo código).")
