#!/usr/bin/env bash
# ============================================================
#  Fixture 2030 — Hito 10 · API REST integrada
#  ARCHIVO: scripts/iniciar_api.sh
#  PROPÓSITO: levantar la API en la notebook (RF1/RF16).
#    1. verifica el entorno virtual .venv; si falta lo crea con `uv`
#       (o con `python3.12 -m venv`) e instala requirements.txt;
#    2. carga `.env` si existe (ignorado por git; ver .env.example);
#    3. ejecuta `uvicorn app.main:app --host $API_HOST --port $API_PORT`.
#  USO:  bash scripts/iniciar_api.sh            (desde fixture2030-hito10-api/)
#        API_PORT=8001 bash scripts/iniciar_api.sh
#  La API arranca aunque alguna base esté caída: esa fuente responde 503
#  hasta que vuelva (ver GET /health/dependencias).
#  RNF7: no imprime credenciales; el token de InfluxDB lo lee la API del archivo local.
# ============================================================
set -euo pipefail
source "$(dirname "$0")/_comun.sh"
cd "$API_DIR"

PY="$API_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "No existe .venv: creándolo…"
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 .venv
    uv pip install --python "$PY" -r requirements.txt
  else
    PYTHON_BASE="$(command -v python3.12 || command -v python3 || true)"
    if [ -z "$PYTHON_BASE" ]; then
      echo "FALLA: no hay uv ni python3.12 en el PATH." >&2
      exit 1
    fi
    "$PYTHON_BASE" -m venv .venv
    "$PY" -m pip install --upgrade pip >/dev/null
    "$PY" -m pip install -r requirements.txt
  fi
fi

if ! "$PY" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  echo "Faltan dependencias en .venv: instalando requirements.txt…"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PY" -r requirements.txt
  else
    "$PY" -m pip install -r requirements.txt
  fi
fi

[ -f .env ] && echo "Usando .env local." || echo "Sin .env: valores por defecto (ver .env.example)."
echo "API en http://${API_HOST}:${API_PORT}  (docs: /docs · salud: /health/dependencias)"
exec "$PY" -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT"
