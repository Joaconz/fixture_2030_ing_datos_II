# Integridad — corrida 2053

Validado leyendo Cassandra directo el 2026-10-29T20:56:03+00:00.

| Verificación | Resultado | Detalle |
|---|:-:|---|
| I1 escritos en Cassandra = POST 201 de k6 | ✅ | 13314 filas únicas · 13314 POST 201 · 0 reintentos 200 · 0 POST con error |
| I2 sin comentario_id duplicados | ✅ | 0 duplicados |
| I3 vista por usuario = vista por partido | ✅ | 0 filas sin su par |
| I4 contenido sin alterar | ✅ | 0 alterados |
| I5 todo en PAR-D16-01, ventana 17:30 | ✅ | 0 fuera de rango |

**Resultado: ✅ integridad verificada**
