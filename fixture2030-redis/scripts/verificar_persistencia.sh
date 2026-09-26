#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · VERIFICACIÓN DE PERSISTENCIA (RNF2, RF13)
#  Uso (desde fixture2030-redis/):  sh scripts/verificar_persistencia.sh
#  Comprueba que (1) los datos viven en un VOLUMEN NOMBRADO respaldado por la
#  carpeta ~/docker/data/redis del host y (2) sobreviven a `restart` y a `down` + `up`
#  (sin `-v`). Usa una clave marcadora con TTL para ver que el vencimiento también persiste.
# ============================================================
cd "$(dirname "$0")/.." || exit 1
RC="docker compose exec -T redis redis-cli"
DIR="${REDIS_DATA_DIR:-$HOME/docker/data/redis}"
MARCA="f30:persist:marca"
VOTOS="f30:voto:mvp:PAR-D16-01"

echo "# Ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "== P.1 Volumen nombrado respaldado por la carpeta del host (RNF2) =="
docker volume inspect fixture2030_redis_data --format 'volumen: {{.Name}} | driver={{.Driver}} | tipo={{index .Options "type"}} | opciones={{index .Options "o"}} | carpeta del host={{index .Options "device"}}'
echo "montaje dentro del contenedor: $(docker inspect fixture2030-redis --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Type}} "{{.Name}}" -> {{.Destination}}{{end}}{{end}}')"
echo "-- contenido de $DIR (lo escribe Redis: AOF y RDB) --"
ls "$DIR"

echo "== P.2 Estado antes de reiniciar =="
$RC SET $MARCA "creada-$(date -u +%H:%M:%S)" EX 3600 > /dev/null
$RC SAVE > /dev/null
echo "clave marcadora : $($RC GET $MARCA) | TTL: $($RC TTL $MARCA) s"
echo "votación abierta: $($RC SCARD $VOTOS:votantes) votantes (sin TTL: $($RC TTL $VOTOS:ranking))"
echo "librerías       : $($RC FUNCTION LIST | grep -A1 '^library_name' | grep -v -e '^library_name' -e '^--' | tr '\n' ' ')"

echo "== P.3 docker compose restart redis =="
docker compose restart redis > /dev/null && docker compose up -d --wait > /dev/null 2>&1
echo "clave marcadora : $($RC GET $MARCA) | TTL: $($RC TTL $MARCA) s   <- el TTL sigue corriendo, no se reinició"
echo "votación abierta: $($RC SCARD $VOTOS:votantes) votantes"
echo "librerías       : $($RC FUNCTION LIST | grep -A1 '^library_name' | grep -v -e '^library_name' -e '^--' | tr '\n' ' ')"

echo "== P.4 docker compose down (sin -v) + up -d: el contenedor se destruye y se crea de nuevo =="
docker compose down > /dev/null 2>&1
echo "-- con el contenedor destruido, el volumen y la carpeta siguen: --"
docker volume ls -q | grep '^fixture2030_redis_data$'
ls "$DIR" | tr '\n' ' '; echo
docker compose up -d --wait > /dev/null 2>&1
echo "clave marcadora : $($RC GET $MARCA) | TTL: $($RC TTL $MARCA) s"
echo "votación abierta: $($RC SCARD $VOTOS:votantes) votantes"
echo "librerías       : $($RC FUNCTION LIST | grep -A1 '^library_name' | grep -v -e '^library_name' -e '^--' | tr '\n' ' ')"

$RC DEL $MARCA > /dev/null
