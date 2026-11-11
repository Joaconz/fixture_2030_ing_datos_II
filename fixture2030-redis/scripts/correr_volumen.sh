#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · VOLUMEN: 100.000 USUARIOS SIMULTÁNEOS, CARGA Y RENDIMIENTO
#  Uso (desde fixture2030-redis/):  sh scripts/correr_volumen.sh [usuarios]
#  Deja la salida en docs/evidencia/10_carga_volumen.txt y 11_rendimiento_volumen.txt,
#  con fecha, commit y comando. Repetible. Al final borra el volumen (la muestra queda).
#
#  10_: la muestra del hito se carga primero; después tres cargas de volumen (dos desde
#       vacío, con limpieza previa, y una encima de la anterior) deben dar los mismos
#       conteos y la misma huella, y la muestra debe seguir igual.
#  11_: rendimiento_volumen.sh, y luego recarga (idempotente) y limpieza por prefijo.
# ============================================================
cd "$(dirname "$0")/.." || exit 1
N=${1:-100000}
EV=docs/evidencia
RC="docker compose exec -T redis"
R="$RC redis-cli"
cab() {
  echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ) | commit: $(git rev-parse --short HEAD 2>/dev/null || echo sin-git)$(git diff --quiet HEAD -- scripts 2>/dev/null || echo ' + scripts sin commitear') | comando: sh scripts/correr_volumen.sh $N"
}
# Estado de la muestra que NO debe cambiar (claves sin TTL o con TTL largo)
muestra() {
  echo "votantes=$($R SCARD f30:voto:mvp:PAR-D16-01:votantes | tr -d '\r') candidatos=$($R ZCARD f30:voto:mvp:PAR-D16-01:ranking | tr -d '\r') partidos_en_tendencia=$($R ZCARD f30:rank:tendencia:2030062916 | tr -d '\r') md5(sesión demo-ses-0000001-1 + índice USR-0000010 + votación)=$(
    printf 'HGETALL f30:ses:demo-ses-0000001-1\nSMEMBERS f30:usr:USR-0000010:sesiones\nZRANGE f30:voto:mvp:PAR-D16-01:ranking 0 -1 WITHSCORES\n' | $R | sort | md5sum | cut -c1-32)"
}
si() { [ "$1" = "$2" ] && echo "SÍ" || echo "NO"; }

mkdir -p "${REDIS_DATA_DIR:-$HOME/docker/data/redis}"   # el volumen nombrado exige que la carpeta exista (RNF2)
docker compose up -d --wait > /dev/null || exit 1

{
  cab
  echo "== C.0 Muestra del hito (carga_muestra.sh) cargada antes del volumen =="
  $RC sh /scripts/carga_muestra.sh > /dev/null
  echo "DBSIZE con la muestra: $($R DBSIZE | tr -d '\r')"
  M0=$(muestra); echo "$M0"
  for i in 1 2 3; do
    echo
    if [ $i -lt 3 ]; then
      echo "== C.$i Corrida $i DESDE VACÍO: limpieza_volumen.sh + carga_volumen.sh $N =="
      $RC sh /scripts/limpieza_volumen.sh
    else
      echo "== C.3 Corrida 3 ENCIMA de la anterior, sin limpiar (idempotencia sobre datos existentes) =="
    fi
    SAL=$($RC sh /scripts/carga_volumen.sh "$N"); echo "$SAL"
    RES="${RES}corrida $i: $(echo "$SAL" | grep '^conteo') | huella $(echo "$SAL" | grep '^huella' | sed 's/.*: //')
"
  done
  echo
  echo "== C.4 Comparación de las tres corridas =="
  printf '%s' "$RES"
  echo "las 3 corridas dieron los mismos conteos y la misma huella: $(si "$(printf '%s' "$RES" | cut -d: -f2- | sort -u | wc -l)" 1)"
  M1=$(muestra); echo "muestra después: $M1"
  echo "la muestra quedó igual: $(si "$M0" "$M1")"
} > $EV/10_carga_volumen.txt

{
  cab
  $RC sh /scripts/rendimiento_volumen.sh "$N"
  echo
  echo "== R.7 Restauración (carga_volumen.sh es idempotente) y limpieza por prefijo =="
  $RC sh /scripts/carga_volumen.sh "$N" | grep -E '^(errors|conteo|huella)'
  $RC sh /scripts/limpieza_volumen.sh
  echo "muestra: $(muestra)"
  echo "la muestra quedó igual que antes del volumen: $(si "$M0" "$(muestra)")"
} > $EV/11_rendimiento_volumen.txt
echo "Evidencia escrita en $EV/10_carga_volumen.txt y $EV/11_rendimiento_volumen.txt"
