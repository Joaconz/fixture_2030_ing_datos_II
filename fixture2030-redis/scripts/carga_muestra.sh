#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · CARGA DE MUESTRA (RF11)
#  Uso (dentro del contenedor):  docker compose exec -T redis sh /scripts/carga_muestra.sh [usuarios]
#
#  Genera el dataset con awk y lo envía a redis-cli como comandos simples
#  (HSET, EXPIRE, SADD, ZADD, ZINCRBY). Después ejecuta carga_muestra.redis,
#  que verifica lo cargado.
#
#  DETERMINISMO: sin azar; todo sale de fórmulas sobre el índice. Los timestamps
#  de las sesiones parten de un instante fijo de demostración (2030-06-29 16:00 UTC,
#  la misma hora del ranking de tendencia), así que dos cargas dejan exactamente
#  los mismos valores. Lo único relativo es el TTL (EXPIRE), que Redis cuenta
#  desde el momento de la carga.
#  IDEMPOTENTE: HSET/SADD reescriben lo mismo; el ranking y la votación se borran
#  y se vuelven a cargar. Repetir la carga deja los mismos conteos.
# ============================================================
N=${1:-2000}

echo "== 2.1 Estado previo (DBSIZE es O(1), no recorre claves) =="
redis-cli DBSIZE

echo "== 2.2 Generación determinista: $N usuarios, tendencia de 112 partidos, 500 votos MVP =="
awk -v n="$N" 'BEGIN {
  T = 1908979200                 # 2030-06-29T16:00:00Z: instante de la demo
  TTL_INACT = 1800; TTL_ABS = 43200
  split("AM EU AF", REG, " ")    # regiones del Hito 3
  split("web android ios", DISP, " ")

  # Sesiones: usuario i -> USR-000000i; cada 10.º usuario tiene 2 sesiones (web + móvil).
  for (i = 1; i <= n; i++) {
    uid = sprintf("USR-%07d", i)
    ns = (i % 10 == 0) ? 2 : 1
    estado = (i % 33 == 0) ? "BLOQUEADA" : "ACTIVA"     # ~3 %
    rol = (i % 200 == 0) ? "MODERADOR" : "HINCHA"
    hace = (i * 7) % 1800        # actividad escalonada: los TTL restantes se reparten
    for (s = 1; s <= ns; s++) {
      sid = sprintf("demo-ses-%07d-%d", i, s)
      k = "f30:ses:" sid
      printf "HSET %s session_id %s usuario_id %s rol %s region %s dispositivo %s estado %s creada_en %d ultima_actividad %d expira_absoluta %d solicitudes %d\n",
        k, sid, uid, rol, REG[(i % 3) + 1], DISP[((i + s) % 3) + 1], estado,
        T - hace - 60, T - hace, T - hace - 60 + TTL_ABS, (i * 13) % 50
      printf "EXPIRE %s %d\n", k, TTL_INACT - hace
      printf "SADD f30:usr:%s:sesiones %s\n", uid, sid
      printf "EXPIRE f30:usr:%s:sesiones %d\n", uid, TTL_ABS
    }
  }

  # Ranking de tendencia de la hora 2030-06-29 16h: los primeros partidos de cada
  # fase concentran la audiencia. Mismos partido_id que los Hitos 5 y 6.
  print "DEL f30:rank:tendencia:2030062916"
  grupos = "ABCDEFGHIJKLMNOP"; idx = 0
  for (g = 1; g <= 16; g++)
    for (j = 1; j <= 6; j++) { idx++; ids[idx] = "PAR-" substr(grupos, g, 1) "-" j }
  for (j = 1; j <= 16; j++) { idx++; ids[idx] = sprintf("PAR-D16-%02d", j) }
  for (x = 1; x <= idx; x++) {
    visitas = int(100000 / (x * x * 0.02 + 1)) + (x * 37) % 101
    if (ids[x] == "PAR-D16-01") visitas = 250000        # partido de audiencia máxima
    printf "ZADD f30:rank:tendencia:2030062916 %d %s\n", visitas, ids[x]
  }
  print "EXPIRE f30:rank:tendencia:2030062916 7200"

  # Votación MVP abierta de PAR-D16-01: SIN TTL a propósito (memoria_y_escalabilidad §3).
  print "DEL f30:voto:mvp:PAR-D16-01:votantes f30:voto:mvp:PAR-D16-01:ranking"
  split("ARG-10 ARG-9 FRA-10 FRA-7 BRA-11", CAND, " ")
  for (i = 1; i <= 500; i++) {
    printf "SADD f30:voto:mvp:PAR-D16-01:votantes USR-%07d\n", i
    printf "ZINCRBY f30:voto:mvp:PAR-D16-01:ranking 1 %s\n", CAND[((i * 7 + int(i / 3)) % 5) + 1]
  }
}' | redis-cli > /dev/null

grep -v '^#' /scripts/carga_muestra.redis | redis-cli
