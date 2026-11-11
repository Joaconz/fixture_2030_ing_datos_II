# Optimización de carga

## 1. Qué se eligió optimizar y por qué

**La concurrencia del cargador de Cassandra** (`carga_masiva.py --concurrencia`, escrituras en vuelo).

- Cassandra es la carga más larga de la arquitectura (1.050.000 comentarios = 2.100.000 filas) y, con la admisión por memoria, corre **sola**. Su tiempo de carga suma directo al reloj total, en paralelo y en secuencial.
- El módulo dejó esta mejora pendiente. `fixture2030-cassandra/docs/rendimiento.md` plantea como hipótesis 1 que *"la tasa sube con la concurrencia hasta un techo… que pone la CPU compartida"* y la marca **"No verificada: solo se midió con concurrencia 128"**.
- InfluxDB ya tiene su barrido de lote y de hilos (`fixture2030-influxdb/docs/pruebas_y_rendimiento.md` §4.1), así que repetirlo no aporta.
- Otra opción era el orden de arranque, pero no cambia nada: con ~1,9 GB de presupuesto solo MongoDB y Redis entran juntos, y las tres bases pesadas van de a una en cualquier orden.

## 2. Hipótesis

<!-- HIPOTESIS -->

## 3. Método

<!-- METODO -->

## 4. Resultado

<!-- RESULTADO -->
