// =============================================================================
// 01-validators.js
// Script de inicialización de MongoDB: crea las colecciones con validadores
// $jsonSchema (validationLevel: "strict") y los índices necesarios.
// Se ejecuta automáticamente al crear el contenedor por primera vez.
// =============================================================================

// Seleccionar la base de datos
const db = db.getSiblingDB("fixture2030");

print("=== Inicializando base de datos fixture2030 ===");

// ---------------------------------------------------------------------------
// 1. Colección "equipos"
// ---------------------------------------------------------------------------
print("Creando colección 'equipos' con validador $jsonSchema...");

db.createCollection("equipos", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      title: "Validador de Equipos",
      required: ["_id", "nombre", "confederacion", "rankingFifa", "grupo"],
      properties: {
        _id: {
          bsonType: "string",
          pattern: "^[A-Z]{3}$",
          description: "Código FIFA de 3 letras en mayúsculas (ej: ARG, BRA)"
        },
        nombre: {
          bsonType: "string",
          description: "Nombre completo de la selección nacional"
        },
        confederacion: {
          bsonType: "string",
          enum: ["CONMEBOL", "UEFA", "CAF", "AFC", "CONCACAF", "OFC"],
          description: "Confederación continental a la que pertenece"
        },
        rankingFifa: {
          bsonType: "int",
          minimum: 1,
          description: "Posición en el ranking FIFA (>= 1)"
        },
        grupo: {
          bsonType: "string",
          pattern: "^[A-P]$",
          description: "Grupo asignado en el fixture (A a P)"
        },
        colores: {
          bsonType: "object",
          description: "Colores de la camiseta (ej: { principal, alternativo })",
          properties: {
            principal: { bsonType: "string" },
            alternativo: { bsonType: "string" }
          }
        },
        entrenador: {
          bsonType: "string",
          description: "Nombre del director técnico"
        },
        sede: {
          bsonType: "string",
          description: "Ciudad sede asignada para los partidos de local"
        },
        cantidadJugadores: {
          bsonType: "int",
          minimum: 0,
          description: "Cantidad de jugadores registrados en el plantel"
        }
      },
      additionalProperties: false
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

print("  ✔ Colección 'equipos' creada.");

// ---------------------------------------------------------------------------
// 2. Colección "jugadores"
// ---------------------------------------------------------------------------
print("Creando colección 'jugadores' con validador $jsonSchema...");

db.createCollection("jugadores", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      title: "Validador de Jugadores",
      required: [
        "dni",
        "nombre",
        "apellido",
        "fechaNacimiento",
        "posicion",
        "dorsal",
        "equipoId"
      ],
      properties: {
        _id: {
          bsonType: "objectId",
          description: "Identificador interno generado por MongoDB"
        },
        dni: {
          bsonType: "string",
          pattern: "^[0-9]{7,8}$",
          description: "Documento de identidad (7 u 8 dígitos numéricos)"
        },
        nombre: {
          bsonType: "string",
          description: "Nombre/s del jugador"
        },
        apellido: {
          bsonType: "string",
          description: "Apellido/s del jugador"
        },
        fechaNacimiento: {
          bsonType: "date",
          description: "Fecha de nacimiento del jugador"
        },
        posicion: {
          bsonType: "string",
          enum: ["Arquero", "Defensor", "Mediocampista", "Delantero"],
          description: "Posición en la cancha"
        },
        dorsal: {
          bsonType: "int",
          minimum: 1,
          maximum: 99,
          description: "Número de camiseta (1-99)"
        },
        equipoId: {
          bsonType: "string",
          pattern: "^[A-Z]{3}$",
          description: "Código FIFA del equipo al que pertenece (referencia)"
        },
        estadisticas: {
          bsonType: "object",
          description: "Estadísticas acumuladas del jugador",
          properties: {
            partidos: {
              bsonType: "int",
              minimum: 0,
              description: "Partidos jugados"
            },
            goles: {
              bsonType: "int",
              minimum: 0,
              description: "Goles anotados"
            },
            asistencias: {
              bsonType: "int",
              minimum: 0,
              description: "Asistencias realizadas"
            }
          }
        }
      },
      additionalProperties: false
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

print("  ✔ Colección 'jugadores' creada.");

// ---------------------------------------------------------------------------
// 3. Índices
// ---------------------------------------------------------------------------
print("Creando índices...");

// Índice en equipos por grupo (para consultas de fase de grupos)
db.equipos.createIndex(
  { grupo: 1 },
  { name: "idx_equipos_grupo" }
);
print("  ✔ Índice idx_equipos_grupo creado.");

// Índice único en jugadores por DNI (clave natural, evita duplicados)
db.jugadores.createIndex(
  { dni: 1 },
  { unique: true, name: "idx_jugadores_dni_unique" }
);
print("  ✔ Índice idx_jugadores_dni_unique creado.");

// Índice compuesto en jugadores por equipo y posición (para filtros combinados)
db.jugadores.createIndex(
  { equipoId: 1, posicion: 1 },
  { name: "idx_jugadores_equipoId_posicion" }
);
print("  ✔ Índice idx_jugadores_equipoId_posicion creado.");

// Índice compuesto en jugadores por apellido y nombre (para ordenamiento alfabético)
db.jugadores.createIndex(
  { apellido: 1, nombre: 1 },
  { name: "idx_jugadores_apellido_nombre" }
);
print("  ✔ Índice idx_jugadores_apellido_nombre creado.");

print("=== Inicialización completada exitosamente ===");
