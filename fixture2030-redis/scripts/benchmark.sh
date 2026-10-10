#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · MEDICIÓN (RF12, RNF10)
#  Uso (desde fixture2030-redis/):  sh scripts/benchmark.sh
#  Requiere el contenedor arriba y la muestra cargada (carga_muestra.sh).
#
#  MÉTODO: redis-benchmark (incluido en la imagen) DENTRO del contenedor, 50 clientes
#  concurrentes, 100.000 requests por prueba, sin pipeline (-P 1) => cada request es un
#  viaje completo. Un solo cliente-generador y un solo servidor en la misma VM.
#  LIMITACIONES: sin red real (loopback), cliente y servidor compiten por la misma CPU
#  de Docker Desktop, nodo único, datos chicos (todo cabe en RAM), un solo run por
#  prueba (sin repeticiones ni intervalos de confianza). Las cifras sirven para comparar
#  operaciones entre sí en ESTE equipo, no como capacidad de producción.
# ============================================================
RB="docker compose exec -T redis redis-benchmark -h 127.0.0.1 -c 50 -n 100000 --csv"
R="docker compose exec -T redis redis-cli"
n() { $R "$@" | tr -d '\r'; }

echo "== B.0 Entorno (RNF10) =="
echo "fecha (UTC)      : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "redis_version    : $($R INFO server | grep '^redis_version:' | cut -d: -f2 | tr -d '\r')"
echo "imagen           : $(docker inspect fixture2030-redis --format '{{.Config.Image}} -> {{.Image}}')"
echo "host             : $(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -sm), $(sysctl -n hw.ncpu 2>/dev/null || nproc) CPUs"
echo "docker           : $(docker info --format '{{.NCPU}} CPUs, {{.MemTotal}} bytes de RAM para contenedores, {{.OperatingSystem}}')"
echo "maxmemory-policy : $(n CONFIG GET maxmemory-policy | tail -1) | appendonly: $(n CONFIG GET appendonly | tail -1) | appendfsync: $(n CONFIG GET appendfsync | tail -1)"
echo "parámetros       : 50 clientes, 100000 requests por prueba, sin pipeline"

echo
echo "== B.1 Línea base: SET / GET (una sola clave, valor de 3 bytes) =="
$RB -t set,get

echo
SOLICITUDES_ANTES=$(n HGET f30:ses:demo-ses-0000002-1 solicitudes)
echo "== B.2 Operaciones del módulo (formato CSV: test,rps,avg,min,p50,p95,p99,max en ms) =="
echo "-- lectura de sesión (HGETALL, 10 campos) --"
$RB HGETALL f30:ses:demo-ses-0000001-1
echo "-- renovación de sesión: los comandos de su MULTI/EXEC, de a uno (redis-benchmark no encola transacciones) --"
$RB HINCRBY f30:ses:demo-ses-0000002-1 solicitudes 1
$RB EXPIRE f30:ses:demo-ses-0000002-1 1800
echo "-- registrar visita en ranking de tendencia (ZINCRBY, 50 clientes sobre la MISMA clave: peor caso de contención) --"
n DEL f30:bench:tend > /dev/null
$RB ZINCRBY f30:bench:tend 1 PAR-D16-01
echo "-- guarda del voto único (SADD con usuarios al azar en un rango de 1000) --"
n DEL f30:bench:votantes > /dev/null
docker compose exec -T redis redis-benchmark -h 127.0.0.1 -c 50 -n 100000 -r 1000 --csv SADD f30:bench:votantes USR-__rand_int__

echo
echo "== B.3 Corrección bajo concurrencia (RF8): el resultado debe ser exacto =="
echo "-- (a) 100000 ZINCRBY concurrentes de B.2 sobre la misma clave: puntaje esperado EXACTO = 100000 --"
echo "puntaje obtenido : $(n ZSCORE f30:bench:tend PAR-D16-01)"
echo "-- (b) 100000 HINCRBY concurrentes de B.2 sobre el contador de UNA sesión: debe sumar EXACTO 100000 --"
echo "solicitudes antes: $SOLICITUDES_ANTES | después: $(n HGET f30:ses:demo-ses-0000002-1 solicitudes) | esperado: $((SOLICITUDES_ANTES + 100000))"
echo "-- (c) 100000 SADD de B.2 con usuarios al azar: SCARD = usuarios distintos (como máximo 1000), nunca duplicados --"
echo "votantes distintos (SCARD) : $(n SCARD f30:bench:votantes)"
echo "-- el voto único con clientes simultáneos del MISMO usuario se prueba en concurrencia_paralela.sh --"

echo "== B.4 Método de medición de cache hit ratio (sintético: valida el método, NO es un hit ratio de producción) =="
echo "Se vacían las estadísticas, se cargan 56 de 112 claves de caché y se piden 100000 claves al azar de las 112."
echo "Esperado por construcción: ~50 %."
n CONFIG RESETSTAT > /dev/null
seq 0 55 | awk '{ printf "SET f30:bench:cache:%012d x EX 600\n", $1 }' | $R > /dev/null
docker compose exec -T redis redis-benchmark -h 127.0.0.1 -c 50 -n 100000 -r 112 -q GET "f30:bench:cache:__rand_int__" | tr '\r' '\n' | tail -1
H=$(n INFO stats | grep '^keyspace_hits:' | cut -d: -f2 | tr -d '\r')
M=$(n INFO stats | grep '^keyspace_misses:' | cut -d: -f2 | tr -d '\r')
echo "keyspace_hits=$H keyspace_misses=$M -> hit ratio observado = $(awk -v h=$H -v m=$M 'BEGIN{printf "%.1f %%", 100*h/(h+m)}')"

echo
echo "== B.5 Limpieza de claves de la medición (SCAN + UNLINK) =="
docker compose exec -T redis sh /scripts/limpieza.sh f30:bench:
