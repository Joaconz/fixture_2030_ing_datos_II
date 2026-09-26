#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · PRUEBA DE CONCURRENCIA CON CLIENTES PARALELOS (RF8)
#  Corre DENTRO del contenedor:  docker compose exec -T redis sh /scripts/concurrencia_paralela.sh
#
#  Compara, con N procesos redis-cli simultáneos que votan con el MISMO usuario:
#    A) secuencia NO atómica (SISMEMBER -> pausa -> SADD -> ZINCRBY): el riesgo real
#    B) FCALL voto_emitir (atómica)
#  Resultado esperado: A) puntaje > 1 (voto contado varias veces)   B) puntaje == 1
#  La pausa de A) (0,2 s) sólo agranda la ventana de la carrera para que se vea siempre;
#  sin ella la carrera existe igual, es más rara.
# ============================================================
N=${1:-20}
R="redis-cli"
$R DEL cc:naive:votantes cc:naive:ranking cc:atom:votantes cc:atom:ranking > /dev/null

echo "== A) NO atómica: $N clientes, mismo usuario =="
i=0
while [ $i -lt $N ]; do
  (
    if [ "$($R SISMEMBER cc:naive:votantes USR-X)" = "0" ]; then   # 1) chequeo
      sleep 0.2                                                    # 2) ventana de carrera
      $R SADD cc:naive:votantes USR-X > /dev/null                  # 3) acción
      $R ZINCRBY cc:naive:ranking 1 ARG-10 > /dev/null
    fi
  ) &
  i=$((i+1))
done
wait
echo "puntaje de ARG-10 (correcto = 1): $($R ZSCORE cc:naive:ranking ARG-10)"

echo "== B) Atómica (FCALL voto_emitir): $N clientes, mismo usuario =="
i=0
while [ $i -lt $N ]; do
  $R FCALL voto_emitir 2 cc:atom:votantes cc:atom:ranking USR-X ARG-10 > /dev/null &
  i=$((i+1))
done
wait
echo "puntaje de ARG-10 (correcto = 1): $($R ZSCORE cc:atom:ranking ARG-10)"

$R DEL cc:naive:votantes cc:naive:ranking cc:atom:votantes cc:atom:ranking > /dev/null
