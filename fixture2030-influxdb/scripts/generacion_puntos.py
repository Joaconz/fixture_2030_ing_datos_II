"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 3 Core)
ARCHIVO: scripts/generacion_puntos.py
PROPÓSITO: GENERAR (no cargar) los puntos en line protocol, de forma determinista.
           La carga está en carga_lotes.py y la verificación en validacion.py (RF7).

USO (desde la carpeta del módulo):
    docker compose run --rm herramientas scripts/generacion_puntos.py --perfil muestra
    docker compose run --rm herramientas scripts/generacion_puntos.py --perfil completo

PERFILES
  muestra   2 partidos (PAR-A-1 normal, PAR-D16-01 máxima audiencia) ≈ 176 mil puntos
  completo  los 112 partidos del Hito 5 + operación continua     ≈ 10,09 millones de puntos
  --limite-partidos N: los primeros N partidos por fecha (prueba intermedia)

TABLAS GENERADAS (base fixture2030_vivo, precisión: SEGUNDOS)
  estadisticas_equipo    feed deportivo, 1 punto por equipo por segundo de juego
  audiencia_partido      plataforma, 1 punto por región por segundo, desde −15' hasta +130'
  operacion_plataforma   observabilidad, 1 punto por servicio cada 10 s, continuo

DETERMINISMO: toda aleatoriedad sale de random.Random(<semilla por partido/serie>).
Generar dos veces produce archivos idénticos, y cargar dos veces escribe los mismos
puntos (misma serie + mismo timestamp): InfluxDB 3 los deduplica, no duplica filas.

SALIDA: data/lp/<perfil>/<tabla>/<archivo>.lp.gz + data/lp/<perfil>/manifiesto.json
        (el manifiesto es la "verdad esperada" que después contrasta validacion.py).
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (AUDIENCIA_DESDE, AUDIENCIA_HASTA, FIN_PRIMER_TIEMPO,  # noqa: E402
                   FIN_SEGUNDO_TIEMPO, INICIO_SEGUNDO_TIEMPO, PRECISION, UTC,
                   Partido, calendario, cronometro, minuto_de_segundo)

MUESTRA = ["PAR-A-1", "PAR-D16-01"]

# Regiones de audiencia: los 6 países anfitriones + 2 agregados. Cuota base de la audiencia.
REGIONES = {"AR": 0.09, "UY": 0.03, "PY": 0.03, "ES": 0.14, "PT": 0.06, "MA": 0.07,
            "RESTO_AMERICAS": 0.22, "RESTO_MUNDO": 0.36}
ANFITRION_REGION = {"ARG": "AR", "URU": "UY", "PAR": "PY", "ESP": "ES", "POR": "PT", "MAR": "MA"}

# Servicios de la plataforma (los módulos de los hitos anteriores)
SERVICIOS = {  # cuota de solicitudes, latencia p95 base en ms
    "sesiones": (0.35, 4.0),       # Hito 7 (Redis)
    "api": (0.30, 35.0),
    "cache": (0.20, 2.0),          # Hito 7 (Redis)
    "comentarios": (0.10, 18.0),   # Hito 6 (Cassandra)
    "estadisticas": (0.05, 12.0),  # este módulo
}
SOLICITUDES_POR_USUARIO_S = 0.04   # 2,8 M usuarios -> ~112.000 req/s (Hito 1: >100.000)
PASO_OPERACION = 10                # segundos


def esc_tag(v: str) -> str:
    return v.replace(",", r"\,").replace(" ", r"\ ").replace("=", r"\=")


# ---------------------------------------------------------------------------
# Curva de audiencia: función PURA del segundo de reloj (la usa también la operación)
# ---------------------------------------------------------------------------
# Puntos de control (segundo de reloj, fracción del pico). Entre puntos se interpola
# linealmente: la audiencia sube y baja de forma continua, sin saltos.
CURVA = [(AUDIENCIA_DESDE, 0.35), (0, 0.85), (60, 0.90), (FIN_PRIMER_TIEMPO, 1.00),
         (FIN_PRIMER_TIEMPO + 120, 0.80), (INICIO_SEGUNDO_TIEMPO - 120, 0.80),
         (INICIO_SEGUNDO_TIEMPO, 0.95), (FIN_SEGUNDO_TIEMPO, 1.00), (AUDIENCIA_HASTA, 0.30)]


def curva_audiencia(p: Partido, s: int, region: str | None = None) -> float:
    if s < AUDIENCIA_DESDE or s >= AUDIENCIA_HASTA:
        return 0.0
    for (s0, v0), (s1, v1) in zip(CURVA, CURVA[1:]):
        if s0 <= s < s1:
            base = v0 + (v1 - v0) * (s - s0) / (s1 - s0)
            break
    return base * (1 + efecto_gol(p, s, region))


def forma_gol(d: int) -> float:
    """Tras un gol la actividad sube durante 1 minuto (llega gente) y se diluye en 4."""
    if 0 <= d < 60:
        return d / 60
    if 60 <= d < 300:
        return 1 - (d - 60) / 240
    return 0.0


def efecto_gol(p: Partido, s: int, region: str | None = None) -> float:
    """Reacción a los goles. Sin región (total de la plataforma): +15 %. Por región: +40 % si
    el gol es de la selección de ese país anfitrión, −10 % si lo recibe, +10 % si es neutral.
    Por eso cada región tiene su pico en un momento distinto del partido."""
    ef = 0.0
    for sg, cond in p.goles:
        f = forma_gol(s - sg)
        if f == 0:
            continue
        if region is None:
            peso = 0.15
        else:
            autor = p.local if cond == "LOCAL" else p.visitante
            receptor = p.visitante if cond == "LOCAL" else p.local
            peso = 0.40 if ANFITRION_REGION.get(autor) == region else \
                -0.10 if ANFITRION_REGION.get(receptor) == region else 0.10
        ef += peso * f
    return ef


def actividad_gol(p: Partido, s: int) -> float:
    """Forma de la reacción (0..1) sin importar la región: la usan los comentarios."""
    return max((forma_gol(s - sg) for sg, _ in p.goles), default=0.0)


def cuotas_region(p: Partido) -> dict:
    c = dict(REGIONES)
    for eq in (p.local, p.visitante):
        if eq in ANFITRION_REGION:
            c[ANFITRION_REGION[eq]] *= 3
    total = sum(c.values())
    return {k: v / total for k, v in c.items()}


# ---------------------------------------------------------------------------
# Tabla 1: estadisticas_equipo
# ---------------------------------------------------------------------------
def gen_estadisticas(p: Partido):
    """Posesión (gauge acumulado, %), pases/tiros/goles (contadores acumulados),
    recuperaciones (evento del segundo, 0/1) y minuto de juego."""
    rng = random.Random(f"est-{p.partido_id}")
    t0 = p.inicio_epoch
    goles_en = {}
    for sg, cond in p.goles:
        goles_en.setdefault(sg, []).append(0 if cond == "LOCAL" else 1)
    equipos = [(p.local, "LOCAL"), (p.visitante, "VISITANTE")]
    prefijo = [
        f"estadisticas_equipo,partido_id={p.partido_id},equipo_id={eq},condicion={cond},"
        f"fase={p.fase},sede_id={p.sede_id} "
        for eq, cond in equipos
    ]
    posesion = [0, 0]
    pases = [0, 0]
    tiros = [0, 0]
    goles = [0, 0]
    con_pelota = 0 if rng.random() < 0.5 else 1
    jugado = 0
    for s in list(range(0, FIN_PRIMER_TIEMPO)) + list(range(INICIO_SEGUNDO_TIEMPO, FIN_SEGUNDO_TIEMPO)):
        recup = [0, 0]
        if s == INICIO_SEGUNDO_TIEMPO:
            con_pelota = 1 - con_pelota            # saca el otro equipo
        elif rng.random() < 0.02:
            con_pelota = 1 - con_pelota
            recup[con_pelota] = 1
        posesion[con_pelota] += 1
        jugado += 1
        if rng.random() < 0.16:
            pases[con_pelota] += 1
        if rng.random() < 0.004:
            tiros[con_pelota] += 1
        for eq in goles_en.get(s, []):             # gol del calendario: siempre viene con tiro
            tiros[eq] += 1
            goles[eq] += 1
        # Posesión acumulada con 30 s "virtuales" por lado: arranca en 50/50 y no en 100/0
        pos_local = round(100.0 * (posesion[0] + 30) / (jugado + 60), 1)
        pos = (pos_local, round(100.0 - pos_local, 1))
        minuto = minuto_de_segundo(s)
        for i in (0, 1):
            yield (f"{prefijo[i]}posesion_pct={pos[i]:.1f},pases_acum={pases[i]}i,tiros_acum={tiros[i]}i,"
                   f"goles_acum={goles[i]}i,recuperaciones={recup[i]}i,minuto_juego={minuto}i {t0 + s}\n")


# ---------------------------------------------------------------------------
# Tabla 2: audiencia_partido
# ---------------------------------------------------------------------------
def gen_audiencia(p: Partido):
    """usuarios_conectados (gauge), comentarios y sesiones_nuevas (eventos del segundo)."""
    t0 = p.inicio_epoch
    cuotas = cuotas_region(p)
    for region, cuota in cuotas.items():
        rng = random.Random(f"aud-{p.partido_id}-{region}")
        pref = f"audiencia_partido,partido_id={p.partido_id},region={region},fase={p.fase} "
        previo = None
        ruido = 0.0                                   # ruido suave (AR(1)): la audiencia no salta
        for s in range(AUDIENCIA_DESDE, AUDIENCIA_HASTA):
            ruido = max(-0.02, min(0.02, 0.98 * ruido + rng.gauss(0, 0.0008)))
            usuarios = int(p.pico_usuarios * cuota * curva_audiencia(p, s, region) * (1 + ruido))
            en_juego = 0 <= s < FIN_SEGUNDO_TIEMPO
            lam = usuarios * (1.0e-5 if en_juego else 0.4e-5) * (1 + 4 * actividad_gol(p, s))
            comentarios = int(lam + rng.random())                 # redondeo estocástico
            churn = int(usuarios * 2e-5 + rng.random())
            nuevas = churn + (max(0, usuarios - previo) if previo is not None else 0)
            previo = usuarios
            yield (f"{pref}usuarios_conectados={usuarios}i,comentarios={comentarios}i,"
                   f"sesiones_nuevas={nuevas}i {t0 + s}\n")


# ---------------------------------------------------------------------------
# Tabla 3: operacion_plataforma
# ---------------------------------------------------------------------------
def gen_operacion(partidos: list[Partido], desde: int, hasta: int):
    """Una línea por servicio cada 10 s en [desde, hasta). La carga depende de la
    audiencia TOTAL de los partidos en curso en ese instante."""
    ventanas = [(p.inicio_epoch + AUDIENCIA_DESDE, p.inicio_epoch + AUDIENCIA_HASTA, p) for p in partidos]
    for t in range(desde, hasta, PASO_OPERACION):
        usuarios = 50_000.0                        # base fuera de partido
        for a, b, p in ventanas:
            if a <= t < b:
                usuarios += p.pico_usuarios * curva_audiencia(p, t - p.inicio_epoch)
        carga = usuarios / 3_000_000
        rng = random.Random(f"ops-{t}")
        for serv, (cuota, lat_base) in SERVICIOS.items():
            solicitudes = int(usuarios * SOLICITUDES_POR_USUARIO_S * cuota * PASO_OPERACION
                              * (1 + rng.uniform(-0.03, 0.03)))
            latencia = lat_base * (1 + 1.5 * carga ** 2) * (1 + rng.uniform(-0.05, 0.08))
            tasa_error = 1e-4 * (1 + 20 * max(0.0, carga - 0.8))
            errores = int(solicitudes * tasa_error + rng.random())
            yield (f"operacion_plataforma,servicio={serv} latencia_p95_ms={latencia:.2f},"
                   f"solicitudes={solicitudes}i,errores={errores}i {t}\n")


# ---------------------------------------------------------------------------
def escribir(ruta: Path, lineas) -> dict:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    tmin = tmax = None
    # mtime=0: el .gz es byte a byte igual en cada generación (determinismo verificable)
    with open(ruta, "wb") as bruto, gzip.GzipFile(fileobj=bruto, mode="wb", compresslevel=1, mtime=0) as f:
        buf = []
        for ln in lineas:
            buf.append(ln)
            if len(buf) >= 20_000:
                f.write("".join(buf).encode("utf-8"))
                buf.clear()
            n += 1
            ts = int(ln.rsplit(" ", 1)[1])
            tmin = ts if tmin is None else min(tmin, ts)
            tmax = ts if tmax is None else max(tmax, ts)
        if buf:
            f.write("".join(buf).encode("utf-8"))
    return {"archivo": str(ruta), "puntos": n, "t_min": tmin, "t_max": tmax}


def main() -> None:
    ap = argparse.ArgumentParser(description="Generación determinista de puntos (line protocol)")
    ap.add_argument("--perfil", choices=["muestra", "completo"], default="muestra")
    ap.add_argument("--limite-partidos", type=int, default=None)
    ap.add_argument("--salida", default="data/lp")
    args = ap.parse_args()

    todos = calendario()
    if args.perfil == "muestra":
        partidos = [p for p in todos if p.partido_id in MUESTRA]
    else:
        partidos = todos[: args.limite_partidos] if args.limite_partidos else todos
    nombre_perfil = args.perfil if not args.limite_partidos else f"completo_{args.limite_partidos}"
    raiz = Path(args.salida) / nombre_perfil
    reloj = cronometro()
    archivos = []

    for p in partidos:
        archivos.append({"tabla": "estadisticas_equipo", "partido_id": p.partido_id,
                         **escribir(raiz / "estadisticas_equipo" / f"{p.partido_id}.lp.gz", gen_estadisticas(p))})
        archivos.append({"tabla": "audiencia_partido", "partido_id": p.partido_id,
                         **escribir(raiz / "audiencia_partido" / f"{p.partido_id}.lp.gz", gen_audiencia(p))})
        print(f"  {p.partido_id:<11} {p.local}-{p.visitante}  {p.inicio:%Y-%m-%d %H:%M}Z  audiencia {p.audiencia}")

    # Operación: continua en el perfil completo; solo alrededor de cada partido en la muestra
    if args.perfil == "completo" and not args.limite_partidos:
        tramos = [(partidos[0].inicio_epoch - 3600, partidos[-1].inicio_epoch + 3 * 3600)]
    else:
        tramos = []
        for p in partidos:                     # unir tramos que se superponen (sin puntos duplicados)
            a, b = p.inicio_epoch - 3600, p.inicio_epoch + 3 * 3600
            if tramos and a <= tramos[-1][1]:
                tramos[-1] = (tramos[-1][0], max(tramos[-1][1], b))
            else:
                tramos.append((a, b))
    for desde, hasta in tramos:
        desde -= desde % PASO_OPERACION
        dia = desde
        while dia < hasta:                     # un archivo por día UTC
            fin_dia = min(hasta, (dia // 86400 + 1) * 86400)
            nombre = datetime.fromtimestamp(dia, UTC).strftime("%Y-%m-%dT%H%M")
            archivos.append({"tabla": "operacion_plataforma", "partido_id": None,
                             **escribir(raiz / "operacion_plataforma" / f"{nombre}.lp.gz",
                                        gen_operacion(todos, dia, fin_dia))})
            dia = fin_dia

    por_tabla: dict[str, int] = {}
    for a in archivos:
        por_tabla[a["tabla"]] = por_tabla.get(a["tabla"], 0) + a["puntos"]
    manifiesto = {
        "perfil": nombre_perfil,
        "base": "fixture2030_vivo",
        "precision": PRECISION,
        "partidos": [{"partido_id": p.partido_id, "fase": p.fase, "local": p.local,
                      "visitante": p.visitante, "sede_id": p.sede_id, "inicio": p.inicio.isoformat(),
                      "audiencia": p.audiencia, "pico_usuarios": p.pico_usuarios,
                      "goles": p.goles} for p in partidos],
        "puntos_por_tabla": por_tabla,
        "puntos_totales": sum(por_tabla.values()),
        "series_esperadas": {
            "estadisticas_equipo": 2 * len(partidos),
            "audiencia_partido": len(REGIONES) * len(partidos),
            "operacion_plataforma": len(SERVICIOS),
        },
        "archivos": archivos,
        "segundos_generacion": round(reloj(), 1),
    }
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nPerfil {nombre_perfil}: {len(partidos)} partidos · {manifiesto['puntos_totales']:,} puntos "
          f"en {len(archivos)} archivos · {manifiesto['segundos_generacion']} s")
    for t, n in por_tabla.items():
        print(f"  {t:<22} {n:>12,}")
    print(f"Manifiesto: {raiz / 'manifiesto.json'}")


if __name__ == "__main__":
    main()
