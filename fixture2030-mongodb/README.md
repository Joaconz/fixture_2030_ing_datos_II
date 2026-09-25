# 🏆 Fixture Mundial 2030 — Módulo Documental (MongoDB)

> **Grupo N°2 — Hito 4**
> Materia: Bases de Datos
> Tecnología: MongoDB 7.0 + Docker Compose

Módulo documental de equipos y jugadores para el Fixture del Mundial 2030.
Implementa dos colecciones relacionadas por **referencia** (`equipos` y `jugadores`),
con validación estricta (`$jsonSchema`), índices optimizados y datos sintéticos
generados con Faker.

---

## 📋 Requisitos previos

| Herramienta        | Versión mínima | Verificación             |
| ------------------ | -------------- | ------------------------ |
| Docker Desktop     | 4.x            | `docker --version`       |
| Docker Compose     | 2.x (incluido) | `docker compose version` |
| Node.js            | 18+            | `node --version`         |
| npm                | 9+             | `npm --version`          |
| mongosh (opcional) | 2.x            | `mongosh --version`      |

> **Nota:** `mongosh` es necesario solo para ejecutar las consultas de
> `queries/queries.js`. Si no lo tenés instalado, podés ejecutar las consultas
> desde la shell de MongoDB dentro del contenedor:
>
> ```bash
> docker exec -it fixture2030_mongo mongosh fixture2030
> ```

---

## 🚀 Puesta en marcha

### 1. Clonar el repositorio

```bash
git clone https://github.com/<tu-usuario>/Grupo_N2_Hito_4_MongoDB_Fixture2030.git
cd Grupo_N2_Hito_4_MongoDB_Fixture2030
```

### 2. Levantar MongoDB con Docker Compose

```bash
docker compose up -d
```

Esto:

- Descarga la imagen `mongo:7.0` (solo la primera vez).
- Crea un contenedor llamado `fixture2030_mongo`.
- Ejecuta automáticamente `init/01-validators.js` para crear las colecciones
  con validadores `$jsonSchema` y los índices.
- Expone MongoDB en `localhost:27017`.
- Crea un volumen persistente `fixture2030_mongo_data`.

#### Verificar que MongoDB está disponible

```bash
docker exec -it fixture2030_mongo mongosh --eval "db.adminCommand('ping')"
```

Deberías ver: `{ ok: 1 }`

### 3. Instalar dependencias y cargar datos

```bash
cd load
npm install
node seed.js
```

O usando el script de npm:

```bash
cd load
npm install
npm run seed
```

El script `seed.js`:

- Genera **64 equipos** con selecciones nacionales reales (códigos FIFA).
- Genera entre **15 y 26 jugadores** sintéticos por equipo (≥ 1000 en total).
- Usa `bulkWrite` con `upsert: true` → **es idempotente**: ejecutarlo dos
  veces no duplica datos ni genera inconsistencias.
- Actualiza el campo `cantidadJugadores` de cada equipo.
- Imprime un resumen final con la verificación de integridad.

**Salida esperada:**

```
✔ Conectado a MongoDB en mongodb://localhost:27017

── Cargando equipos ──
  Equipos insertados: 64

── Cargando jugadores ──
  Jugadores insertados: ~1300
  Total de operaciones: ~1300

══════════════════════════════════════════════
  VERIFICACIÓN FINAL
══════════════════════════════════════════════
  Cantidad de equipos:   64   (esperado: 64)
  Cantidad de jugadores: 1300 (esperado: >= 1000)
  Jugadores huérfanos:   0    (esperado: 0)
══════════════════════════════════════════════

✔ Carga completada exitosamente.
✔ Conexión cerrada.
```

### 4. Ejecutar las consultas

Con `mongosh` instalado localmente:

```bash
mongosh mongodb://localhost:27017/fixture2030 queries/queries.js
```

O desde dentro del contenedor:

```bash
docker exec -it fixture2030_mongo mongosh fixture2030 --file /docker-entrypoint-initdb.d/../queries.js
```

> **Alternativa:** Copiar el archivo al contenedor y ejecutarlo:
>
> ```bash
> docker cp queries/queries.js fixture2030_mongo:/tmp/queries.js
> docker exec -it fixture2030_mongo mongosh fixture2030 --file /tmp/queries.js
> ```

---

## 🔄 Detener, reiniciar y eliminar

### Detener sin perder datos

```bash
docker compose down
```

El volumen `fixture2030_mongo_data` persiste. Al volver a levantar con
`docker compose up -d`, los datos siguen intactos.

### Reiniciar

```bash
docker compose restart
```

### Eliminar todo (incluidos los datos)

```bash
docker compose down -v
```

> **⚠ Atención:** El flag `-v` elimina el volumen persistente. La próxima vez
> que levantes el contenedor, se ejecutarán nuevamente los scripts de
> inicialización y deberás volver a ejecutar `seed.js`.

---

## 📁 Estructura del repositorio

```
Grupo_N2_Hito_4_MongoDB_Fixture2030/
├── docker-compose.yml          # Configuración de Docker Compose (MongoDB 7.0)
├── .gitignore                  # Exclusiones de Git
├── README.md                   # Este archivo
│
├── init/
│   └── 01-validators.js        # Creación de colecciones con $jsonSchema + índices
│                                # (se ejecuta al crear el contenedor)
│
├── load/
│   ├── package.json             # Dependencias Node.js (mongodb, @faker-js/faker)
│   └── seed.js                  # Script de carga idempotente de datos sintéticos
│
├── queries/
│   └── queries.js               # Consultas de ejemplo para mongosh (CRUD,
│                                # agregación, explain)
│
├── docs/
│   └── diseno-documental.md     # Documentación del diseño documental
│                                # (colecciones, relaciones, índices)
│
└── evidencia/
    ├── .gitkeep                 # Placeholder para Git
    └── README.md                # Guía de qué evidencia guardar
```

---

## 📊 Modelo de datos

```
┌─────────────────────┐          ┌─────────────────────────┐
│      equipos        │          │       jugadores          │
├─────────────────────┤          ├─────────────────────────┤
│ _id: "ARG"  (PK)   │◄─────────│ equipoId: "ARG"  (FK)   │
│ nombre              │   1 : N  │ _id: ObjectId    (PK)   │
│ confederacion       │          │ dni              (UK)    │
│ rankingFifa         │          │ nombre                  │
│ grupo               │          │ apellido                │
│ colores {}          │          │ fechaNacimiento         │
│ entrenador          │          │ posicion                │
│ sede                │          │ dorsal                  │
│ cantidadJugadores   │          │ estadisticas {}         │
└─────────────────────┘          └─────────────────────────┘
```

Relación por **referencia**: `jugadores.equipoId` → `equipos._id`

---

## ⚠ Limitaciones conocidas

- **Datos sintéticos**: Los nombres, apellidos y DNI de los jugadores son
  generados con `@faker-js/faker` y no corresponden a jugadores reales.
- **Sin API REST**: Este módulo se limita a la capa de base de datos.
  No incluye servidor backend, endpoints REST ni interfaz gráfica.
- **Sin autenticación**: MongoDB se levanta sin autenticación para simplificar
  el desarrollo. No usar esta configuración en producción.
- **Integridad referencial manual**: MongoDB no tiene foreign keys nativas.
  La integridad se valida programáticamente en `seed.js` con `$lookup`.
- **Confederaciones y rankings**: Los datos de confederaciones son reales,
  pero los rankings FIFA son aproximados y pueden no reflejar el ranking actual.

---

## 👥 Integrantes del Grupo N°2

| Nombre | Legajo |
| ------ | ------ |
| Santiago Pazos | 1172896 |
| Joaquin Nuñez | 1224134 |
| Valentina Frisoli | 1167852 |

---

## 📝 Licencia

Proyecto académico — Uso exclusivamente educativo.
