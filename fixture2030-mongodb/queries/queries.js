const db = db.getSiblingDB("fixture2030");

print("══════════════════════════════════════════════════════════════════");
print("  CONSULTAS — Fixture Mundial 2030 (Módulo Documental)");
print("══════════════════════════════════════════════════════════════════\n");

print("── 1. Inserción de un equipo nuevo y un jugador nuevo ──");

db.equipos.deleteOne({ _id: "TST" });
db.jugadores.deleteOne({ dni: "99999999" });

db.equipos.insertOne({
  _id:            "TST",
  nombre:         "Equipo de Prueba",
  confederacion:  "UEFA",
  rankingFifa:    NumberInt(200),
  grupo:          "A",
  entrenador:     "Juan Pérez",
  sede:           "Madrid",
  colores:        { principal: "Blanco", alternativo: "Negro" },
  cantidadJugadores: NumberInt(1)
});

db.jugadores.insertOne({
  dni:              "99999999",
  nombre:           "Carlos",
  apellido:         "González",
  fechaNacimiento:  new Date("1998-03-15"),
  posicion:         "Delantero",
  dorsal:           NumberInt(9),
  equipoId:         "TST",
  estadisticas:     {
    partidos:    NumberInt(10),
    goles:       NumberInt(7),
    asistencias: NumberInt(3)
  }
});

print("  ✔ Equipo 'TST' y jugador 'González, Carlos' insertados.\n");

print("── 2. Recuperación por identificador ──");

print("  Equipo con _id = 'ARG':");
printjson(db.equipos.findOne({ _id: "ARG" }));

print("\n  Jugador con dni = '99999999':");
printjson(db.jugadores.findOne({ dni: "99999999" }));
print("");

print("── 3. Recuperación filtrada: delanteros de ARG con >= 5 goles ──");

const delanteros = db.jugadores.find({
  equipoId:              "ARG",
  posicion:              "Delantero",
  "estadisticas.goles":  { $gte: 5 }
}).toArray();

if (delanteros.length === 0) {
  print("  (Sin resultados — los datos sintéticos tienen estadísticas en 0)");
  print("  Mostrando en su lugar delanteros de ARG (sin filtro de goles):");
  printjson(db.jugadores.find({ equipoId: "ARG", posicion: "Delantero" }).limit(3).toArray());
} else {
  printjson(delanteros);
}
print("");

print("── 4. Proyección: nombre, apellido, dorsal, posicion de jugadores de BRA ──");

const proyeccion = db.jugadores.find(
  { equipoId: "BRA" },
  {
    projection: {
      _id:      0,
      nombre:   1,
      apellido: 1,
      dorsal:   1,
      posicion: 1
    }
  }
).toArray();

printjson(proyeccion);
print("");

// ---------------------------------------------------------------------------
// 5. ORDEN Y PAGINACIÓN
//    Objetivo: Listado general de jugadores ordenado alfabéticamente por
//    apellido y nombre, con paginación (skip/limit). Muestra la "página 2"
//    (registros 11 a 20).
// ---------------------------------------------------------------------------
print("── 5. Orden y paginación: jugadores ordenados por apellido/nombre (pág 2) ──");

const PAGE_SIZE = 10;
const PAGE_NUM  = 2;   // Página 2 (skip = 10)

const pagina = db.jugadores.find(
  {},
  { projection: { _id: 0, apellido: 1, nombre: 1, equipoId: 1, dorsal: 1 } }
)
  .sort({ apellido: 1, nombre: 1 })
  .skip((PAGE_NUM - 1) * PAGE_SIZE)
  .limit(PAGE_SIZE)
  .toArray();

print(`  Página ${PAGE_NUM} (registros ${(PAGE_NUM - 1) * PAGE_SIZE + 1} a ${PAGE_NUM * PAGE_SIZE}):`);
printjson(pagina);
print("");

// ---------------------------------------------------------------------------
// 6. ACTUALIZACIÓN
//    Objetivo: Demostrar updateOne para modificar un campo de equipo
//    (entrenador) y $inc para incrementar estadísticas de un jugador.
// ---------------------------------------------------------------------------
print("── 6. Actualización de equipo y jugador ──");

// 6a. Cambiar el entrenador de Argentina
const resEquipo = db.equipos.updateOne(
  { _id: "ARG" },
  { $set: { entrenador: "Marcelo Gallardo" } }
);
print(`  Entrenador de ARG actualizado: matchedCount=${resEquipo.matchedCount}, modifiedCount=${resEquipo.modifiedCount}`);

// 6b. Incrementar goles y partidos del jugador de prueba
const resJugador = db.jugadores.updateOne(
  { dni: "99999999" },
  {
    $inc: {
      "estadisticas.goles":    NumberInt(2),
      "estadisticas.partidos": NumberInt(1)
    }
  }
);
print(`  Estadísticas de González actualizadas: matchedCount=${resJugador.matchedCount}, modifiedCount=${resJugador.modifiedCount}`);

print("  Estado actual del jugador:");
printjson(db.jugadores.findOne({ dni: "99999999" }, { projection: { _id: 0, nombre: 1, apellido: 1, estadisticas: 1 } }));
print("");

// ---------------------------------------------------------------------------
// 7. PIPELINE DE AGREGACIÓN
//    Objetivo: Por cada equipo, calcular la cantidad de jugadores, la edad
//    promedio y los goles totales. Hacer $lookup con la colección equipos
//    para traer el nombre del equipo. Ordenar de mayor a menor por goles.
// ---------------------------------------------------------------------------
print("── 7. Pipeline de agregación: estadísticas por equipo ──");

const pipeline = [
  // Agrupar jugadores por equipo
  {
    $group: {
      _id:              "$equipoId",
      cantidadJugadores: { $sum: 1 },
      edadPromedio: {
        $avg: {
          $divide: [
            { $subtract: [new Date(), "$fechaNacimiento"] },
            // Milisegundos en un año aprox. (365.25 días)
            1000 * 60 * 60 * 24 * 365.25
          ]
        }
      },
      golesTotales: { $sum: "$estadisticas.goles" }
    }
  },
  // Lookup para traer el nombre del equipo
  {
    $lookup: {
      from:         "equipos",
      localField:   "_id",
      foreignField: "_id",
      as:           "equipo"
    }
  },
  // Desestructurar el array de equipo (siempre 1 elemento)
  { $unwind: "$equipo" },
  // Proyectar los campos finales
  {
    $project: {
      _id:               0,
      codigoFifa:        "$_id",
      nombreEquipo:      "$equipo.nombre",
      cantidadJugadores: 1,
      edadPromedio:      { $round: ["$edadPromedio", 1] },
      golesTotales:      1
    }
  },
  // Ordenar de mayor a menor por goles totales
  { $sort: { golesTotales: -1, nombreEquipo: 1 } }
];

const resultadoAgregacion = db.jugadores.aggregate(pipeline).toArray();
printjson(resultadoAgregacion.slice(0, 10));  // Mostrar top 10
print(`  ... (mostrando top 10 de ${resultadoAgregacion.length} equipos)\n`);

// ---------------------------------------------------------------------------
// 8. EXPLAIN — Para comparar rendimiento antes/después de índices
//    Objetivo: Ejecutar explain("executionStats") sobre la consulta filtrada
//    del punto 3, para analizar el plan de ejecución y evidenciar la mejora
//    de rendimiento al usar índices.
//
//    INSTRUCCIONES:
//    - Descomentar el bloque correspondiente.
//    - Ejecutar UNA VEZ sin índices (borrarlos primero si ya existen).
//    - Guardar la salida en evidencia/.
//    - Ejecutar OTRA VEZ con los índices creados.
//    - Guardar la salida y comparar totalDocsExamined, executionTimeMillis, etc.
// ---------------------------------------------------------------------------
print("── 8. EXPLAIN (bloques comentados — descomentar para ejecutar) ──\n");

// ---- BLOQUE A: explain ANTES de crear índices ----
// Para usar este bloque:
//   1. Borrar los índices: db.jugadores.dropIndex("idx_jugadores_equipoId_posicion")
//   2. Descomentar el bloque
//   3. Ejecutar y guardar la salida

/*
print("=== EXPLAIN SIN ÍNDICE (COLLSCAN esperado) ===");
const explainSinIndice = db.jugadores.find({
  equipoId:              "ARG",
  posicion:              "Delantero",
  "estadisticas.goles":  { $gte: 5 }
}).explain("executionStats");
printjson(explainSinIndice);
*/

// ---- BLOQUE B: explain DESPUÉS de crear índices ----
// Para usar este bloque:
//   1. Asegurarse de que el índice existe:
//      db.jugadores.createIndex({ equipoId: 1, posicion: 1 }, { name: "idx_jugadores_equipoId_posicion" })
//   2. Descomentar el bloque
//   3. Ejecutar y guardar la salida

/*
print("=== EXPLAIN CON ÍNDICE (IXSCAN esperado) ===");
const explainConIndice = db.jugadores.find({
  equipoId:              "ARG",
  posicion:              "Delantero",
  "estadisticas.goles":  { $gte: 5 }
}).explain("executionStats");
printjson(explainConIndice);
*/

print("  ℹ Los bloques de explain() están comentados.");
print("  Descomentá el bloque A o B según corresponda y ejecutá manualmente.\n");

print("── Limpieza: eliminando datos de prueba (TST) ──");
db.jugadores.deleteOne({ dni: "99999999" });
db.equipos.deleteOne({ _id: "TST" });
print("  ✔ Datos de prueba eliminados.\n");

print("══════════════════════════════════════════════════════════════════");
print("  Todas las consultas ejecutadas exitosamente.");
print("══════════════════════════════════════════════════════════════════");
