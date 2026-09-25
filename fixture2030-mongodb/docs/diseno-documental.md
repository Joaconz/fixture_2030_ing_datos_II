# Diseño Documental — Fixture Mundial 2030

## 1. Estructura de las colecciones

### Colección `equipos`

Almacena las selecciones nacionales participantes del Fixture Mundial 2030.
El `_id` es el **código FIFA de 3 letras** (clave natural, no ObjectId).

```json
{
  "_id":                "ARG",
  "nombre":             "Argentina",
  "confederacion":      "CONMEBOL",
  "rankingFifa":        1,
  "grupo":              "A",
  "colores": {
    "principal":        "Celeste",
    "alternativo":      "Azul"
  },
  "entrenador":         "Lionel Scaloni",
  "sede":               "Madrid",
  "cantidadJugadores":  23
}
```

| Campo              | Tipo     | Obligatorio | Descripción                                  |
|--------------------|----------|:-----------:|----------------------------------------------|
| `_id`              | string   | ✔           | Código FIFA (patrón `^[A-Z]{3}$`)            |
| `nombre`           | string   | ✔           | Nombre completo de la selección              |
| `confederacion`    | string   | ✔           | Enum: CONMEBOL, UEFA, CAF, AFC, CONCACAF, OFC|
| `rankingFifa`      | int      | ✔           | Posición en el ranking FIFA (≥ 1)            |
| `grupo`            | string   | ✔           | Grupo del fixture (patrón `^[A-P]$`)         |
| `colores`          | object   | ✘           | `{ principal, alternativo }`                 |
| `entrenador`       | string   | ✘           | Director técnico                             |
| `sede`             | string   | ✘           | Ciudad sede asignada                         |
| `cantidadJugadores`| int      | ✘           | Total de jugadores registrados (≥ 0)         |

---

### Colección `jugadores`

Almacena los jugadores de cada selección. El `_id` es un **ObjectId** autogenerado,
y el **DNI** funciona como clave natural única (índice único).

```json
{
  "_id":              ObjectId("..."),
  "dni":              "12345678",
  "nombre":           "Lionel",
  "apellido":         "Messi",
  "fechaNacimiento":  ISODate("1987-06-24T00:00:00Z"),
  "posicion":         "Delantero",
  "dorsal":           10,
  "equipoId":         "ARG",
  "estadisticas": {
    "partidos":       0,
    "goles":          0,
    "asistencias":    0
  }
}
```

| Campo              | Tipo     | Obligatorio | Descripción                                  |
|--------------------|----------|:-----------:|----------------------------------------------|
| `_id`              | ObjectId | (auto)      | Identificador interno de MongoDB             |
| `dni`              | string   | ✔           | Documento de identidad (patrón `^[0-9]{7,8}$`)|
| `nombre`           | string   | ✔           | Nombre/s del jugador                         |
| `apellido`         | string   | ✔           | Apellido/s del jugador                       |
| `fechaNacimiento`  | date     | ✔           | Fecha de nacimiento                          |
| `posicion`         | string   | ✔           | Enum: Arquero, Defensor, Mediocampista, Delantero |
| `dorsal`           | int      | ✔           | Número de camiseta (1–99)                    |
| `equipoId`         | string   | ✔           | Código FIFA del equipo (patrón `^[A-Z]{3}$`) |
| `estadisticas`     | object   | ✘           | `{ partidos, goles, asistencias }` (int ≥ 0) |

---

## 2. Decisión de diseño: relación por referencia

Se optó por **referenciar** a los jugadores desde la colección `jugadores` hacia
`equipos` a través del campo `equipoId`, en lugar de embeber un array de jugadores
dentro del documento de equipo.

### Justificación

| Criterio                 | Embedding (descartado)                  | Referencia (elegido)                     |
|--------------------------|------------------------------------------|------------------------------------------|
| **Tamaño del documento** | Puede superar los 16 MB con muchos jugadores embebidos y sus estadísticas | Cada documento se mantiene pequeño       |
| **Acceso independiente** | No es posible consultar jugadores sin cargar el equipo completo | Los jugadores se consultan, filtran y paginan de forma independiente |
| **Actualización parcial**| Actualizar un jugador requiere operar sobre el array del equipo ($push, $pull, $set con posición) | Actualizar un jugador es un updateOne directo |
| **Integridad referencial**| Implícita (el jugador "vive" dentro del equipo) | Se garantiza programáticamente y se valida con `$lookup` + `$match` |
| **Agregación cross-collection** | No necesaria (todo en un doc) | Se resuelve con `$lookup` (demostrado en el pipeline de queries.js) |

La relación **1:N** (un equipo tiene muchos jugadores) con acceso frecuente
independiente a ambas entidades justifica la separación en dos colecciones
con referencia por `equipoId`.

---

## 3. Reglas de validación

Ambas colecciones usan `$jsonSchema` con `validationLevel: "strict"` y
`validationAction: "error"`, definidos en [`init/01-validators.js`](../init/01-validators.js).

- **Equipos**: Todos los campos obligatorios se validan con tipos y patrones.
  Los campos opcionales (`colores`, `entrenador`, `sede`, `cantidadJugadores`)
  están declarados en el schema pero no son requeridos.
  Se usa `additionalProperties: false` para rechazar campos no declarados.

- **Jugadores**: Análogo a equipos. El campo `estadisticas` es un subdocumento
  opcional con tres campos numéricos (`partidos`, `goles`, `asistencias`).
  Se usa `additionalProperties: false`.

---

## 4. Índices

| Colección   | Índice                                   | Campos                   | Tipo   | Consulta que optimiza                                   |
|-------------|------------------------------------------|--------------------------|--------|---------------------------------------------------------|
| `equipos`   | `idx_equipos_grupo`                      | `{ grupo: 1 }`          | Simple | Obtener equipos de un grupo específico (fase de grupos) |
| `jugadores` | `idx_jugadores_dni_unique`               | `{ dni: 1 }`            | Único  | Búsqueda por DNI, garantía de unicidad                  |
| `jugadores` | `idx_jugadores_equipoId_posicion`        | `{ equipoId: 1, posicion: 1 }` | Compuesto | Filtrar jugadores por equipo y posición          |
| `jugadores` | `idx_jugadores_apellido_nombre`          | `{ apellido: 1, nombre: 1 }` | Compuesto | Ordenamiento alfabético y paginación            |

Los índices se crean automáticamente al inicializar el contenedor, mediante el
script montado en `/docker-entrypoint-initdb.d/`.
