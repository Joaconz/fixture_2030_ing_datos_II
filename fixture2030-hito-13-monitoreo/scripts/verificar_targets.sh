#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 13 · estado de cada target y de cada base (§5.2).
#  USO: bash scripts/verificar_targets.sh            (muestra el estado)
#       bash scripts/verificar_targets.sh --guardar  (además lo deja en evidencia/)
#  Fuente: API HTTP de Prometheus (/api/v1/targets y probe_success). Sale con
#  código 1 si algún target está DOWN, para poder usarlo antes de la demo.
# ============================================================================
. "$(dirname "$0")/_comun.sh"

curl -fsS -m 3 "$PROM_URL/-/ready" >/dev/null 2>&1 || falla "Prometheus no responde en $PROM_URL: correr scripts/iniciar_monitoreo.sh"

informe() {
  echo "# Targets de Prometheus — $(ahora_utc)"
  echo
  echo "Fuente: \`GET $PROM_URL/api/v1/targets\` y \`probe_success{job=\"salud-bases\"}\`. Commit: \`$(git -C "$H13_DIR" rev-parse --short HEAD 2>/dev/null || echo '-')\`."
  echo
  echo "## Targets (lo que Prometheus pudo leer)"
  echo
  curl -fsS "$PROM_URL/api/v1/targets?state=active" | python3 -c '
import json, sys
print("| job | base / capa | instance | estado | último scrape | error |")
print("|---|---|---|---|---|---|")
for t in sorted(json.load(sys.stdin)["data"]["activeTargets"], key=lambda t: (t["labels"]["job"], t["labels"].get("base", ""))):
    l = t["labels"]
    err = (t.get("lastError") or "").replace("|", "/")[:90]
    print(f"| {l[\"job\"]} | {l.get(\"base\") or l.get(\"capa\") or \"-\"} | {l[\"instance\"]} | {t[\"health\"].upper()} | {t[\"lastScrape\"][:19]} | {err} |")'
  echo
  echo "## Disponibilidad por base (sonda del blackbox-exporter)"
  echo
  echo "| base | probe_success |"
  echo "|---|---|"
  prom_query 'probe_success{job="salud-bases"}' | sed -E 's/.*base=([a-z0-9]+).* ([01])$/| \1 | \2 |/'
  echo
  echo "## Alertas activas"
  echo
  local a; a="$(prom_query 'ALERTS' || true)"
  [ -n "$a" ] && echo "$a" | sed 's/^/- /' || echo "Ninguna."
}

salida="$(informe)"
echo "$salida"

if [ "${1:-}" = "--guardar" ]; then
  mkdir -p "$EVID"
  archivo="$EVID/prometheus_targets_$(sello).md"
  echo "$salida" > "$archivo"
  echo; echo "Guardado en ${archivo#$REPO_DIR/}"
fi

echo "$salida" | grep -q '| DOWN |' && { echo; echo "Hay targets DOWN: ver la columna error y docs/limitaciones_y_evidencia.md §Investigar un target DOWN."; exit 1; }
exit 0
