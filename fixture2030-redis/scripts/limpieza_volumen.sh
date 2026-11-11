#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · LIMPIEZA DE LA CARGA DE VOLUMEN (RNF8)
#  Uso (dentro del contenedor):  docker compose exec -T redis sh /scripts/limpieza_volumen.sh
#  Borra sólo lo de carga_volumen.sh, por prefijo: SCAN (cursor, no bloquea) + UNLINK
#  (libera en segundo plano). Nunca KEYS ni FLUSHALL. La muestra (USR-0…, demo-ses-…)
#  no coincide con ningún patrón: queda intacta.
# ============================================================
for P in 'f30:ses:vol-ses-*' 'f30:usr:USR-1??????:sesiones' 'f30:cache:usuario:USR-1??????:perfil'; do
  B=$(redis-cli --scan --count 1000 --pattern "$P" \
      | awk '{ k = k " " $0; n++ } n == 500 { print "UNLINK" k; k = ""; n = 0 } END { if (n) print "UNLINK" k }' \
      | redis-cli | awk '{ s += $1 } END { print s + 0 }')
  echo "borradas $B claves con patrón '$P'"
done
echo "DBSIZE restante: $(redis-cli DBSIZE)"
