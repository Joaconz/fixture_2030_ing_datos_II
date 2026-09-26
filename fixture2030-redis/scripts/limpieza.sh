#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · LIMPIEZA OPCIONAL POR PREFIJO (RNF8)
#  Uso (dentro del contenedor):  docker compose exec -T redis sh /scripts/limpieza.sh [prefijo]
#  Sin argumento borra TODO lo del módulo (f30:*). Usa SCAN (cursor, no bloquea) + UNLINK
#  (libera en segundo plano). Nunca KEYS ni FLUSHALL.
#  Las Functions NO se borran (viven aparte del keyspace).
# ============================================================
PREFIJO=${1:-f30:}
echo "Borrando claves con prefijo '$PREFIJO' (SCAN + UNLINK)..."
redis-cli --scan --pattern "${PREFIJO}*" | xargs -r -n 500 redis-cli UNLINK > /dev/null
echo "DBSIZE restante: $(redis-cli DBSIZE)"
