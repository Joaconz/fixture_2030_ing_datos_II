# Carpeta de Evidencia

En esta carpeta se deben guardar las capturas y salidas de consola que
demuestren el correcto funcionamiento del módulo documental.

## ¿Qué evidencia guardar?

1. **Salida de `seed.js`**: Copiar la salida de consola del script de carga,
   mostrando los conteos finales (64 equipos, ≥ 1000 jugadores, 0 huérfanos).
   - Ejemplo: `evidencia/seed-output.png`

2. **Resultados de `explain()` SIN índices**: Ejecutar el bloque A de
   `queries/queries.js` (descomentándolo) después de borrar los índices.
   Guardar la salida que muestra `COLLSCAN` y `totalDocsExamined`.
   - Ejemplo: `evidencia/explain-sin-indice.png`

3. **Resultados de `explain()` CON índices**: Ejecutar el bloque B de
   `queries/queries.js` (descomentándolo) con los índices creados.
   Guardar la salida que muestra `IXSCAN` y la reducción de documentos examinados.
   - Ejemplo: `evidencia/explain-con-indice.png`

4. **Capturas de mongosh o MongoDB Compass**: Capturas adicionales que muestren
   las colecciones, documentos de ejemplo, resultados de consultas, o la
   estructura de la base de datos visualizada en Compass.
   - Ejemplo: `evidencia/compass-colecciones.png`

## Formato recomendado

- Capturas de pantalla: `.png` o `.jpg`
- Salidas de consola: `.png` (captura) o copiar como texto en un `.md`
- Nombrar los archivos de forma descriptiva

## Nota

El archivo `.gitkeep` existe solo para que Git trackee esta carpeta aunque
esté vacía inicialmente. Puede eliminarse una vez que haya archivos reales.
