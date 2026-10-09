"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 3 Core)
ARCHIVO: scripts/carga_lotes.py
PROPÓSITO: CARGAR los archivos que produjo generacion_puntos.py, en lotes, con
           concurrencia, reintentos y medición (RF7, RF12, RF13).

USO:
    docker compose run --rm herramientas scripts/carga_lotes.py --perfil muestra
    docker compose run --rm herramientas scripts/carga_lotes.py --perfil completo --hilos 8 --lote 50000

ESTRATEGIA (documentada en docs/cardinalidad_y_escalabilidad.md §4)
  · Lote: N líneas por POST (por defecto 50.000 ≈ 7 MB, debajo de los 10 MB que
    recomienda InfluxDB 3). Cada POST se confirma recién cuando el WAL se vuelca a
    disco (cada 1 s): cada viaje cuesta ~1 s sea cual sea su tamaño, así que conviene
    mandar más líneas por viaje. Medido en docs/evidencia/barrido/: 10.000 líneas y
    4 hilos dan ~40.000 puntos/s; 50.000 líneas, ~100.000 puntos/s.
  · Concurrencia: H hilos con POST en paralelo (por defecto 8). Como máximo 2·H
    lotes en vuelo: el generador no llena la memoria si el servidor va más lento.
  · Orden: dentro de cada archivo, cronológico (el orden monótono por partido del
    Hito 3). Entre archivos no importa: InfluxDB acepta puntos fuera de orden.
  · Una línea inválida (sintaxis o tipo de field distinto al de la tabla) hace que
    InfluxDB rechace el lote entero (HTTP 400, porque se envía accept_partial=false)
    y la carga se DETIENE mostrando el error.
  · OJO: un punto más viejo que la retención de la base NO da error: InfluxDB 3
    responde 204 y lo descarta en silencio (validacion.py V5). Por eso la carga no
    alcanza como prueba: validacion.py compara lo cargado contra el manifiesto (V1).
  · Reintentos: ante 429, 5xx o error de red se reintenta hasta 4 veces con espera
    exponencial (0,5 s, 1 s, 2 s, 4 s). Reintentar es seguro porque la carga es
    idempotente: el mismo punto (serie + timestamp) se sobrescribe, no se duplica.

MEDICIÓN: se cronometra la carga completa (lectura + envío) y la latencia de cada
POST. El resultado va a evidencia/carga_<perfil>_<fecha>.md/.json con versión,
ambiente, puntos y resultados. No se reporta ninguna cifra que no se haya medido.
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
import time
import urllib.error
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (DB_VIVO, ambiente, cronometro, encabezado, escribir_lp,  # noqa: E402
                   guardar_evidencia, version_servidor)

REINTENTABLES = {429, 500, 502, 503, 504}


class ErrorDeCarga(Exception):
    pass


def enviar(lote: bytes, n: int, reintentos: int, gz: bool) -> dict:
    espera = 0.5
    for intento in range(reintentos + 1):
        t0 = time.perf_counter()
        try:
            estado, cuerpo = escribir_lp(DB_VIVO, lote, gzip_body=gz)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            estado, cuerpo = None, str(e).encode()
        dt = time.perf_counter() - t0
        if estado in (200, 204):
            return {"lineas": n, "bytes": len(lote), "segundos": dt, "reintentos": intento}
        if estado is not None and estado not in REINTENTABLES:
            raise ErrorDeCarga(f"HTTP {estado} (no reintentable): {cuerpo.decode('utf-8', 'replace')[:400]}")
        if intento < reintentos:
            time.sleep(espera)
            espera *= 2
    raise ErrorDeCarga(f"Se agotaron los reintentos. Último estado: {estado} {cuerpo[:200]!r}")


def lotes_de(archivo: Path, tam: int):
    with gzip.open(archivo, "rb") as f:
        buf, n = [], 0
        for linea in f:
            buf.append(linea)
            n += 1
            if n == tam:
                yield b"".join(buf), n
                buf, n = [], 0
        if buf:
            yield b"".join(buf), n


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga por lotes a InfluxDB 3 Core")
    ap.add_argument("--perfil", default="muestra")
    ap.add_argument("--entrada", default="data/lp")
    ap.add_argument("--lote", type=int, default=50_000, help="líneas por POST")
    ap.add_argument("--hilos", type=int, default=8, help="POST concurrentes")
    ap.add_argument("--reintentos", type=int, default=4)
    ap.add_argument("--gzip", action="store_true", help="comprimir el cuerpo de cada POST")
    ap.add_argument("--tabla", default=None, help="cargar solo esta tabla")
    args = ap.parse_args()

    raiz = Path(args.entrada) / args.perfil
    manifiesto = json.loads((raiz / "manifiesto.json").read_text(encoding="utf-8"))
    archivos = [a for a in manifiesto["archivos"] if not args.tabla or a["tabla"] == args.tabla]
    esperado = sum(a["puntos"] for a in archivos)
    version = version_servidor()
    print(f"{version} · perfil {args.perfil} · {esperado:,} puntos · lote {args.lote} · hilos {args.hilos}")

    resultados, por_tabla = [], {}
    enviados = 0
    reloj = cronometro()
    error = None
    with ThreadPoolExecutor(max_workers=args.hilos) as pool:
        en_vuelo = set()
        try:
            for a in archivos:
                t_arch = cronometro()
                for lote, n in lotes_de(Path(a["archivo"]), args.lote):
                    if len(en_vuelo) >= 2 * args.hilos:
                        hechos, en_vuelo = wait(en_vuelo, return_when=FIRST_COMPLETED)
                        for h in hechos:
                            resultados.append(h.result())
                    en_vuelo.add(pool.submit(enviar, lote, n, args.reintentos, args.gzip))
                    enviados += n
                por_tabla.setdefault(a["tabla"], [0, 0.0])
                por_tabla[a["tabla"]][0] += a["puntos"]
                por_tabla[a["tabla"]][1] += t_arch()
                print(f"  {a['tabla']:<22} {Path(a['archivo']).name:<26} {a['puntos']:>9,} · "
                      f"acumulado {enviados:>11,} · {enviados / reloj():>9,.0f} puntos/s")
            for h in wait(en_vuelo).done:
                resultados.append(h.result())
        except ErrorDeCarga as e:
            error = str(e)
            print(f"\n✖ Carga detenida: {error}")
    total_s = reloj()

    ok = sum(r["lineas"] for r in resultados)
    lat = sorted(r["segundos"] for r in resultados) or [0.0]
    datos = {
        "perfil": args.perfil, "servidor": version, "ambiente_cliente": ambiente(),
        "parametros": {"lote": args.lote, "hilos": args.hilos, "reintentos": args.reintentos,
                       "gzip": args.gzip, "tabla": args.tabla, "precision": manifiesto["precision"]},
        "puntos_esperados": esperado, "puntos_confirmados": ok, "lotes": len(resultados),
        "lotes_con_reintento": sum(1 for r in resultados if r["reintentos"]),
        "segundos_totales": round(total_s, 2),
        "puntos_por_segundo": round(ok / total_s, 1) if total_s else 0,
        "mb_enviados": round(sum(r["bytes"] for r in resultados) / 1e6, 1),
        "latencia_post_s": {"p50": round(statistics.median(lat), 3),
                            "p95": round(lat[max(0, -(-95 * len(lat) // 100) - 1)], 3),
                            "max": round(lat[-1], 3)},
        "error": error,
    }
    md = encabezado(f"Carga por lotes — perfil {args.perfil}") + [
        "| Dato | Valor |", "|---|---|",
        f"| Puntos esperados (manifiesto) | {esperado:,} |",
        f"| Puntos confirmados por el servidor | {ok:,} |",
        f"| Lotes enviados / con reintento | {len(resultados):,} / {datos['lotes_con_reintento']} |",
        f"| Tamaño de lote / hilos / gzip | {args.lote} / {args.hilos} / {args.gzip} |",
        f"| Tiempo total | {datos['segundos_totales']} s |",
        f"| **Tasa de carga** | **{datos['puntos_por_segundo']:,} puntos/s** |",
        f"| Datos enviados | {datos['mb_enviados']} MB |",
        f"| Latencia por POST p50 / p95 / máx | {datos['latencia_post_s']['p50']} / "
        f"{datos['latencia_post_s']['p95']} / {datos['latencia_post_s']['max']} s |",
        f"| Error | {error or 'ninguno'} |",
        "", "Por tabla (puntos / segundos de lectura y envío):", "",
        *[f"- `{t}`: {v[0]:,} puntos · {v[1]:.1f} s" for t, v in por_tabla.items()],
        "", "La verificación de que lo cargado coincide con el manifiesto está en `validacion.py`.",
    ]
    ruta = guardar_evidencia(f"carga_{args.perfil}", "\n".join(md) + "\n", datos)
    print("\n" + "\n".join(md[5:]))
    print(f"\nEvidencia: {ruta}")
    if error or ok != esperado:
        sys.exit(1)


if __name__ == "__main__":
    main()
