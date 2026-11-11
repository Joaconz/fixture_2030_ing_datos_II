#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · CARGA DE VOLUMEN: 100.000 USUARIOS SIMULTÁNEOS
#  Uso (dentro del contenedor):  docker compose exec -T redis sh /scripts/carga_volumen.sh [usuarios]
#
#  Cada usuario queda con su sesión activa (con TTL), su índice de sesiones y su perfil
#  en caché (idioma y región = sus preferencias). Mismas estructuras y claves que el resto
#  del módulo (docs/modelo_clave_valor.md §2); no se agrega ninguna estructura:
#    f30:ses:{session_id}                    HASH, mismos 10 campos que la muestra, TTL 1800 s
#    f30:usr:{usuario_id}:sesiones           SET,  TTL 43200 s (tope de sesión)
#    f30:cache:usuario:{usuario_id}:perfil   HASH nombre/idioma/region, TTL 900 s
#
#  NO PISA LA MUESTRA: la muestra usa USR-0000001…0002000 y demo-ses-…; el volumen usa
#  USR-1000000…USR-1099999 y vol-ses-{12 dígitos}. Los 12 dígitos son el formato que
#  redis-benchmark pone en __rand_int__: así las pruebas eligen sesiones reales al azar.
#  Se borra con limpieza_volumen.sh (SCAN por prefijo + UNLINK).
#
#  PIPELINE: awk genera el protocolo de Redis (RESP) y redis-cli --pipe lo envía sin
#  esperar cada respuesta. Cada usuario se crea igual que en la aplicación: crear sesión
#  (P1) y cachear perfil (P7), cada una en su MULTI/EXEC. Sin Lua.
#
#  DETERMINISMO: sin azar; todo sale de fórmulas sobre el índice y de un instante fijo
#  (2030-06-29 16:00 UTC, el de la muestra). Lo único relativo es el TTL, que Redis cuenta
#  desde la carga: la actividad escalonada deja TTL entre 1201 y 1800 s, así ninguna sesión
#  vence durante las pruebas.
#  IDEMPOTENTE: HSET/SADD reescriben los mismos valores y EXPIRE renueva el TTL. Repetir la
#  carga (con o sin limpieza previa) deja los mismos conteos y los mismos valores.
# ============================================================
N=${1:-100000}
R="redis-cli"
mem() { $R INFO memory | grep "^$1:" | cut -d: -f2 | tr -d '\r'; }
cuenta() { $R --scan --count 1000 --pattern "$1" | wc -l; }

echo "== V.1 Estado previo (DBSIZE e INFO son O(1), no recorren claves) =="
echo "DBSIZE: $($R DBSIZE) | used_memory: $(mem used_memory) bytes"
ANTES=$(mem used_memory)

echo "== V.2 Carga de $N usuarios por pipeline (awk -> RESP -> redis-cli --pipe) =="
T0=$(date +%s%N)
awk -v n="$N" '
function resp(linea,   a, k, i, s) {   # "ARG1|ARG2|…" -> comando en protocolo RESP
  k = split(linea, a, "|"); s = "*" k "\r\n"
  for (i = 1; i <= k; i++) s = s "$" length(a[i]) "\r\n" a[i] "\r\n"
  printf "%s", s
}
BEGIN {
  T = 1908979200                    # 2030-06-29T16:00:00Z, instante de la demo
  TTL_INACT = 1800; TTL_ABS = 43200; TTL_PERFIL = 900
  split("AM EU AF", REG, " ")       # regiones del Hito 3
  split("web android ios", DISP, " ")
  split("es en pt fr ar", IDIOMA, " ")
  for (k = 0; k < n; k++) {
    uid = sprintf("USR-%07d", 1000000 + k)
    sid = sprintf("vol-ses-%012d", k)
    rol = (k % 200 == 0) ? "MODERADOR" : "HINCHA"
    region = REG[(k % 3) + 1]
    hace = (k * 7) % 600            # última actividad entre 0 y 10 min atrás
    # P1 crear sesión: HSET + EXPIRE + SADD + EXPIRE del índice, en MULTI/EXEC
    resp("MULTI")
    resp("HSET|f30:ses:" sid "|session_id|" sid "|usuario_id|" uid "|rol|" rol "|region|" region \
         "|dispositivo|" DISP[(k % 3) + 1] "|estado|ACTIVA|creada_en|" (T - hace - 60) \
         "|ultima_actividad|" (T - hace) "|expira_absoluta|" (T - hace - 60 + TTL_ABS) \
         "|solicitudes|" ((k * 13) % 50))
    resp("EXPIRE|f30:ses:" sid "|" (TTL_INACT - hace))
    resp("SADD|f30:usr:" uid ":sesiones|" sid)
    resp("EXPIRE|f30:usr:" uid ":sesiones|" TTL_ABS)
    resp("EXEC")
    # P7 cachear perfil (preferencias: idioma y región): HSET + EXPIRE, en MULTI/EXEC
    resp("MULTI")
    resp("HSET|f30:cache:usuario:" uid ":perfil|nombre|Usuario " (1000000 + k) "|idioma|" IDIOMA[(k % 5) + 1] "|region|" region)
    resp("EXPIRE|f30:cache:usuario:" uid ":perfil|" TTL_PERFIL)
    resp("EXEC")
  }
}' | $R --pipe | tail -1
T1=$(date +%s%N)
MS=$(( (T1 - T0) / 1000000 ))
echo "tiempo de carga: $MS ms | $(awk -v n="$N" -v ms="$MS" 'BEGIN { printf "%.0f usuarios/s, %.0f comandos/s (11 por usuario)", n*1000/ms, n*11*1000/ms }')"

echo "== V.3 Verificación (conteos con SCAN por prefijo: cursor, no bloquea; nunca KEYS) =="
echo "conteo usuarios=$(cuenta 'f30:usr:USR-1??????:sesiones') sesiones=$(cuenta 'f30:ses:vol-ses-*') perfiles=$(cuenta 'f30:cache:usuario:USR-1??????:perfil') esperado=$N"
echo "INFO keyspace (expires = claves con TTL): $($R INFO keyspace | grep '^db0' | tr -d '\r')"
echo "huella de contenido (md5 de HGETALL/SMEMBERS de 1 de cada 100 usuarios, sin TTL): $(
  awk -v n="$N" 'BEGIN { for (k = 0; k < n; k += 100) {
    printf "HGETALL f30:ses:vol-ses-%012d\nSMEMBERS f30:usr:USR-%07d:sesiones\nHGETALL f30:cache:usuario:USR-%07d:perfil\n", k, 1000000 + k, 1000000 + k } }' \
  | $R | md5sum | cut -c1-32)"
echo "-- primer usuario --"
$R HGETALL f30:ses:vol-ses-000000000000 | paste -sd' '
$R HGETALL f30:cache:usuario:USR-1000000:perfil | paste -sd' '
echo "TTL sesión: $($R TTL f30:ses:vol-ses-000000000000) | TTL índice: $($R TTL f30:usr:USR-1000000:sesiones) | TTL perfil: $($R TTL f30:cache:usuario:USR-1000000:perfil)"
U=$((N - 1))
echo "-- último usuario ($(printf 'USR-%07d' $((1000000 + U)))) --"
echo "sesiones: $($R SMEMBERS "$(printf 'f30:usr:USR-%07d:sesiones' $((1000000 + U)))") | TTL sesión: $($R TTL "$(printf 'f30:ses:vol-ses-%012d' $U)")"

echo "== V.4 Memoria =="
DESPUES=$(mem used_memory)
echo "used_memory antes: $ANTES | después: $DESPUES ($(mem used_memory_human)) | maxmemory: $($R CONFIG GET maxmemory | tail -1)"
echo "por usuario (diferencia / $N): $(( (DESPUES - ANTES) / N )) bytes"
echo "evicted_keys: $($R INFO stats | grep '^evicted_keys:' | cut -d: -f2 | tr -d '\r')   <- 0: la carga entró sin desalojar nada"
