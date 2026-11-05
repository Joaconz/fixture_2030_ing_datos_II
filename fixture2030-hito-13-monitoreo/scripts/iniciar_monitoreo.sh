#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 13 · levanta Prometheus, Grafana y los exporters (RF1).
#  USO: bash scripts/iniciar_monitoreo.sh
#  No levanta las bases ni la API: cada módulo se arranca desde su carpeta
#  (ver README §"Levantar la plataforma"). Lo que esté apagado aparece DOWN.
# ============================================================================
. "$(dirname "$0")/_comun.sh"

echo "== 1. Carpetas de datos (volúmenes nombrados respaldados por ~/docker/data)"
mkdir -p "${PROMETHEUS_DATA_DIR:-$HOME/docker/data/prometheus}" "${GRAFANA_DATA_DIR:-$HOME/docker/data/grafana}"

echo "== 2. docker compose up -d"
( cd "$H13_DIR" && docker compose up -d )

echo "== 3. Esperando a Prometheus y Grafana"
esperar_url "$PROM_URL/-/ready" 60 || falla "Prometheus no respondió en 60 s (docker logs fixture2030-prometheus)"
esperar_url "$GRAFANA_URL/api/health" 90 || falla "Grafana no respondió en 90 s (docker logs fixture2030-grafana)"

echo
echo "Prometheus  $PROM_URL           (Status → Targets, Alerts)"
echo "Grafana     $GRAFANA_URL           dashboard 'Fixture 2030 — Monitoreo'"
echo
docker ps --format '{{.Names}}' | grep -qx fixture2030-cassandra-jmx-agent \
  || docker inspect fixture2030-cassandra --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -q '^JVM_EXTRA_OPTS=-javaagent' \
  || echo "Aviso: Cassandra no tiene el agente JMX (target 'cassandra' DOWN). Ver fixture2030-cassandra/docker-compose.monitoreo.yml."
echo "Siguiente: bash scripts/verificar_targets.sh"
