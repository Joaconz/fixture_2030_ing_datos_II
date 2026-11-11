#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Replicación y CAP · Cassandra: consistencia eventual
#  USO: bash scripts/cassandra_consistencia_eventual.sh   (después de cassandra_iniciar.sh)
#
#  Es la configuración del Hito 3 para Comentarios: N=3, W=1 (CONSISTENCY ONE).
#  Un comentario se escribe con ONE mientras cas3 está caído; cuando cas3
#  vuelve, se lee ESE MISMO comentario en cas3 con ONE antes y después de que
#  las réplicas se pongan de acuerdo. Dos mecanismos de reparación:
#
#   A. Hinted handoff. El coordinador (cas1) guarda un hint para cas3. Para
#      poder ver la lectura vieja se PAUSA la entrega de hints
#      (nodetool pausehandoff) antes de que cas3 vuelva; al reanudarla
#      (resumehandoff) el comentario aparece en cas3.
#   B. Repair (anti-entropía). Con los hints DESACTIVADOS (nodetool
#      disablehandoff), lo que cas3 se perdió no llega solo: la lectura en
#      cas3 sigue vieja hasta correr `nodetool repair`.
#
#  "Leer en cas3" = cqlsh con cas3 como coordinador, CONSISTENCY ONE y
#  TRACING ON: la traza muestra qué nodo leyó la partición (debe ser cas3
#  solo; si el coordinador hubiera consultado otra réplica, se ve ahí).
#  Un trap deja la entrega de hints reanudada/activada y cas3 arriba aunque el
#  script falle. Al final borra las dos filas de prueba (CONSISTENCY ALL).
# ============================================================================
. "$(dirname "$0")/_comun.sh"
evidencia cassandra_consistencia_eventual "bash scripts/cassandra_consistencia_eventual.sh"
C1=fixture2030-rep-cas1; C2=fixture2030-rep-cas2; C3=fixture2030-rep-cas3
TS="2030-06-09 13:04:00.000+0000"
# Identificadores únicos por corrida: una fila de una corrida anterior (o su
# tombstone) no puede contaminar la lectura de esta.
SUF="$(date +%Y%m%d%H%M%S)"
ID_A="PAR-A-1-REP-EVENTUAL-HINT-$SUF"; ID_B="PAR-A-1-REP-EVENTUAL-REPAIR-$SUF"

restablecer() {
  docker ps --format '{{.Names}}' | grep -qx $C3 || docker start $C3 >/dev/null 2>&1 || true
  for c in $C1 $C2; do docker exec $c nodetool resumehandoff >/dev/null 2>&1 || true; docker exec $c nodetool enablehandoff >/dev/null 2>&1 || true; done
}
trap restablecer EXIT

# leer_local NODO ID — lectura con ese NODO como coordinador, CONSISTENCY ONE
# y TRACING ON. Con ONE el coordinador consulta UNA réplica, pero no siempre la
# propia: el dynamic snitch puede elegir otra (pasó en la primera corrida: la
# traza mostraba READ_REQ a cas2, y una lectura "desde cas1" la contestó cas3).
# Por eso se repite la lectura (hasta 10 veces) hasta que la traza muestre que
# la partición la leyó solo ese nodo, y se informa si se logró y en qué
# intento. Así se ve lo que tiene ESA réplica.
leer_local() {
  local out traza n ip local="no"; ip="$(ip_de "$1")"
  for n in $(seq 1 10); do
    out="$(dk exec "$1" cqlsh -e "CONSISTENCY ONE; TRACING ON;
      SELECT comentario_id, contenido FROM $KS.comentarios_por_partido WHERE $PART AND creado_en = '$TS' AND comentario_id = '$2';" 2>&1)" || true
    traza="$(echo "$out" | grep -E 'single-partition|Sending READ_REQ|Read [0-9]+ live' |       awk -F'|' '{gsub(/^ +| +$/, "", $1); gsub(/^ +| +$/, "", $3); print $3 "  " $1}')"
    if echo "$traza" | grep -q "^$ip .*single-partition" && ! echo "$traza" | grep -q 'READ_REQ'; then local="sí"; break; fi
  done
  echo "$out" | grep -qE "^ *$2 " && echo "   resultado: 1 fila -> $(echo "$out" | grep -E "^ *$2 " | sed 's/  */ /g')"                                    || echo "   resultado: 0 filas"
  echo "   ¿la leyó solo ${1#fixture2030-rep-} ($ip)? $local · traza del intento $n:"
  echo "$traza" | sed 's/^/     /' | sort -u
}
leer_en_cas3() { leer_local $C3 "$1"; }
# esperar_en_cas3 ID SEGUNDOS — repite leer_en_cas3 hasta ver la fila.
esperar_en_cas3() {
  local t0 r; t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt "$2" ]; do
    r="$(leer_en_cas3 "$1")"
    echo "$r" | grep -q 'resultado: 1 fila' && echo "$r" | grep -q 'solo cas3 .*sí' && { echo $(( $(date +%s) - t0 )); return 0; }
    sleep 2
  done
  echo "más de $2"; return 1
}
ip3() { ip_de $C3; }

titulo "Anillo y nodos (cas3 = $(ip3))"
for c in $CASS; do echo "   $c = $(ip_de $c)"; done
nodetool $C1 status "$KS" | grep -E '^UN|^DN' | sed 's/^/   /'

# ------------------------------------------------------------------------- A
titulo "A1. Pausa de la entrega de hints en cas1 y cas2 (pausehandoff) y docker stop $C3"
for c in $C1 $C2; do nodetool $c pausehandoff; done
IP3="$(ip3)"; dk stop $C3 >/dev/null
echo "   cas1 ve a cas3 ($IP3) DN a los $(esperar_estado_cas $C1 "$IP3" DN 120) s"

titulo "A2. Escritura con CONSISTENCY ONE (coordinador cas1) mientras cas3 está caído"
insertar_comentario $C1 ONE "$ID_A" "$TS" "Golazo! (escrito con ONE, cas3 caido)" && echo "   escritura aceptada con ONE: $ID_A"
sleep 11   # hints_flush_period = 10 s: el hint pasa de memoria al archivo
echo "   archivos en /var/lib/cassandra/hints de cas1:"
hints_en_disco $C1

titulo "A3. docker start $C3 (la entrega de hints sigue pausada)"
dk start $C3 >/dev/null
esperar_healthy $C3 400 || falla "$C3 no volvió"
echo "   cas1 ve a cas3 ($(ip3)) UN a los $(esperar_estado_cas $C1 "$(ip3)" UN 120) s de que acepta CQL"

titulo "A4. Lectura en cas3 ANTES de la reparación"
leer_en_cas3 "$ID_A"
echo "   la misma fila leída solo en cas1 (recibió la escritura):"
leer_local $C1 "$ID_A" | sed 's/^/  /'

titulo "A5. Se reanuda la entrega de hints (resumehandoff)"
DESDE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for c in $C1 $C2; do nodetool $c resumehandoff; done
echo "   entrega reanudada a las $DESDE (UTC)"
echo "   cas3 tiene el comentario (lectura local) a los $(esperar_en_cas3 "$ID_A" 180) s de reanudar"
echo "   log de cas1: $(esperar_log $C1 "$DESDE" 'Finished hinted handoff' 60 | sed 's/^[0-9]* s · //')"
echo "   archivos de hints que quedan en cas1:"
hints_en_disco $C1

titulo "A6. Lectura en cas3 DESPUÉS del hinted handoff"
leer_en_cas3 "$ID_A"

# ------------------------------------------------------------------------- B
titulo "B1. Hints DESACTIVADOS en cas1 y cas2 (disablehandoff) y docker stop $C3"
for c in $C1 $C2; do nodetool $c disablehandoff; done
nodetool $C1 statushandoff | sed 's/^/   cas1: /'
IP3="$(ip3)"; dk stop $C3 >/dev/null
echo "   cas1 ve a cas3 ($IP3) DN a los $(esperar_estado_cas $C1 "$IP3" DN 120) s"

titulo "B2. Escritura con CONSISTENCY ONE (coordinador cas1) mientras cas3 está caído"
insertar_comentario $C1 ONE "$ID_B" "$TS" "Que partido! (escrito con ONE, sin hints)" && echo "   escritura aceptada con ONE: $ID_B"
sleep 11   # más que el volcado de hints a disco (10 s): si se hubiera guardado uno, se vería
echo "   archivos en /var/lib/cassandra/hints de cas1 (hints desactivados):"
hints_en_disco $C1

titulo "B3. docker start $C3"
dk start $C3 >/dev/null
esperar_healthy $C3 400 || falla "$C3 no volvió"
echo "   cas1 ve a cas3 ($(ip3)) UN a los $(esperar_estado_cas $C1 "$(ip3)" UN 120) s de que acepta CQL"
for c in $C1 $C2; do nodetool $c enablehandoff; done
echo "   (hints reactivados para lo que venga; lo perdido mientras estaban desactivados no se recupera así)"

titulo "B4. Lectura en cas3 recién vuelto y 30 s después: no se repara sola"
leer_en_cas3 "$ID_B"
sleep 30
leer_en_cas3 "$ID_B"

titulo "B5. nodetool repair en cas3 (anti-entropía: compara árboles de Merkle con las otras réplicas)"
T0=$(date +%s)
nodetool $C3 repair -full "$KS" comentarios_por_partido 2>&1 | grep -iE 'repair (session|command)|finished|Repair completed|error' | sed 's/^/   /' | tail -4
echo "   repair terminado en $(( $(date +%s) - T0 )) s"

titulo "B6. Lectura en cas3 DESPUÉS del repair"
leer_en_cas3 "$ID_B"

titulo "Limpieza de las filas de prueba (CONSISTENCY ALL)"
for id in "$ID_A" "$ID_B"; do
  cql $C1 ALL "DELETE FROM $KS.comentarios_por_partido WHERE $PART AND creado_en = '$TS' AND comentario_id = '$id';" >/dev/null
  echo "   $id: $(leer_comentario $C1 ALL "$id" "$TS" | grep -E '^ +[0-9]+$' | tr -d ' ') filas"
done
nodetool $C1 statushandoff | sed 's/^/   cas1: /'
echo
echo "✔ Fin. Evidencia: ${EVID_FILE#$MOD_DIR/}"
