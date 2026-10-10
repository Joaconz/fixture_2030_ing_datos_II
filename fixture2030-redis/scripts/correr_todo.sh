#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · EJECUCIÓN COMPLETA Y REGISTRO DE EVIDENCIA (RF13)
#  Uso (desde fixture2030-redis/):  sh scripts/correr_todo.sh
#  Deja la salida de cada etapa en docs/evidencia/NN_*.txt. Repetible.
# ============================================================
set -e
cd "$(dirname "$0")/.."
EV=docs/evidencia
RC="docker compose exec -T redis"
run() { # run <archivo .redis> -> ejecuta filtrando comentarios (redis-cli no los admite)
  $RC sh -c "grep -v '^#' /scripts/$1 | redis-cli"
}

mkdir -p "${REDIS_DATA_DIR:-$HOME/docker/data/redis}"   # el volumen nombrado exige que la carpeta exista (RNF2)
docker compose up -d --wait > /dev/null
echo "Versión: $($RC redis-cli INFO server | grep '^redis_version:' | tr -d '\r') | $(date -u +%Y-%m-%dT%H:%M:%SZ)"

$RC redis-cli CONFIG RESETSTAT > /dev/null   # estadísticas limpias: la evidencia empieza de cero

{ echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; run inicializacion.redis; }  > $EV/01_inicializacion.txt
{ echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; $RC sh /scripts/carga_muestra.sh; } > $EV/02_carga_muestra.txt
{ echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; run sesiones.redis; }        > $EV/03_sesiones.txt
{ echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; run cache.redis; }           > $EV/04_cache.txt
{ echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; run concurrencia.redis; $RC sh /scripts/concurrencia_paralela.sh 20; } > $EV/05_concurrencia.txt
sh scripts/benchmark.sh > $EV/06_benchmark.txt
{ echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; $RC sh /scripts/memoria_prueba.sh; } > $EV/07_memoria.txt
# la prueba de memoria degrada la muestra: se recarga y se miden métricas sobre el estado sano
$RC sh /scripts/carga_muestra.sh > /dev/null
{ echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; run metricas.redis; }        > $EV/08_metricas.txt

# Persistencia: volumen nombrado + reinicio + down/up sin -v (ver verificar_persistencia.sh)
sh scripts/verificar_persistencia.sh > $EV/09_persistencia.txt
echo "Evidencia escrita en $EV/"
