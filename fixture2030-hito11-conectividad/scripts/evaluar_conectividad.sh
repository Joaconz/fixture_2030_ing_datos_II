#!/usr/bin/env bash
# ============================================================
#  Fixture 2030 — Hito 11 · Evaluación de la conectividad
#  ARCHIVO: scripts/evaluar_conectividad.sh   (punto de entrada, §5.8)
#  Adapta el script de la Clase 12 a la API real del Hito 10 y separa, en
#  módulos, cada capa de diagnóstico (RNF2, RNF15):
#
#    --config    capa 0   prueba_config.py           variables, origen, secretos sin mostrar, API vs hito
#    --tcp       capa 1-2 prueba_tcp.py              resolución + TCP (refused ≠ timeout ≠ no resuelto)
#    --nativos   capa 3-6 prueba_drivers.py          drivers de la API: protocolo, identidad, contexto, operación
#                         prueba_clientes_nativos.sh mongosh · cypher-shell · cqlsh · redis-cli · influxdb3
#    --api       capa API prueba_api.py              rutas del Hito 10, status, request-id, log asociado
#    --falla     §5.7     prueba_falla_controlada.py stop/start, pause/unpause y configuración incorrecta
#    --matriz             generar_matriz.py          matriz de la corrida (estado por dependencia)
#    (sin modo)           --config --tcp --nativos --api --matriz   (completo, sin fallas provocadas)
#
#  Opciones:
#    --producto X     repetible: mongodb neo4j cassandra redis influxdb iris (RNF13: por producto)
#    --escenarios     agrega a --tcp los escenarios de §5.3 (puerto incorrecto, host no resuelto, timeout,
#                     localhost dentro de un contenedor, bind a 127.0.0.1)
#    --api-url URL    API a evaluar (por defecto API_URL de la configuración)
#    --log ARCHIVO    log JSON de esa API (para asociar cada request con sus líneas de log)
#    --corrida NOMBRE carpeta de evidencia (por defecto <fecha>_<modo>); permite sumar módulos a una corrida
#    --limpiar        borra SOLO las salidas crudas locales (docs/evidencia/crudo/); nunca datos ni volúmenes
#
#  Variables externas: config/configuracion-ejemplo.env < config/configuracion.env < entorno.
#  Salida: consola + docs/evidencia/corridas/<corrida>/*.md|jsonl (redactados, RNF8).
#  Exit code: 0 aunque haya FAIL (como el script de la clase: se necesita el diagnóstico
#  completo); con ESTRICTO=1 sale 1 si hubo algún FAIL (para CI).
# ============================================================
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HITO="$(cd "$DIR/.." && pwd)"
PY="${PY:-python3}"

MODOS=(); PRODUCTOS=(); ESCENARIOS=0; API_URL_ARG=""; LOG_ARG=""; CORRIDA=""
while [ $# -gt 0 ]; do
  case "$1" in
    --config|--tcp|--nativos|--api|--falla|--matriz) MODOS+=("${1#--}") ;;
    --tcp-only) MODOS+=(tcp) ;; --native-only) MODOS+=(nativos) ;; --api-only) MODOS+=(api) ;;   # nombres de la Clase 12
    --producto) PRODUCTOS+=("$2"); shift ;;
    --escenarios) ESCENARIOS=1 ;;
    --api-url) API_URL_ARG="$2"; shift ;;
    --log) LOG_ARG="$2"; shift ;;
    --corrida) CORRIDA="$2"; shift ;;
    --limpiar) rm -rf "$HITO/docs/evidencia/crudo"; echo "Borrado docs/evidencia/crudo/ (salidas crudas locales)."; exit 0 ;;
    -h|--help) sed -n '2,33p' "$0" | sed 's/^#  \{0,1\}//'; exit 0 ;;
    *) echo "Argumento desconocido: $1 (usar --help)" >&2; exit 2 ;;
  esac
  shift
done
[ "${#MODOS[@]}" -eq 0 ] && MODOS=(config tcp nativos api matriz)

cfg() { "$PY" "$DIR/registro.py" config "$1"; }
API_DIR="$(cfg API_DIR)"
PY_API="${PY_API:-$API_DIR/.venv/bin/python}"
API_URL="${API_URL_ARG:-${API_URL:-$(cfg API_URL)}}"
export API_URL

etiqueta="$(IFS=-; echo "${MODOS[*]}")"
[ "${#PRODUCTOS[@]}" -gt 0 ] && etiqueta="$etiqueta-$(IFS=-; echo "${PRODUCTOS[*]}")"
CORRIDA="${CORRIDA:-$(date -u +%Y%m%d-%H%M%S)_$etiqueta}"
export CORRIDA_DIR="$HITO/docs/evidencia/corridas/$CORRIDA"
mkdir -p "$CORRIDA_DIR"

args_producto=(); for p in "${PRODUCTOS[@]+"${PRODUCTOS[@]}"}"; do args_producto+=(--producto "$p"); done
seccion() { printf '\n=== %s ===\n' "$1"; }

printf 'Fixture 2030 — Hito 11 · evaluación de conectividad\n'
printf 'Inicio (UTC): %s · modos: %s · productos: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${MODOS[*]}" \
  "${PRODUCTOS[*]:-todos}"
printf 'Origen: notebook (mismo entorno que la API) · API: %s · evidencia: %s\n' "$API_URL" "${CORRIDA_DIR#$HITO/}"

if [ ! -x "$PY_API" ]; then
  echo "AVISO: no existe $PY_API (el .venv de la API). Las pruebas con drivers darán SKIP."
  echo "       Crear con: bash $API_DIR/scripts/iniciar_api.sh (o uv venv + uv pip install -r requirements.txt)"
  PY_API="$PY"
fi

for modo in "${MODOS[@]}"; do
  case "$modo" in
    config)
      seccion "Capa 0 · configuración"
      prods=("${args_producto[@]+"${args_producto[@]}"}"); [ "${#PRODUCTOS[@]}" -gt 0 ] && prods+=(--producto api)
      "$PY_API" "$DIR/prueba_config.py" "${prods[@]+"${prods[@]}"}" ;;
    tcp)
      seccion "Capas 1-2 · resolución y TCP"
      esc=(); [ "$ESCENARIOS" = 1 ] && esc=(--escenarios)
      "$PY" "$DIR/prueba_tcp.py" "${args_producto[@]+"${args_producto[@]}"}" "${esc[@]+"${esc[@]}"}" ;;
    nativos)
      seccion "Capas 3-6 · drivers de la API"
      "$PY_API" "$DIR/prueba_drivers.py" "${args_producto[@]+"${args_producto[@]}"}"
      seccion "Capas 3-6 · clientes nativos (CLI)"
      PY_API="$PY_API" bash "$DIR/prueba_clientes_nativos.sh" "${PRODUCTOS[@]+"${PRODUCTOS[@]}"}" ;;
    api)
      seccion "Capa API · rutas del Hito 10"
      logs=(); [ -n "$LOG_ARG" ] && logs=(--log "$LOG_ARG")
      "$PY" "$DIR/prueba_api.py" --api-url "$API_URL" "${args_producto[@]+"${args_producto[@]}"}" "${logs[@]+"${logs[@]}"}" ;;
    falla)
      seccion "Fallas controladas (§5.7)"
      logs=(); [ -n "$LOG_ARG" ] && logs=(--log "$LOG_ARG")
      fuentes=("${PRODUCTOS[@]+"${PRODUCTOS[@]}"}"); [ "${#fuentes[@]}" -eq 0 ] && fuentes=(redis)
      for f in "${fuentes[@]}"; do
        [ "$f" = iris ] && { echo "iris: NOT_CONFIGURED, no se provoca falla"; continue; }
        "$PY_API" "$DIR/prueba_falla_controlada.py" detener "$f" "${logs[@]+"${logs[@]}"}"
      done
      "$PY_API" "$DIR/prueba_falla_controlada.py" pausar influxdb "${logs[@]+"${logs[@]}"}"
      "$PY_API" "$DIR/prueba_falla_controlada.py" config ;;
    matriz)
      seccion "Matriz de conectividad"
      "$PY" "$DIR/generar_matriz.py" "$CORRIDA_DIR" ;;
  esac
done

seccion "Resumen"
"$PY" - "$CORRIDA_DIR" <<'EOF'
import json, sys
from pathlib import Path
filas = []
for a in Path(sys.argv[1]).glob("*.jsonl"):
    if a.stem.endswith("_logs"):
        continue
    filas += [json.loads(l) for l in a.read_text(encoding="utf-8").splitlines() if l.strip()]
tot = {r: sum(f["resultado"] == r for f in filas) for r in ("OK", "WARN", "FAIL", "SKIP", "N/C")}
print(f"Total: {len(filas)} | " + " | ".join(f"{k}: {v}" for k, v in tot.items()))
for f in filas:
    if f["resultado"] == "FAIL":
        print(f"  FAIL {f['producto']}/{f['capa']}: {f['prueba']} → {f['detalle'][:110]}")
Path(sys.argv[1], ".fallas").write_text(str(tot["FAIL"]))
EOF
printf 'Fin (UTC): %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat <<'TXT'

Interpretación: OK = esa prueba concreta funcionó ahora; no garantiza rendimiento ni disponibilidad
permanente (RNF17). SKIP = no se ejecutó por falta de herramienta o configuración: NO es "producto caído".
N/C = la capa no aplica en este entorno o el producto no está configurado (IRIS).
TXT
fallas="$(cat "$CORRIDA_DIR/.fallas" 2>/dev/null || echo 0)"; rm -f "$CORRIDA_DIR/.fallas"
if [ "${ESTRICTO:-0}" = 1 ] && [ "$fallas" -gt 0 ]; then exit 1; fi
exit 0
