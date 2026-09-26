# Correcciones del profesor — Hito 1

**Fuente:** transmitidas por el grupo (Joaquín Núñez) el 26/09/2026, como texto — no hay documento formal adjunto de la corrección en sí, solo la entrega original (`hito-1-analisis-requisitos.md`).

---

Deben ajustar el alcance a lo visto en Clase 1: aparecen MVCC, CTE recursivas, consenso multi-región, peer-to-peer, claves de partición compuestas, TTL, downsampling, herencia en IRIS y detalles internos de varios motores que todavía no fueron desarrollados. Para el próximo hito conviene justificar con volumen, velocidad, acceso, esquema, escalabilidad y ACID/BASE, sin adelantar implementación específica.

---

## Estado — ✅ aplicada en el documento (26/09/2026)

Ver "Historial de revisión" al final de [`hito-1-analisis-requisitos.md`](./hito-1-analisis-requisitos.md) para el detalle de qué pasajes se reescribieron.

## Lectura para las skills de validación

Esta corrección **no cambió ninguna decisión de modelo de datos** — fue una corrección de *calibración académica* (no adelantar contenido de clases futuras), no de arquitectura. No genera entradas en [`../ESTADO-CANONICO-NECESIDADES.md`](../ESTADO-CANONICO-NECESIDADES.md).

Sí es relevante para `/validar-hito`: si un hito nuevo justifica una decisión citando mecanismos internos de un motor que la cursada todavía no vio en clase, es la misma clase de desprolijidad que esta corrección señaló acá. Vale la pena chequearlo, aunque no sea un chequeo de consistencia entre hitos sino de alcance.
