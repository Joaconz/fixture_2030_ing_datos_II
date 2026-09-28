# secrets/

Carpeta para la **autorización local** de InfluxDB 2 (`admin-token.json`: usuario, contraseña, organización y token).
Lo crea `sh scripts/autorizacion_local.sh` (lo llama `inicializacion.sh`) y está **ignorado por git** (ver `.gitignore`):
en el repositorio solo existe este README.

- Es un token de laboratorio, generado en cada notebook. No sirve fuera de ella.
- Si se pierde, el servidor ya no acepta un nuevo `influx setup`: empezar de cero con
  `sh scripts/limpieza.sh todo && sh scripts/inicializacion.sh` (se pierden los datos cargados, que se regeneran).
