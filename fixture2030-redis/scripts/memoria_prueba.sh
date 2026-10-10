#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · PRUEBA CONTROLADA DE MEMORIA: TTL vs EVICCIÓN (RF10)
#  Uso:  docker compose exec -T redis sh /scripts/memoria_prueba.sh
#
#  Método: se baja maxmemory a (uso actual + 8 MB) y se escriben ~20 MB de claves de
#  relleno CON TTL. Debe haber evicción (evicted_keys > 0) y la votación abierta (SIN
#  TTL) debe seguir íntegra. Fase 2: se baja maxmemory a 100 KB (menos que el piso
#  de Redis vacío): se desaloja todo lo volátil y una escritura nueva falla con OOM,
#  sin tocar la votación.
#  Al final se restaura maxmemory y se borran los rellenos. LA MUESTRA QUEDA DEGRADADA:
#  volver a correr carga_muestra.redis (correr_todo.sh lo hace).
# ============================================================
R="redis-cli"
VOTOS="f30:voto:mvp:PAR-D16-01"
ORIGINAL=$($R CONFIG GET maxmemory | tail -1)
stat() { $R INFO stats | grep "^$1:" | cut -d: -f2 | tr -d '\r'; }

echo "== M.0 Estado inicial =="
USED=$($R INFO memory | grep '^used_memory:' | cut -d: -f2 | tr -d '\r')
echo "maxmemory original: $ORIGINAL bytes | used_memory: $USED bytes"
echo "policy: $($R CONFIG GET maxmemory-policy | tail -1)"
echo "DBSIZE: $($R DBSIZE) | votantes: $($R SCARD $VOTOS:votantes) | candidatos: $($R ZCARD $VOTOS:ranking)"
echo "expired_keys: $(stat expired_keys) | evicted_keys: $(stat evicted_keys)"
$R HGET f30:ses:demo-ses-0000001-1 estado > /dev/null   # una sesión recién leída (LRU): se observa si sobrevive (LRU es aproximado)

LIMITE=$((USED + 8 * 1024 * 1024))
echo "== M.1 CONFIG SET maxmemory $LIMITE (uso + 8 MB) =="
$R CONFIG SET maxmemory $LIMITE

echo "== M.2 Fase 1: 20.000 claves de relleno de 1 KB con TTL 3600 s =="
PAYLOAD=$(head -c 1000 /dev/zero | tr '\0' x)
redis-benchmark -q -n 20000 -r 100000 SET "f30:cache:relleno:__rand_int__" "$PAYLOAD" EX 3600 > /dev/null 2>&1
echo "used_memory: $($R INFO memory | grep '^used_memory:' | cut -d: -f2 | tr -d '\r') (tope $LIMITE)"
echo "evicted_keys: $(stat evicted_keys)   <- > 0: hubo evicción por presión, no por TTL"
echo "expired_keys: $(stat expired_keys)   <- TTL: sin cambios (ninguna clave venció por tiempo)"
echo "DBSIZE: $($R DBSIZE)"
echo "votación abierta intacta -> votantes: $($R SCARD $VOTOS:votantes) | candidatos: $($R ZCARD $VOTOS:ranking) | TTL: $($R TTL $VOTOS:ranking)"
echo "muestra de sesiones (1 = sobrevivió, 0 = desalojada):"
for n in 1 2 3 4 5 6 7 8 9 11; do
  printf 'demo-ses-%07d-1: ' $n; $R EXISTS "f30:ses:$(printf 'demo-ses-%07d-1' $n)"
done

echo "== M.3 Fase 2: presión extrema, maxmemory 100 KB (inalcanzable) =="
$R CONFIG SET maxmemory 102400
echo "-- escritura de un dato SIN TTL: el servidor desaloja lo volátil y, si aún no alcanza, la rechaza con OOM --"
I=0; RESP=OK
while [ "$RESP" = "OK" ] && [ $I -lt 2000 ]; do
  I=$((I+1)); RESP=$($R SET f30:tmp:sin_ttl x)
done
echo "escrituras hasta el primer rechazo: $I | respuesta: $RESP"
echo "evicted_keys: $(stat evicted_keys)"
echo "DBSIZE: $($R DBSIZE)"
echo "votación abierta intacta -> votantes: $($R SCARD $VOTOS:votantes) | candidatos: $($R ZCARD $VOTOS:ranking)"
echo "las lecturas siguen funcionando: $($R ZREVRANGE $VOTOS:ranking 0 0 WITHSCORES | tr '\n' ' ')"

echo "== M.4 Restaurar maxmemory y limpiar =="
$R CONFIG SET maxmemory "$ORIGINAL"
$R DEL f30:tmp:sin_ttl > /dev/null
redis-cli --scan --pattern 'f30:cache:relleno:*' | xargs -r -n 500 redis-cli UNLINK > /dev/null
echo "maxmemory: $($R CONFIG GET maxmemory | tail -1) | DBSIZE: $($R DBSIZE)"
