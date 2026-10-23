"""Matriz de conectividad de una corrida (RF16, RNF9, RNF10, RNF18).

Lee los JSONL de una carpeta de corrida y escribe `matriz.md` (+ `matriz.json`):
una fila por dependencia con el estado, el resultado de cada capa, latencias,
controles negativos, evidencia y diagnóstico.

Estados (RNF9), en este orden de precedencia:
  NO_CONFIGURADO  el producto no forma parte del entorno (todas sus filas N/C);
  NO_DISPONIBLE   alguna prueba de base falló (se nombra la PRIMERA capa que falló);
  DEGRADADO       ninguna falló pero alguna dio WARN (las "observaciones" de
                  higiene de configuración, como una credencial de desarrollo
                  pública, se listan aparte y no degradan la conectividad);
  NO_PROBADO      no se incluyó en la corrida, o faltan capas clave (protocolo u
                  operación) por SKIP: no se sabe;
  DESCONOCIDO     el diagnóstico se ejecutó pero no pudo terminar ni clasificar;
  DISPONIBLE      todas las pruebas ejecutadas dieron OK (o N/C donde no aplica).

Las filas "control: …", "escenario: …" y las de fallas controladas son
diagnósticos provocados: no cambian el estado, se cuentan aparte.

    python3 scripts/generar_matriz.py [CARPETA_DE_CORRIDA]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registro import CAPAS, EVIDENCIA_DIR, ahora, commit_actual, leer_corrida, origen_ejecucion, ruta_publica  # noqa: E402

PRODUCTOS = ["mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris", "api"]
SIMBOLO = {"OK": "OK", "FAIL": "**FAIL**", "WARN": "WARN", "SKIP": "SKIP", "N/C": "N/C", None: "—"}
SIGUIENTE_PASO = {
    "configuracion": "corregir la variable indicada (config/configuracion.env o entorno) y repetir --config",
    "resolucion": "revisar el nombre del host desde el mismo entorno que la API (localhost vs nombre de servicio)",
    "tcp": "revisar que el contenedor esté corriendo y el puerto publicado (`docker ps`, `docker compose ps`)",
    "protocolo": "el puerto responde pero no habla el protocolo esperado: ¿puerto equivocado? revisar logs del contenedor",
    "autenticacion": "credencial rechazada: revisar usuario/contraseña/token sin imprimirlos",
    "autorizacion": "identidad válida sin permiso: revisar roles/ACL del usuario",
    "contexto": "database/keyspace/tabla/namespace inexistente: revisar el nombre y la carga del hito",
    "operacion": "la lectura mínima falló: revisar datos de demo, filtros y modelo",
    "api": "el cliente nativo funciona pero la API no: revisar .env de la API, adaptador y log con el requestId",
}


def es_control(f: dict) -> bool:
    p = str(f.get("prueba", ""))
    return p.startswith(("control:", "escenario:", "[")) or f.get("_archivo") == "resultados_falla_controlada"


def peor(resultados: list[str]) -> str | None:
    for r in ("FAIL", "WARN", "OK", "N/C", "SKIP"):
        if r in resultados:
            return r
    return None


def estado_de(filas: list[dict]) -> tuple[str, str, str | None]:
    """(estado, diagnóstico, capa_que_falla)"""
    base = [f for f in filas if not es_control(f)]
    if not base:
        return "NO_PROBADO", "no incluido en esta corrida (filtro --producto o modo parcial)", None
    if all(f["capa"] == "configuracion" for f in base) and any(
            f["prueba"].startswith("API vs hito") for f in base):
        # En una corrida filtrada (--producto X) los demás productos sólo aparecen por la
        # comparación de configuración API vs. hito: no se probó red, protocolo ni operación.
        return "NO_PROBADO", "sólo se comparó su configuración (corrida filtrada con --producto)", None
    roto = next((f for f in base if f["prueba"] == "ejecución del diagnóstico"), None)
    if roto:
        return "DESCONOCIDO", f"el diagnóstico no pudo terminar: {roto['detalle']}", None
    res = [f["resultado"] for f in base]
    if all(r in ("N/C", "OK") for r in res) and "N/C" in res and not any(
            f["resultado"] == "OK" and f["capa"] in ("protocolo", "operacion") for f in base):
        return "NO_CONFIGURADO", "fuera del entorno de prueba: no se inventan resultados", None
    for capa in CAPAS:
        fallo = next((f for f in base if f["capa"] == capa and f["resultado"] == "FAIL"), None)
        if fallo:
            return "NO_DISPONIBLE", f"falla en la capa **{capa}**: {fallo['detalle']}", capa
    aviso = next((f for f in base if f["resultado"] == "WARN" and not f.get("observacion")), None)
    if aviso:
        return "DEGRADADO", f"{aviso['capa']}: {aviso['detalle']}", aviso["capa"]
    claves = {f["capa"] for f in base if f["resultado"] == "OK"}
    if "SKIP" in res and not ({"protocolo", "operacion"} <= claves or "api" in claves):
        skip = next(f for f in base if f["resultado"] == "SKIP")
        return "NO_PROBADO", f"{skip['capa']}: {skip['detalle']}", None
    return "DISPONIBLE", "todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento)", None


CLIS = ("mongosh", "cypher-shell", "cqlsh", "redis-cli", "influxdb3")


def latencia(filas: list[dict], capa: str) -> str:
    """Rango de latencias OK de la capa. Excluye los CLI (incluyen el arranque del proceso)."""
    vals = [f["latencia_ms"] for f in filas if f["capa"] == capa and f.get("latencia_ms") is not None
            and not es_control(f) and f["resultado"] == "OK" and not str(f["prueba"]).startswith(CLIS)]
    if not vals:
        return "—"
    fmt = (lambda v: f"{v:.1f}" if v < 10 else f"{v:.0f}")  # noqa: E731
    lo, hi = min(vals), max(vals)
    return fmt(lo) if fmt(lo) == fmt(hi) else f"{fmt(lo)}–{fmt(hi)}"


def main() -> int:
    if len(sys.argv) > 1:
        d = Path(sys.argv[1])
    else:
        corridas = sorted((EVIDENCIA_DIR / "corridas").glob("*"))
        if not corridas:
            print("no hay corridas", file=sys.stderr)
            return 1
        d = corridas[-1]
    filas = leer_corrida(d)
    ts = min((f["ts"] for f in filas), default=ahora())
    commit = next((f["commit"] for f in filas), commit_actual())
    entorno = next((f["entorno"] for f in filas), "-")
    salida = [f"# Matriz de conectividad — corrida `{d.name}`", "",
              f"- Fecha (UTC): {ts} → {max((f['ts'] for f in filas), default=ts)}",
              f"- Commit: `{commit}` · Entorno: {entorno} · Origen: {next((f['origen'] for f in filas), origen_ejecucion())}",
              f"- Archivos: " + ", ".join(f"[`{p.name}`]({p.name})" for p in sorted(d.glob('*.md')) if p.name != "matriz.md"),
              "- OK = esa prueba concreta funcionó en ese momento; no es garantía de rendimiento ni de disponibilidad permanente (RNF17).",
              "", "| Dependencia | Estado | Config | DNS | TCP | Protocolo | Autent. | Autoriz. | Contexto | Operación | API | "
              "ms TCP | ms operación (driver) | ms API | Controles | Diagnóstico | Siguiente paso | Observaciones (no cambian el estado) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|"]
    resumen = []
    for prod in PRODUCTOS:
        fp = [f for f in filas if f["producto"] == prod]
        if not fp and prod == "api":
            continue
        estado, diag, capa = estado_de(fp)
        celdas = []
        for c in CAPAS:
            celdas.append(SIMBOLO[peor([f["resultado"] for f in fp if f["capa"] == c and not es_control(f)
                                        and not f.get("observacion")])])
        ctrl = [f for f in fp if es_control(f)]
        obs = "; ".join(f"{f['prueba']}: {f['detalle']}" for f in fp
                        if f.get("observacion") and f["resultado"] == "WARN").replace("|", "/") or "—"
        ctrl_ok = sum(1 for f in ctrl if f["resultado"] == "OK")
        paso = SIGUIENTE_PASO.get(capa or "", "—") if estado in ("NO_DISPONIBLE", "DEGRADADO") else (
            "ninguno: IRIS está fuera de la arquitectura vigente" if estado == "NO_CONFIGURADO"
            else "instalar la herramienta o completar la configuración y repetir" if estado == "NO_PROBADO" else "—")
        salida.append(f"| **{prod}** | **{estado}** | " + " | ".join(celdas) +
                      f" | {latencia(fp, 'tcp')} | {latencia(fp, 'operacion')} | {latencia(fp, 'api')} | "
                      f"{ctrl_ok}/{len(ctrl)} | {str(diag).replace('|', '/')} | {paso} | {obs} |")
        resumen.append({"producto": prod, "estado": estado, "diagnostico": diag, "capa": capa,
                        "capas": dict(zip(CAPAS, celdas)), "controles_ok": ctrl_ok, "controles": len(ctrl)})
    otros = [f for f in filas if f["producto"] not in PRODUCTOS]
    if otros:
        salida += ["", f"Escenarios de red provocados (§5.3): {sum(f['resultado'] == 'OK' for f in otros)}/{len(otros)} "
                       "se comportaron como se esperaba (ver `resultados_tcp.md`)."]
    fallidos = [f for f in filas if es_control(f) and f["resultado"] in ("FAIL", "WARN")]
    if fallidos:
        salida += ["", "## Controles con resultado inesperado", "", "| Producto | Prueba | Detalle |", "|---|---|---|"]
        salida += [f"| {f['producto']} | {f['prueba']} | {f['detalle']} |" for f in fallidos]
    totales = {r: sum(1 for f in filas if f["resultado"] == r) for r in ("OK", "WARN", "FAIL", "SKIP", "N/C")}
    salida += ["", "Totales de la corrida: " + " · ".join(f"{k} {v}" for k, v in totales.items()),
               "", "SKIP = prueba no ejecutada por falta de herramienta o configuración; NO significa producto caído. "
                   "N/C = la capa no aplica en este entorno (p. ej. laboratorio sin autenticación) o el producto no está configurado."]
    (d / "matriz.md").write_text("\n".join(salida) + "\n", encoding="utf-8")
    (d / "matriz.json").write_text(json.dumps({"corrida": d.name, "commit": commit, "desde": ts, "dependencias": resumen,
                                               "totales": totales}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in resumen:
        print(f"{r['producto']:<10} {r['estado']:<15} {r['diagnostico'][:90]}")
    print("Totales: " + " · ".join(f"{k} {v}" for k, v in totales.items()))
    print(f"Matriz: {ruta_publica(d / 'matriz.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
