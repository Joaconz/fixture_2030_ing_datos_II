# secrets/

Carpeta para la **autorización local** de InfluxDB 3 Core (`admin-token.json`: el token de administración de la instancia).
Lo crea `sh scripts/autorizacion_local.sh` (lo llama `inicializacion.sh`) con `influxdb3 create token --admin`, y está **ignorado por git** (ver `.gitignore`):
en el repositorio solo existe este README.

- Es un token de laboratorio, generado en cada notebook. No sirve fuera de ella.
- InfluxDB 3 lo muestra una sola vez. Si se pierde, el servidor no crea otro token de administración: empezar de cero con
  `sh scripts/limpieza.sh todo && sh scripts/inicializacion.sh` (se pierden los datos cargados, que se regeneran).
