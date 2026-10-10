#!/bin/sh
# ============================================================
#  Fixture 2030 — Hito 7 · PRUEBA DE CONCURRENCIA CON CLIENTES PARALELOS (RF8)
#  Corre DENTRO del contenedor:  docker compose exec -T redis sh /scripts/concurrencia_paralela.sh [N]
#
#  N procesos redis-cli simultáneos votan con el MISMO usuario:
#    A) NO atómica: SISMEMBER (chequeo) -> pausa -> SADD + ZINCRBY (acción)
#    B) Atómica:    SADD (chequeo y registro en un solo comando) -> ZINCRBY solo si devolvió 1
#  Resultado esperado: A) puntaje > 1 (voto contado varias veces)   B) puntaje == 1
#  La pausa de A) (0,2 s) solo agranda la ventana de la carrera para que se vea siempre;
#  sin ella la carrera existe igual, es más rara. B) tiene la MISMA pausa entre SADD y
#  ZINCRBY, y aun así da 1: la decisión ya la tomó SADD.
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

echo "== B) Atómica (SADD como guarda): $N clientes, mismo usuario =="
i=0
while [ $i -lt $N ]; do
  (
    if [ "$($R SADD cc:atom:votantes USR-X)" = "1" ]; then         # chequeo + registro atómicos
      sleep 0.2                                                    # misma ventana que en A)
      $R ZINCRBY cc:atom:ranking 1 ARG-10 > /dev/null
    fi
  ) &
  i=$((i+1))
done
wait
echo "puntaje de ARG-10 (correcto = 1): $($R ZSCORE cc:atom:ranking ARG-10)"
echo "votantes registrados (correcto = 1): $($R SCARD cc:atom:votantes)"

$R DEL cc:naive:votantes cc:naive:ranking cc:atom:votantes cc:atom:ranking > /dev/null
