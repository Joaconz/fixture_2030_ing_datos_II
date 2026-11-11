"""
Fixture 2030 — Carga masiva integrada (Hito 11 del PDF del TPO)
ARCHIVO: scripts/orquestador.py
PROPÓSITO: cargar el VOLUMEN COMPLETO en las 5 bases de la arquitectura vigente
(MongoDB, Neo4j, Cassandra, Redis, InfluxDB; IRIS quedó fuera con aprobación del
profesor), con los cargadores QUE YA TIENE CADA MÓDULO, en paralelo o en secuencia,
y dejar un reporte de tiempos, recursos, integridad y distribución.

USO (desde la raíz del repo; Python >= 3.10 y Docker Desktop):
    python fixture2030-carga-masiva/scripts/orquestador.py --modo paralelo
    python fixture2030-carga-masiva/scripts/orquestador.py --modo secuencial
    python fixture2030-carga-masiva/scripts/orquestador.py --modo paralelo --orden redis mongodb neo4j influxdb cassandra
    python fixture2030-carga-masiva/scripts/orquestador.py --modo paralelo --cassandra-concurrencia 32 --etiqueta conc32

QUÉ HACE, EN ORDEN
  0. Limpieza: `down -v` de los proyectos f30cm-* y borrado de sus carpetas de datos
     (~/docker/data/f30cm/*). Cada corrida arranca DESDE VOLÚMENES VACÍOS.
  1. Insumos: los .lp.gz de InfluxDB (generacion_puntos.py --perfil completo) si faltan.
     Son deterministas; se generan una vez y no cuentan como carga.
  2. Por cada base, cinco fases cronometradas por separado:
       arranque      docker compose up -d --wait (hasta healthy)
       preparacion   esquema / estructura / dependencias del cargador
       carga         el cargador del módulo, sin cambios           <- lo que se compara
       verificacion  validación de integridad y distribución de ESA base (validacion.py,
                     distribucion.py); guarda partido_id y equipos para los cruces
       apagado       down -v: libera la memoria para la base siguiente
     --modo paralelo: ADMISIÓN POR PRESUPUESTO DE MEMORIA. Arranca, en el orden de --orden,
       la primera base cuya reserva (suma de sus mem_limit, compose/*.yml) entre en el
       presupuesto = RAM de la VM − RAM de los contenedores ajenos − margen; las demás esperan
       a que otra se apague. Arrancar las 5 a la vez colgó Docker Desktop
       (evidencia/cuelgue_20261111.md).
     --modo secuencial: una detrás de otra.
  3. Mientras tanto, `docker stats` cada ~2 s (CPU y RAM de cada contenedor) y RAM libre del host.
  4. Referencias cruzadas entre bases (partido_id -> Neo4j, equipos MongoDB <-> Neo4j).
  5. Reporte: evidencia/corridas/<sello>_<modo>[_etiqueta]/ con reporte.md, reporte.json,
     salida.txt (todo lo que imprimió cada cargador), recursos.csv.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun  # noqa: E402
from comun import (CLASES, EVIDENCIA, ORDEN, ErrorPaso, InfluxDB, Muestreador, ahora, commit,  # noqa: E402
                   cpus_vm, log, memoria_contenedores_mib, memoria_vm_bytes, ram_libre_host_mib, sello)
from distribucion import distribuir  # noqa: E402
from validacion import cruzar, resumen, validar_base  # noqa: E402

FASES = ["arranque", "preparacion", "carga", "verificacion", "apagado"]


def ejecutar_pipeline(base, t0: float, resultado: dict, leidos: dict, op: dict) -> None:
    r = resultado[base.nombre] = {"fases": {}, "estado": "ok"}

    def verificar():
        v = validar_base(base.nombre)
        r["validacion"] = {"chequeos": v["chequeos"], "datos": v["datos"]}
        leidos[base.nombre] = v["leido"]
        if not op["sin_distribucion"]:
            r["distribucion"] = distribuir([base.nombre])[base.nombre]

    acciones = {"arranque": base.arrancar, "preparacion": base.preparar, "carga": base.cargar,
                "verificacion": verificar, "apagado": base.apagar}
    for fase in FASES:
        if fase == "apagado" and not op["liberar"]:
            continue
        if comun.ABORTO and fase != "apagado":
            r["estado"] = f"cortada por el vigía antes de {fase}"
            r.setdefault("fallas", []).append(f"vigía: {comun.ABORTO}")
            break
        ini = time.perf_counter()
        log(f"{base.nombre:<9} ▶ {fase}")
        try:
            salida = acciones[fase]()
        except Exception as e:  # noqa: BLE001 — se registra; la base queda marcada
            r["fases"][fase] = {"desde_s": round(ini - t0, 1), "hasta_s": round(time.perf_counter() - t0, 1),
                                "segundos": round(time.perf_counter() - ini, 1)}
            r.setdefault("fallas", []).append(f"{fase}: {e.__class__.__name__}: {e}")
            log(f"{base.nombre:<9} ✖ {fase}: {e.__class__.__name__}: {e}")
            if fase == "verificacion":   # sin validación no hay integridad comprobada: cuenta como falla
                r["validacion"] = {"chequeos": r.get("validacion", {}).get("chequeos", []) + [
                    {"chequeo": f"{base.nombre} · verificación completa", "esperado": "sin error",
                     "obtenido": f"{e.__class__.__name__}: {str(e)[:160]}", "ok": False}], "datos": {}}
            if fase in ("arranque", "preparacion", "carga"):
                r["estado"] = f"falló en {fase}"
                if op["liberar"]:
                    _apagar_silencioso(base)
                return
            continue   # una falla al verificar no invalida la carga; se informa
        fin = time.perf_counter()
        r["fases"][fase] = {"desde_s": round(ini - t0, 1), "hasta_s": round(fin - t0, 1),
                            "segundos": round(fin - ini, 1)}
        if fase == "carga":
            r.update(salida)
            r["por_segundo"] = round(salida["volumen"] / (fin - ini), 1) if fin > ini else None
        log(f"{base.nombre:<9} ✔ {fase} en {fin - ini:,.1f} s"
            + (f" · {salida['volumen']:,} {salida['unidad']} · {r['por_segundo']:,} /s" if fase == "carga" else ""))


def _apagar_silencioso(base) -> None:
    try:
        base.apagar()
    except Exception as e:  # noqa: BLE001
        log(f"✖ apagado de {base.nombre}: {e}")


def planificar_paralelo(bases: list, t0: float, resultado: dict, leidos: dict, op: dict,
                        presupuesto: int | None, max_paralelo: int | None) -> list[dict]:
    """Admisión por presupuesto de memoria: arranca (en orden, la primera que entre) toda base cuya
    reserva entre en lo que queda del presupuesto; la reserva se devuelve cuando la base se apaga.
    Si no hay ninguna corriendo y la siguiente no entra sola, se la deja pasar igual (avisando):
    no hay forma de cargarla con menos memoria."""
    cond = threading.Condition()
    estado = {"reservado": 0, "activos": 0}
    pendientes = list(bases)
    hilos, admisiones = [], []

    def correr(b):
        try:
            ejecutar_pipeline(b, t0, resultado, leidos, op)
        finally:
            with cond:
                estado["activos"] -= 1
                if op["liberar"]:
                    estado["reservado"] -= b.reserva_mib
                cond.notify_all()

    with cond:
        while pendientes:
            if comun.ABORTO:
                log(f"✖ no se admiten más bases: {', '.join(b.nombre for b in pendientes)}")
                for b in pendientes:
                    resultado[b.nombre] = {"fases": {}, "estado": "no arrancó (vigía)"}
                break
            elegida = None
            for b in pendientes:
                if max_paralelo and estado["activos"] >= max_paralelo:
                    break
                if presupuesto is None or estado["reservado"] + b.reserva_mib <= presupuesto:
                    elegida = b
                    break
            if elegida is None and estado["activos"] == 0:
                elegida = pendientes[0]
                log(f"⚠ {elegida.nombre}: reserva {elegida.reserva_mib} MiB + reservado {estado['reservado']} MiB "
                    f"supera el presupuesto ({presupuesto} MiB); arranca sola")
            if elegida is None:
                cond.wait(timeout=5)
                continue
            pendientes.remove(elegida)
            estado["reservado"] += elegida.reserva_mib
            estado["activos"] += 1
            admisiones.append({"base": elegida.nombre, "t_s": round(time.perf_counter() - t0, 1),
                               "reservado_mib": estado["reservado"], "simultaneas": estado["activos"],
                               "ram_libre_host_mib": ram_libre_host_mib()})
            log(f"{elegida.nombre:<9} admitida · reservado {estado['reservado']}/{presupuesto or '∞'} MiB · "
                f"{estado['activos']} en curso")
            h = threading.Thread(target=correr, args=(elegida,))
            h.start()
            hilos.append(h)
    for h in hilos:
        h.join()
    return admisiones


def main() -> int:
    ap = argparse.ArgumentParser(description="Carga masiva integrada de las 5 bases (Hito 11 del PDF)")
    ap.add_argument("--modo", choices=["paralelo", "secuencial"], default="paralelo")
    ap.add_argument("--bases", nargs="+", choices=ORDEN, default=ORDEN)
    ap.add_argument("--orden", nargs="+", choices=ORDEN, default=None,
                    help="orden de arranque (secuencial) o de admisión (paralelo)")
    ap.add_argument("--max-paralelo", type=int, default=None, help="tope de pipelines simultáneos (paralelo)")
    ap.add_argument("--margen-mib", type=int, default=768, help="RAM de la VM que no se reparte (paralelo)")
    ap.add_argument("--presupuesto-mib", type=int, default=None, help="fija el presupuesto en vez de calcularlo")
    ap.add_argument("--sin-presupuesto", action="store_true",
                    help="arranca todo a la vez sin control de memoria (colgó Docker: no usar)")
    ap.add_argument("--cassandra-concurrencia", type=int, default=None, help="--concurrencia de carga_masiva.py")
    ap.add_argument("--influx-hilos", type=int, default=None, help="--hilos de carga_lotes.py")
    ap.add_argument("--influx-lote", type=int, default=None, help="--lote de carga_lotes.py")
    ap.add_argument("--etiqueta", default="", help="sufijo de la carpeta de evidencia")
    ap.add_argument("--sin-distribucion", action="store_true")
    ap.add_argument("--conservar", action="store_true",
                    help="no apagar ninguna base (todas quedan arriba: ojo con la memoria)")
    args = ap.parse_args()

    corrida = f"{sello()}_{args.modo}" + (f"_{args.etiqueta}" if args.etiqueta else "")
    carpeta = EVIDENCIA / "corridas" / corrida
    carpeta.mkdir(parents=True, exist_ok=True)
    comun.log.archivo = carpeta / "salida.txt"
    comando = "python fixture2030-carga-masiva/scripts/orquestador.py " + " ".join(sys.argv[1:])
    vm_mib = round(memoria_vm_bytes() / 2 ** 20)
    mem0 = memoria_contenedores_mib()
    presupuesto = None
    if args.modo == "paralelo" and not args.sin_presupuesto:
        presupuesto = args.presupuesto_mib or vm_mib - mem0["ajenos"] - mem0["prueba"] - args.margen_mib
    meta = {"corrida": corrida, "fecha_inicio": ahora(), "commit": commit(), "comando": comando,
            "modo": args.modo, "max_paralelo": args.max_paralelo, "bases": args.bases,
            "vm": {"cpus": cpus_vm(), "memoria_gib": round(vm_mib / 1024, 2)},
            "memoria_inicial": {"vm_mib": vm_mib, "contenedores_ajenos_mib": mem0["ajenos"],
                                "contenedores_ajenos": mem0["ajenos_cantidad"],
                                "ram_libre_host_mib": ram_libre_host_mib(),
                                "presupuesto_mib": presupuesto, "margen_mib": args.margen_mib},
            "parametros": {"cassandra_concurrencia": args.cassandra_concurrencia or 128,
                           "influx_hilos": args.influx_hilos or 8, "influx_lote": args.influx_lote or 50_000}}
    log(f"# Ejecutado: {meta['fecha_inicio']} | commit: {meta['commit']} | comando: {comando}")
    log(f"# VM de Docker: {meta['vm']['cpus']} CPUs, {vm_mib} MiB · contenedores ajenos: "
        f"{mem0['ajenos_cantidad']} ({mem0['ajenos']} MiB) · RAM libre del host: "
        f"{meta['memoria_inicial']['ram_libre_host_mib']} MiB · presupuesto: {presupuesto or 'sin control'} MiB")

    op = {"corrida": corrida, "cassandra_concurrencia": args.cassandra_concurrencia,
          "influx_hilos": args.influx_hilos, "influx_lote": args.influx_lote,
          "liberar": not args.conservar, "sin_distribucion": args.sin_distribucion}
    orden = [b for b in (args.orden or ORDEN) if b in args.bases]
    orden += [b for b in ORDEN if b in args.bases and b not in orden]
    meta["orden"] = orden
    bases = [CLASES[n](op) for n in orden]

    # 0. limpieza ------------------------------------------------------------
    log("== 0. Limpieza: proyectos f30cm-* abajo, volúmenes y carpetas de datos borrados")
    for b in bases:
        b.limpiar()

    # 1. insumos ------------------------------------------------------------
    insumos = None
    if "influxdb" in args.bases:
        log("== 1. Insumos de InfluxDB (data/lp/completo, deterministas)")
        s = InfluxDB(op).generar_insumos()
        insumos = {"generados_en_esta_corrida": s is not None, "segundos": round(s, 1) if s else None}
        log("   generados en %.1f s" % s if s else "   ya existían: se reutilizan (no cuentan como carga)")

    # 2. pipelines ----------------------------------------------------------
    log(f"== 2. Carga en modo {args.modo} · orden {' → '.join(orden)}")
    muestreador = Muestreador(vm_mib=vm_mib)
    muestreador.fase = "pipelines"
    muestreador.start()
    resultado: dict = {}
    leidos: dict = {}
    admisiones: list = []
    t0 = time.perf_counter()
    meta["inicio_carga"] = ahora()
    if args.modo == "secuencial":
        for b in bases:
            if comun.ABORTO:
                resultado[b.nombre] = {"fases": {}, "estado": "no arrancó (vigía)"}
                continue
            admisiones.append({"base": b.nombre, "t_s": round(time.perf_counter() - t0, 1),
                               "reservado_mib": b.reserva_mib, "simultaneas": 1,
                               "ram_libre_host_mib": ram_libre_host_mib()})
            ejecutar_pipeline(b, t0, resultado, leidos, op)
    else:
        admisiones = planificar_paralelo(bases, t0, resultado, leidos, op, presupuesto, args.max_paralelo)
    total = time.perf_counter() - t0
    meta["fin"] = ahora()
    muestreador.detener()
    recursos = muestreador.resumen()
    muestreador.csv(carpeta / "recursos.csv")

    # 3. cruces -------------------------------------------------------------
    log("== 3. Referencias cruzadas")
    chequeos = [c for b in orden for c in resultado.get(b, {}).get("validacion", {}).get("chequeos", [])]
    cruces = cruzar({b: v for b, v in leidos.items() if v is not None})
    chequeos += cruces["chequeos"]
    validacion = {"chequeos": chequeos, "cruces": cruces["cruces"], "resumen": resumen(chequeos),
                  "bases": {b: r.get("validacion", {}).get("datos") for b, r in resultado.items()}}
    distribucion = {b: r["distribucion"] for b, r in resultado.items() if "distribucion" in r}

    meta["vigia"] = comun.ABORTO
    informe = {"meta": meta, "insumos_influxdb": insumos, "admisiones": admisiones,
               "bases": {b: {k: v for k, v in r.items() if k not in ("validacion", "distribucion")}
                         for b, r in resultado.items()},
               "total": totales(resultado, total), "recursos": recursos,
               "validacion": validacion, "distribucion": distribucion}
    (carpeta / "reporte.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False, default=str),
                                          encoding="utf-8")
    (carpeta / "reporte.md").write_text(markdown(informe), encoding="utf-8")
    log(f"== 4. Reporte: {carpeta.relative_to(comun.RAIZ)}/reporte.md")

    # Lo que haya quedado arriba (bases que fallaron a mitad de camino); nada con --conservar
    if not args.conservar:
        for b in bases:
            try:
                b.apagar()
            except ErrorPaso as e:
                log(f"✖ apagado de {b.nombre}: {e}")
    fallidas = [b for b, r in resultado.items() if r["estado"] != "ok"]
    malos = validacion["resumen"]["fallidos"]
    log(f"FIN · carga {informe['total']['reloj_hasta_ultima_carga_s']:,.1f} s · total {total:,.1f} s · "
        f"bases con error: {fallidas or 'ninguna'} · chequeos fallidos: {malos or 'ninguno'}")
    if comun.ABORTO:
        log(f"✖ CORRIDA CORTADA POR EL VIGÍA: {comun.ABORTO}")
    return 1 if fallidas or malos or comun.ABORTO else 0


def totales(res: dict, total: float) -> dict:
    cargas = {b: r["fases"]["carga"] for b, r in res.items() if "carga" in r["fases"]}
    trabajo = ("arranque", "preparacion", "carga")
    fin_carga = max((c["hasta_s"] for c in cargas.values()), default=0)
    ultimo = max(cargas.items(), key=lambda kv: kv[1]["hasta_s"]) if cargas else (None, {})
    carga_larga = max(cargas.items(), key=lambda kv: kv[1]["segundos"]) if cargas else (None, {})
    return {
        "reloj_hasta_ultima_carga_s": fin_carga,
        "segundos_reloj_total": round(total, 1),
        "suma_segundos_carga": round(sum(c["segundos"] for c in cargas.values()), 1),
        "suma_arranque_preparacion_carga_s": round(sum(f["segundos"] for r in res.values()
                                                       for k, f in r["fases"].items() if k in trabajo), 1),
        "registros": sum(r.get("volumen", 0) for r in res.values()),
        "registros_por_segundo_reloj": round(sum(r.get("volumen", 0) for r in res.values()) / fin_carga, 1)
        if fin_carga else None,
        "termina_ultima": ultimo[0],
        "carga_mas_larga": [carga_larga[0], carga_larga[1].get("segundos")],
    }


# ---------------------------------------------------------------------------
# Reporte en markdown
# ---------------------------------------------------------------------------
def n(x) -> str:
    return f"{x:,}".replace(",", ".") if isinstance(x, int) else (f"{x:,.1f}".replace(",", "X").replace(".", ",")
                                                                  .replace("X", ".") if isinstance(x, float) else str(x))


def markdown(inf: dict) -> str:
    m, t, rec, val = inf["meta"], inf["total"], inf["recursos"], inf["validacion"]
    mi = m["memoria_inicial"]
    L = [f"# Carga masiva integrada — modo {m['modo']}" + (f" (de a {m['max_paralelo']})" if m["max_paralelo"] else ""),
         "", f"- Ejecutado: {m['fecha_inicio']} (UTC) · commit `{m['commit']}`",
         f"- Comando: `{m['comando']}`",
         f"- VM de Docker: {m['vm']['cpus']} CPUs, {m['vm']['memoria_gib']} GiB · "
         f"{rec.get('otros_contenedores')} contenedores ajenos a la prueba ocupaban hasta "
         f"{n(rec.get('mem_otros_contenedores_mib'))} MiB",
         f"- Parámetros de los cargadores: Cassandra concurrencia {m['parametros']['cassandra_concurrencia']} · "
         f"InfluxDB lote {n(m['parametros']['influx_lote'])}, hilos {m['parametros']['influx_hilos']}",
         f"- Memoria al empezar: VM {n(mi['vm_mib'])} MiB, {mi['contenedores_ajenos']} contenedores ajenos con "
         f"{n(mi['contenedores_ajenos_mib'])} MiB, RAM libre del host {n(mi['ram_libre_host_mib'])} MiB · "
         f"presupuesto para la prueba: {n(mi['presupuesto_mib']) + ' MiB' if mi['presupuesto_mib'] else 'sin control (secuencial)'}",
         f"- Orden: {' → '.join(m['orden'])}",
         "- Desde volúmenes vacíos: sí (limpieza al inicio de la corrida)"]
    if m.get("vigia"):
        L += ["", f"> **Corrida cortada por el vigía de memoria:** {m['vigia']}"]
    ins = inf.get("insumos_influxdb")
    if ins:
        L.append(f"- Insumos de InfluxDB: " + (f"generados en esta corrida ({n(ins['segundos'])} s, fuera del tiempo de carga)"
                                              if ins["generados_en_esta_corrida"] else "reutilizados (deterministas)"))
    L += ["", "## Tiempos por base", "",
          "| Base | Arranque (s) | Preparación (s) | **Carga (s)** | Carga desde → hasta (s) | Volumen | Throughput de la carga "
          "| Verificación (s) | Apagado (s) | Estado |",
          "|---|---:|---:|---:|---|---:|---:|---:|---:|---|"]
    for b, r in inf["bases"].items():
        f = r["fases"]
        c = f.get("carga", {})
        L.append(f"| {b} | {n(f.get('arranque', {}).get('segundos', '–'))} | {n(f.get('preparacion', {}).get('segundos', '–'))} | "
                 f"{n(c.get('segundos', '–'))} | {n(c.get('desde_s', '–'))} → {n(c.get('hasta_s', '–'))} | "
                 f"{n(r.get('volumen', '–'))} {r.get('unidad', '')} | {n(r.get('por_segundo', '–'))} {r.get('unidad', '')}/s | "
                 f"{n(f.get('verificacion', {}).get('segundos', '–'))} | {n(f.get('apagado', {}).get('segundos', '–'))} | "
                 f"{r['estado']} |")
    L += ["", "| Total | Valor |", "|---|---|",
          f"| **Reloj: arranque de la primera → fin de la última carga** | **{n(t['reloj_hasta_ultima_carga_s'])} s** |",
          f"| Reloj total (incluye verificación, distribución y apagado) | {n(t['segundos_reloj_total'])} s |",
          f"| Suma de las fases de carga | {n(t['suma_segundos_carga'])} s |",
          f"| Suma de arranque + preparación + carga de todas las bases | {n(t['suma_arranque_preparacion_carga_s'])} s |",
          f"| Registros cargados (de distinta naturaleza) | {n(t['registros'])} |",
          f"| Registros por segundo de reloj | {n(t['registros_por_segundo_reloj'])} |",
          f"| Última carga en terminar | {t['termina_ultima']} |",
          f"| Carga más larga | {t['carga_mas_larga'][0]} ({n(t['carga_mas_larga'][1])} s) |", ""]
    for b, r in inf["bases"].items():
        L.append(f"- **{b}**: {r.get('detalle', '')}" + (f" · {r['tasa_propia']}" if r.get("tasa_propia") else ""))
        for e in r.get("fallas", []):
            L.append(f"  - error: `{e[:600]}`")
    adm = inf.get("admisiones") or []
    if adm:
        L += ["", "### Admisión (cuándo arrancó cada base)", "",
              "| Base | Admitida en (s) | Reservado al admitirla (MiB) | Bases en curso | RAM libre del host (MiB) |",
              "|---|---:|---:|---:|---:|"]
        L += [f"| {a['base']} | {n(a['t_s'])} | {n(a['reservado_mib'])} | {a['simultaneas']} | {n(a['ram_libre_host_mib'])} |"
              for a in adm]
    L += ["", "## Recursos (docker stats durante todas las fases)", "",
          f"{rec.get('muestras')} muestras. Pico de RAM de los contenedores de la prueba: **{n(rec.get('pico_mem_prueba_mib'))} MiB**; "
          f"pico de RAM de toda la VM (prueba + ajenos): **{n(rec.get('pico_mem_total_vm_mib'))} MiB** de "
          f"{n(round(m['vm']['memoria_gib'] * 1024))} MiB; pico de CPU de la prueba: **{n(rec.get('pico_cpu_prueba_pct'))} %** "
          f"(100 % = 1 CPU, {m['vm']['cpus']} CPUs = {m['vm']['cpus'] * 100} %). RAM libre mínima del host: "
          f"**{n(rec.get('ram_libre_host_min_mib'))} MiB**.", "",
          "| Contenedor | Muestras | CPU prom. (%) | CPU máx. (%) | RAM máx. (MiB) |", "|---|---:|---:|---:|---:|"]
    for c, v in rec.get("contenedores_prueba", {}).items():
        L.append(f"| {c} | {v['muestras']} | {n(v['cpu_prom_pct'])} | {n(v['cpu_max_pct'])} | {n(v['mem_max_mib'])} |")
    L += ["", "## Validación de integridad", ""]
    if val.get("error"):
        L.append(f"✖ {val['error']}")
    rs = val.get("resumen", {})
    L += [f"{rs.get('ok', 0)} de {rs.get('chequeos', 0)} chequeos OK · fallidos: {rs.get('fallidos') or 'ninguno'} · "
          f"informativos: {rs.get('informativos') or 'ninguno'}", "",
          "| Chequeo | Esperado | Obtenido | Resultado |", "|---|---:|---:|---|"]
    for c in val.get("chequeos", []):
        L.append(f"| {c['chequeo']} | {n(c['esperado'])} | {n(c['obtenido'])} | "
                 f"{'OK' if c['ok'] is True else ('FALLA' if c['ok'] is False else c['ok'])} |")
    cr = val.get("cruces", {})
    if cr:
        L += ["", "### Referencias cruzadas", ""]
        for k, v in cr.items():
            if k.startswith("partidos_"):
                L.append(f"- `partido_id` de **{k[9:]}**: {v['partido_ids']} distintos; inexistentes en Neo4j: "
                         f"{len(v['inexistentes_en_neo4j'])} {v['inexistentes_en_neo4j'][:10] or ''}; partidos de Neo4j sin "
                         f"datos en esta base: {v['partidos_de_neo4j_sin_datos_en_esta_base']}")
        e = cr.get("equipos_mongodb_neo4j")
        if e:
            L += ["", f"**Equipos MongoDB ↔ Neo4j (hallazgo H1, medido y sin corregir)**: {e['mongodb']} en MongoDB, "
                      f"{e['neo4j']} en Neo4j, **{e['codigo_coincide']} con el mismo código** y "
                      f"**{len(e['solo_mongodb'])} que no coinciden** de cada lado.", "",
                  f"- Mismo nombre, distinto código ({len(e['mismo_nombre_distinto_codigo'])}): " +
                  ", ".join(f"{x['nombre']} {x['mongodb']}/{x['neo4j']}" for x in e["mismo_nombre_distinto_codigo"]),
                  f"- Solo en MongoDB, sin par por nombre ({len(e['sin_par_por_nombre']['mongodb'])}): " +
                  ", ".join(e["sin_par_por_nombre"]["mongodb"]),
                  f"- Solo en Neo4j, sin par por nombre ({len(e['sin_par_por_nombre']['neo4j'])}): " +
                  ", ".join(e["sin_par_por_nombre"]["neo4j"])]
    d = inf.get("distribucion") or {}
    if d:
        L += ["", "## Distribución de los datos", "", "Interpretación: `docs/distribucion_y_escalabilidad.md`. "
              "Datos completos en `reporte.json` → `distribucion`.", ""]
        L += markdown_distribucion(d)
    return "\n".join(L) + "\n"


def markdown_distribucion(d: dict) -> list[str]:
    L = []
    mg = d.get("mongodb", {})
    if "por_equipo" in mg:
        pe = mg["por_equipo"]
        L += ["### MongoDB", "", f"- Jugadores por equipo: {pe['equipos']} equipos, mín {pe['min']}, máx {pe['max']}, "
              f"prom {pe['prom']:.1f}",
              "- Por confederación: " + ", ".join(f"{c['_id']} {c['jugadores']} ({c['equipos']} eq.)" for c in mg["por_confederacion"]),
              "- Por posición: " + ", ".join(f"{p['_id']} {p['n']}" for p in mg["por_posicion"])]
        for t in mg["tamanos"]:
            L.append(f"- `{t['coleccion']}`: {n(t['documentos'])} docs, {n(t['bytes_datos'])} B de datos "
                     f"({n(t['bytes_promedio_doc'])} B/doc), {n(t['bytes_almacenados'])} B en disco, "
                     f"{t['indices']} índices ({n(t['bytes_indices'])} B)")
        L.append("")
    ne = d.get("neo4j", {})
    if "nodos_por_etiqueta" in ne:
        L += ["### Neo4j", "", "- Nodos por etiqueta: " + ", ".join(f"{e['etiqueta']} {n(e['n'])}" for e in ne["nodos_por_etiqueta"]),
              "- Relaciones por tipo: " + ", ".join(f"{r['tipo']} {n(r['n'])}" for r in ne["relaciones_por_tipo"]),
              "", "| Etiqueta | Grado mín | p50 | p99 | máx | prom |", "|---|---:|---:|---:|---:|---:|"]
        L += [f"| {g['etiqueta']} | {g['min']} | {g['p50']} | {g['p99']} | {g['max']} | {g['prom']} |" for g in ne["grados"]]
        L += ["", "- Más conectados: " + ", ".join(f"{x['etiqueta']} {x['id']} ({x['grado']})" for x in ne["mas_conectados"]),
              "- Eventos por fase: " + ", ".join(f"{x['fase']} {x['partidos']} partidos / {x['eventos']} eventos"
                                                 for x in ne["eventos_por_fase"]), ""]
    ca = d.get("cassandra", {})
    if "tablestats" in ca:
        L += ["### Cassandra", ""]
        for tabla, v in ca["tablestats"].items():
            L.append(f"- `{tabla}`: " + " · ".join(f"{k}: {x}" for k, x in v.items()))
        fp = ca["filas_por_particion"]
        L += [f"- Filas por partición (recorrido completo) `comentarios_por_partido`: {fp['particiones_comentarios_por_partido']} "
              f"particiones · {fp['comentarios_por_partido']}",
              f"- `comentarios_por_usuario`: {fp['particiones_comentarios_por_usuario']} particiones · {fp['comentarios_por_usuario']}",
              "- Particiones más grandes: " + "; ".join(f"{p[0]} {p[1]} bucket {p[2]} = {n(p[3])}" for p in ca["top_particiones"]),
              f"- Comentarios por partido: {ca['comentarios_por_partido']}",
              "- Más comentados: " + ", ".join(f"{k} {n(v)}" for k, v in ca["partidos_mas_comentados"]),
              "", "```", ca["tablehistograms"]["comentarios_por_partido"], "```", ""]
    rd = d.get("redis", {})
    if "por_tipo" in rd:
        L += ["### Redis", "", "- Por tipo (`--memkeys`): " + ", ".join(f"{k} {n(v['claves'])} claves / {n(v['bytes'])} B"
                                                                    for k, v in rd["por_tipo"].items()),
              "- Por prefijo: " + ", ".join(f"`{k}` {n(v)}" for k, v in rd["por_prefijo"].items()),
              "- Memoria: " + ", ".join(f"{k}={v}" for k, v in rd["info"].items()),
              "- Bytes por clave (MEMORY USAGE): " + ", ".join(f"{k} {v}" for k, v in rd["bytes_por_clave_muestra"].items()), ""]
    ix = d.get("influxdb", {})
    if "series_por_tabla" in ix:
        L += ["### InfluxDB", "", "- Series por tabla: " + ", ".join(f"{k} {n(v)}" for k, v in ix["series_por_tabla"].items())]
        for t, v in ix["puntos_por_partido"].items():
            L.append(f"- Puntos por partido en `{t}`: " + ", ".join(f"{k} {n(x)}" for k, x in v.items() if k != "top")
                     + " · mayores: " + ", ".join(f"{a} {n(b)}" for a, b in v["top"]))
        L += ["- Partidos por audiencia: " + ", ".join(f"{k} {v}" for k, v in ix["partidos_por_audiencia"].items()),
              f"- Disco: {ix['disco']}", ""]
    for b, v in d.items():
        if "error" in v:
            L.append(f"- ✖ distribución de {b}: {v['error']}")
    return L


if __name__ == "__main__":
    sys.exit(main())
