# Correcciones del profesor — Hito 6

**Fuente:** transmitidas por el grupo (Joaquín Núñez) el 26/09/2026, como texto.

---

Deben corregir la persistencia declarada: la entrega está muy completa, con carga >1M, idempotencia, CRUD, consultas y medición real, pero `docker-compose.yml` usa `~/docker/data/cassandra:/var/lib/cassandra`, que es un bind mount y no el volumen nombrado exigido por RNF2. Para el próximo hito conviene mantener este nivel técnico, pero cumplir literalmente los requisitos de infraestructura.

---

## Lectura para las skills de validación — ✅ corregido (26/09/2026)

Se verificó `docker-compose.yml` (26/09/2026): efectivamente usaba bind mount directo, tal como describe la corrección. **Se corrigió** siguiendo el mismo patrón ya aprobado en Redis (Hito 7, `fixture2030-redis/docker-compose.yml`): se agregó un volumen nombrado Docker (`fixture2030_cassandra_data`, driver `local` con `driver_opts` de tipo `bind` hacia `~/docker/data/cassandra`), se actualizó el bloque de comentarios RNF2 en el compose, y se sincronizó el README (pasos de `mkdir -p` antes del primer `up`, aclaración de qué hace `down -v`, y el comando de "empezar de cero"). Validado con `docker compose config`.

Este era el único punto que la corrección señalaba; el resto de Hito 6 (carga masiva, idempotencia, CRUD, consultas, medición) no se tocó.
