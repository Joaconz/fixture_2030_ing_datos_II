#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · RENDIMIENTO CON 100.000 USUARIOS SIMULTÁNEOS (RF12, RNF10)
#  Uso (dentro del contenedor, con carga_volumen.sh ya ejecutado):
#    docker compose exec -T redis sh /scripts/rendimiento_volumen.sh [usuarios] [clientes] [clientes_tx]
#
#  R.1 memoria total y por usuario (INFO memory, MEMORY USAGE sobre 1 de cada 100 usuarios)
#  R.2 latencia en reposo (redis-cli --latency)
#  R.3 redis-benchmark con [clientes] conexiones sobre sesiones AL AZAR entre las 100.000:
#      validar (HMGET) y los tres comandos de renovar, de a uno; latencia de un cliente
#      extra medida mientras tanto
#  R.4 las operaciones completas de sesión, como transacciones (MULTI/EXEC), con
#      [clientes_tx] clientes simultáneos (redis-cli --pipe), cada uno con sus usuarios:
#      validar, renovar, cerrar y crear las 100.000 sesiones, verificando el resultado
#  R.5 expiración activa: las 100.000 sesiones pasan a TTL 5 s y se observa, sin leerlas,
#      cómo Redis las borra solo
#  LA CARGA QUEDA MODIFICADA (renovadas y vencidas): correr_volumen.sh la recarga después.
#
#  LIMITACIONES: cliente y servidor en el mismo contenedor y la misma VM (comparten CPU,
#  sin red real); una corrida por prueba, sin repeticiones. Sirve para comparar en ESTE
#  equipo, no como capacidad de producción (concurrencia_y_pruebas.md §6).
# ============================================================
N=${1:-100000}
C=${2:-200}
P=${3:-50}
R="redis-cli"
D=/tmp/f30vol
LAT="--latency-percentiles 50,99,99.9"
info() { $R INFO "$1" | grep "^$2:" | cut -d: -f2 | tr -d '\r'; }
cuenta() { $R --scan --count 1000 --pattern "$1" | wc -l; }
ms() { echo $(( ($(date +%s%N) - $1) / 1000000 )); }
huella() {
  awk -v n="$N" 'BEGIN { for (k = 0; k < n; k += 100) {
    printf "HGETALL f30:ses:vol-ses-%012d\nSMEMBERS f30:usr:USR-%07d:sesiones\nHGETALL f30:cache:usuario:USR-%07d:perfil\n", k, 1000000 + k, 1000000 + k } }' \
  | $R | md5sum | cut -c1-32
}
rm -rf $D && mkdir -p $D

echo "== R.0 Entorno (RNF10) =="
echo "fecha (UTC)  : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "redis        : $(info server redis_version) | $(info server os) | CPUs visibles: $(nproc)"
echo "memoria      : maxmemory $($R CONFIG GET maxmemory | tail -1) | policy $($R CONFIG GET maxmemory-policy | tail -1) | appendonly $($R CONFIG GET appendonly | tail -1) ($($R CONFIG GET appendfsync | tail -1))"
echo "keyspace     : $($R INFO keyspace | grep '^db0' | tr -d '\r')"
echo "parámetros   : $N usuarios | redis-benchmark con $C clientes (--threads 4) | $P clientes con transacciones"
echo "conteo previo: sesiones=$(cuenta 'f30:ses:vol-ses-*') (esperado $N)"
$R CONFIG RESETSTAT > /dev/null; $R SLOWLOG RESET > /dev/null; $R LATENCY RESET > /dev/null

echo
echo "== R.1 Memoria con $N usuarios cargados =="
for c in used_memory used_memory_human used_memory_dataset used_memory_rss_human mem_fragmentation_ratio maxmemory_human; do
  echo "$c: $(info memory $c)"
done
echo "-- MEMORY USAGE de 1 de cada 100 usuarios ($((N / 100)) usuarios x 3 claves); bytes promedio por clave --"
awk -v n="$N" 'BEGIN { for (k = 0; k < n; k += 100)
  printf "MEMORY USAGE f30:ses:vol-ses-%012d\nMEMORY USAGE f30:usr:USR-%07d:sesiones\nMEMORY USAGE f30:cache:usuario:USR-%07d:perfil\n", k, 1000000 + k, 1000000 + k }' \
| $R | awk '{ s[NR % 3] += $1; c[NR % 3]++ }
  END { printf "sesión (HASH 10 campos): %.0f | índice (SET): %.0f | perfil (HASH 3 campos): %.0f | total por usuario: %.0f bytes\n",
        s[1]/c[1], s[2]/c[2], s[0]/c[0], s[1]/c[1] + s[2]/c[2] + s[0]/c[0] }'
echo "codificación: sesión $($R OBJECT ENCODING f30:ses:vol-ses-000000000000) | índice $($R OBJECT ENCODING f30:usr:USR-1000000:sesiones) | perfil $($R OBJECT ENCODING f30:cache:usuario:USR-1000000:perfil)"
echo "proyección lineal a 256 MB (maxmemory): $(awk -v u="$(info memory used_memory)" -v n="$N" 'BEGIN { printf "~%.0f usuarios", 268435456 / (u / n) }') (incluye el piso de Redis; sin contar fragmentación)"

echo
echo "== R.2 Latencia en reposo: un cliente, 5 s (redis-cli --latency) =="
echo "min max avg muestras p50 p99 p99.9 (ms)"
$R --latency -i 5 $LAT

echo
echo "== R.3 redis-benchmark: $C clientes, sesiones al azar entre las $N (-r $N) =="
echo "formato CSV: test,rps,avg,min,p50,p95,p99,max (ms)"
RB="redis-benchmark -c $C --threads 4 -r $N --csv"
echo "-- VALIDAR (P2): HMGET usuario_id estado expira_absoluta. Mientras corre, un cliente extra mide latencia 3 s --"
( sleep 1; $R --latency -i 3 $LAT > $D/lat_validar ) &
$RB -n 1000000 HMGET f30:ses:vol-ses-__rand_int__ usuario_id estado expira_absoluta | tail -1
wait
echo "latencia del cliente extra bajo carga (min max avg muestras p50 p99 p99.9): $(cat $D/lat_validar)"
echo "-- RENOVAR (P2), sus tres comandos de a uno (redis-benchmark no encola transacciones; la transacción completa está en R.4) --"
$RB -n 300000 HSET f30:ses:vol-ses-__rand_int__ ultima_actividad 1908979260 | tail -1
$RB -n 300000 HINCRBY f30:ses:vol-ses-__rand_int__ solicitudes 1 | tail -1
$RB -n 300000 EXPIRE f30:ses:vol-ses-__rand_int__ 1800 | tail -1
echo "evicted_keys: $(info stats evicted_keys) | sesiones: $(cuenta 'f30:ses:vol-ses-*')"

echo
echo "== R.4 Operaciones completas de sesión (MULTI/EXEC), $P clientes simultáneos, $N usuarios distintos =="
echo "Cada cliente es un redis-cli --pipe con su parte de los usuarios (k mod $P): todos a la vez, cada uno encadena sus transacciones."
# genera los $P archivos de una fase en protocolo RESP; no entra en el tiempo medido
genera() {
  awk -v n="$N" -v p="$P" -v fase="$1" -v d="$D" '
  function resp(linea,   a, k, i, s) {
    k = split(linea, a, "|"); s = "*" k "\r\n"
    for (i = 1; i <= k; i++) s = s "$" length(a[i]) "\r\n" a[i] "\r\n"
    printf "%s", s > f
  }
  BEGIN {
    T = 1908979200; split("AM EU AF", REG, " "); split("web android ios", DISP, " ")
    for (k = 0; k < n; k++) {
      f = d "/" fase "." (k % p)
      uid = sprintf("USR-%07d", 1000000 + k); sid = sprintf("vol-ses-%012d", k); ses = "f30:ses:" sid
      if (fase == "validar") resp("HMGET|" ses "|usuario_id|estado|expira_absoluta")
      else if (fase == "renovar") {
        resp("MULTI"); resp("HSET|" ses "|ultima_actividad|" (T + 120)); resp("HINCRBY|" ses "|solicitudes|1")
        resp("EXPIRE|" ses "|1800"); resp("EXEC") }
      else if (fase == "cerrar") {
        resp("MULTI"); resp("SREM|f30:usr:" uid ":sesiones|" sid); resp("DEL|" ses); resp("EXEC") }
      else if (fase == "crear") {   # mismo P1 y mismos valores que carga_volumen.sh
        hace = (k * 7) % 600
        resp("MULTI")
        resp("HSET|" ses "|session_id|" sid "|usuario_id|" uid "|rol|" ((k % 200 == 0) ? "MODERADOR" : "HINCHA") \
             "|region|" REG[(k % 3) + 1] "|dispositivo|" DISP[(k % 3) + 1] "|estado|ACTIVA|creada_en|" (T - hace - 60) \
             "|ultima_actividad|" (T - hace) "|expira_absoluta|" (T - hace - 60 + 43200) "|solicitudes|" ((k * 13) % 50))
        resp("EXPIRE|" ses "|" (1800 - hace)); resp("SADD|f30:usr:" uid ":sesiones|" sid)
        resp("EXPIRE|f30:usr:" uid ":sesiones|43200"); resp("EXEC") }
    }
  }'
}
fase() { # fase <nombre> <comandos por usuario>
  genera "$1"
  T0=$(date +%s%N)
  for p in $(seq 0 $((P - 1))); do $R --pipe < $D/$1.$p > $D/$1.$p.out 2>&1 & done
  wait
  M=$(ms $T0)
  cat $D/$1.*.out | awk -v n="$N" -v ms="$M" -v f="$1" -v cpu="$2" '/^errors:/ { e += $2; r += $4 }
    END { printf "%-8s %6d ms | %7.0f operaciones/s | %8.0f comandos/s | respuestas %d | errores %d\n", f, ms, n*1000/ms, n*cpu*1000/ms, r, e }'
}
echo "fase      tiempo  | operaciones (1 por usuario)  | comandos enviados"
fase validar 1
fase renovar 5
echo "   verificación renovar (las $N sesiones, HMGET de a una): $(
  awk -v n="$N" 'BEGIN { for (k = 0; k < n; k++) printf "HMGET f30:ses:vol-ses-%012d solicitudes ultima_actividad\n", k }' \
  | $R | paste - - | awk '{ if ($2 == 1908979320) okT++ } END { printf "ultima_actividad renovada en %d de %d", okT, NR }')"
echo "   (solicitudes suma +1 por la transacción; R.3 ya había sumado incrementos al azar, por eso no se compara su valor exacto)"
fase cerrar 4
echo "   verificación cerrar: sesiones=$(cuenta 'f30:ses:vol-ses-*') índices=$(cuenta 'f30:usr:USR-1??????:sesiones') (esperado 0 y 0: el SET vacío desaparece solo)"
fase crear 6
echo "   verificación crear : sesiones=$(cuenta 'f30:ses:vol-ses-*') índices=$(cuenta 'f30:usr:USR-1??????:sesiones') perfiles=$(cuenta 'f30:cache:usuario:USR-1??????:perfil') (esperado $N)"
echo "   huella de contenido tras crear: $(huella)   <- igual a la de carga_volumen.sh: crear dejó los mismos valores"
echo "evicted_keys: $(info stats evicted_keys)"

echo
echo "== R.5 Expiración activa: las $N sesiones pasan a TTL 5 s y NADIE las lee =="
awk -v n="$N" 'BEGIN { for (k = 0; k < n; k++) { s = sprintf("f30:ses:vol-ses-%012d", k)
  printf "*3\r\n$6\r\nEXPIRE\r\n$%d\r\n%s\r\n$1\r\n5\r\n", length(s), s } }' | $R --pipe | tail -1
E0=$(info stats expired_keys)
echo "seg  DBSIZE  vencidas_por_TTL(expired_keys)   <- DBSIZE e INFO no tocan claves: el borrado lo hace el ciclo activo de Redis"
T0=$(date +%s%N)
for s in $(seq 0 40); do
  V=$(( $(info stats expired_keys) - E0 ))
  [ $((s % 2)) -eq 0 ] || [ "$V" -ge "$N" ] && printf '%3d  %6d  %6d\n' "$s" "$($R DBSIZE)" "$V"
  [ "$V" -ge "$N" ] && break
  sleep 1
done
echo "vencidas sin ser leídas: $(( $(info stats expired_keys) - E0 )) de $N | sesiones que quedan (SCAN, que además borra las vencidas que encuentra): $(cuenta 'f30:ses:vol-ses-*')"
echo "índices y perfiles siguen (TTL 12 h y 900 s): índices=$(cuenta 'f30:usr:USR-1??????:sesiones') perfiles=$(cuenta 'f30:cache:usuario:USR-1??????:perfil')"

echo
echo "== R.6 Resumen del servidor durante las pruebas =="
echo "evicted_keys: $(info stats evicted_keys)   <- 0: nada se desalojó por memoria"
echo "-- LATENCY LATEST (eventos sobre latency-monitor-threshold = 50 ms; vacío = ninguno) --"
$R LATENCY LATEST | paste - - - - | awk '{ printf "evento %s | último %s ms | máximo %s ms\n", $1, $3, $4 }'
echo "-- SLOWLOG (comandos > 10 ms): $($R SLOWLOG LEN) registrados; los 3 más recientes --"
$R SLOWLOG GET 3 | paste -sd' ' | cut -c1-600
rm -rf $D
