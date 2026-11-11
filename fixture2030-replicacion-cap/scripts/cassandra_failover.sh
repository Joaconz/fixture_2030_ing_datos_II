#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Replicación y CAP · Cassandra: un nodo caído y niveles de
#  consistencia ONE / QUORUM / ALL
#  USO: bash scripts/cassandra_failover.sh      (después de cassandra_iniciar.sh)
#
#  Con RF=3 cada partición tiene 3 réplicas (cas1, cas2, cas3).
#    ONE    = 1 réplica responde · QUORUM = 2 de 3 · ALL = las 3
#  1. Con los 3 nodos arriba: escritura y lectura con cada nivel.
#  2. `docker stop fixture2030-rep-cas3` y, con cas1 como coordinador, otra vez
#     escritura y lectura con cada nivel: ONE y QUORUM siguen, ALL no.
#  3. Las escrituras aceptadas mientras cas3 estaba caído quedan como HINTS en
#     el coordinador (archivos en /var/lib/cassandra/hints de cas1).
#  4. `docker start`: cas3 vuelve, el coordinador le entrega los hints
#     (hinted handoff) y ALL vuelve a funcionar.
#  Al final borra las filas de prueba (CONSISTENCY ALL). No borra volúmenes.
# ============================================================================
. "$(dirname "$0")/_comun.sh"
evidencia cassandra_failover "bash scripts/cassandra_failover.sh"
C1=fixture2030-rep-cas1; C3=fixture2030-rep-cas3
trap 'docker ps --format "{{.Names}}" | grep -qx $C3 || docker start $C3 >/dev/null 2>&1 || true' EXIT

ts_de() { case $1 in ONE) echo "2030-06-09 13:01:00.000+0000" ;; QUORUM) echo "2030-06-09 13:02:00.000+0000" ;; ALL) echo "2030-06-09 13:03:00.000+0000" ;; esac; }

# matriz ETIQUETA — escribe una fila y la lee con cada nivel, coordinador cas1.
matriz() {
  local cl id ts res
  printf '   %-8s %-62s %s\n' "nivel" "escritura" "lectura de esa fila"
  for cl in ONE QUORUM ALL; do
    id="PAR-A-1-REP-$1-$cl"; ts="$(ts_de $cl)"
    if res="$(insertar_comentario $C1 $cl "$id" "$ts" "prueba $1 CL=$cl")"; then res="OK"; else res="FALLA"; ERRORES="$ERRORES
     escritura $cl: $(motivo "$res")"; fi
    printf '   %-8s %-12s ' "$cl" "$res"
    if res="$(leer_comentario $C1 $cl "$id" "$ts")"; then
      echo "OK ($(echo "$res" | grep -E '^ +[0-9]+$' | tr -d ' ') fila)"
    else
      echo "FALLA"; ERRORES="$ERRORES
     lectura   $cl: $(motivo "$res")"
    fi
  done
  [ -z "$ERRORES" ] || printf "   errores que devolvió Cassandra:$ERRORES
"
}

titulo "Anillo antes de la prueba"
nodetool $C1 status "$KS" | grep -E '^UN|^DN' | sed 's/^/   /'

titulo "1. Los 3 nodos arriba (coordinador cas1)"
matriz arriba

titulo "2. docker stop $C3"
IP3="$(ip_de $C3)"
dk stop $C3 >/dev/null
echo "   cas1 ve a cas3 ($IP3) DN (caído) a los $(esperar_estado_cas $C1 "$IP3" DN 120) s de que terminó docker stop"
nodetool $C1 status "$KS" | grep -E '^UN|^DN' | sed 's/^/   /'
echo
matriz caido

titulo "3. Hints guardados en el coordinador (cas1) para la réplica caída"
sleep 11   # hints_flush_period = 10 s: el hint pasa de memoria al archivo
echo "   archivos en /var/lib/cassandra/hints de cas1:"
hints_en_disco $C1

titulo "4. docker start $C3 — vuelta y hinted handoff"
DESDE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
dk start $C3 >/dev/null
T0=$(date +%s)
esperar_healthy $C3 400 || falla "$C3 no volvió"
echo "   cas3 acepta CQL a los $(( $(date +%s) - T0 )) s del docker start"
echo "   cas1 lo ve UN $(esperar_estado_cas $C1 "$(ip_de $C3)" UN 120) s después"
echo "   entrega del hint (log de cas1), contado desde que cas3 está UN:"
echo "     $(esperar_log $C1 "$DESDE" 'Finished hinted handoff' 180)"
echo "   archivos de hints que quedan en cas1:"
hints_en_disco $C1

titulo "5. Los 3 nodos arriba otra vez (coordinador cas1)"
matriz vuelta

titulo "Limpieza de las filas de prueba (CONSISTENCY ALL)"
QUEDAN=0
for etapa in arriba caido vuelta; do for cl in ONE QUORUM ALL; do
  cql $C1 ALL "DELETE FROM $KS.comentarios_por_partido WHERE $PART AND creado_en = '$(ts_de $cl)' AND comentario_id = 'PAR-A-1-REP-$etapa-$cl';" >/dev/null
  QUEDAN=$(( QUEDAN + $(leer_comentario $C1 ALL "PAR-A-1-REP-$etapa-$cl" "$(ts_de $cl)" | grep -E '^ +[0-9]+$' | tr -d ' ') ))
done; done
echo "   filas de prueba restantes: $QUEDAN"
echo
echo "✔ Fin. Evidencia: ${EVID_FILE#$MOD_DIR/}"
