const { MongoClient, Int32 } = require("mongodb");
const { faker } = require("@faker-js/faker");

// ── Configuración 
const MONGO_URI = process.env.MONGO_URI || "mongodb://localhost:27017";
const DB_NAME   = "fixture2030";

// ── Lista de 64 selecciones nacionales reales
// Cada entrada: [codigoFifa, nombre, confederacion, rankingFifa]
const EQUIPOS_DATA = [
  // ── CONMEBOL (10) ──
  ["ARG", "Argentina",           "CONMEBOL",  1],
  ["BRA", "Brasil",              "CONMEBOL",  5],
  ["URY", "Uruguay",             "CONMEBOL",  11],
  ["COL", "Colombia",            "CONMEBOL",  12],
  ["CHL", "Chile",               "CONMEBOL",  18],
  ["PRY", "Paraguay",            "CONMEBOL",  38],
  ["PER", "Perú",                "CONMEBOL",  32],
  ["ECU", "Ecuador",             "CONMEBOL",  33],
  ["VEN", "Venezuela",           "CONMEBOL",  56],
  ["BOL", "Bolivia",             "CONMEBOL",  83],
  // ── UEFA (20) ──
  ["ESP", "España",              "UEFA",       3],
  ["FRA", "Francia",             "UEFA",       2],
  ["GER", "Alemania",            "UEFA",      15],
  ["ITA", "Italia",              "UEFA",       9],
  ["POR", "Portugal",            "UEFA",       6],
  ["NED", "Países Bajos",        "UEFA",       7],
  ["ENG", "Inglaterra",          "UEFA",       4],
  ["BEL", "Bélgica",             "UEFA",       8],
  ["CRO", "Croacia",             "UEFA",      10],
  ["SRB", "Serbia",              "UEFA",      26],
  ["SUI", "Suiza",               "UEFA",      20],
  ["DEN", "Dinamarca",           "UEFA",      19],
  ["AUT", "Austria",             "UEFA",      22],
  ["POL", "Polonia",             "UEFA",      28],
  ["UKR", "Ucrania",             "UEFA",      24],
  ["CZE", "República Checa",     "UEFA",      36],
  ["SWE", "Suecia",              "UEFA",      35],
  ["TUR", "Turquía",             "UEFA",      40],
  ["SCO", "Escocia",             "UEFA",      39],
  ["HUN", "Hungría",             "UEFA",      30],
  // ── CAF (10) ──
  ["MAR", "Marruecos",           "CAF",       13],
  ["SEN", "Senegal",             "CAF",       17],
  ["NGA", "Nigeria",             "CAF",       31],
  ["CMR", "Camerún",             "CAF",       46],
  ["GHA", "Ghana",               "CAF",       60],
  ["CIV", "Costa de Marfil",     "CAF",       42],
  ["TUN", "Túnez",               "CAF",       41],
  ["ALG", "Argelia",             "CAF",       48],
  ["EGY", "Egipto",              "CAF",       37],
  ["ZAF", "Sudáfrica",           "CAF",       59],
  // ── AFC (10) ──
  ["JPN", "Japón",               "AFC",       14],
  ["KOR", "Corea del Sur",       "AFC",       23],
  ["AUS", "Australia",           "AFC",       25],
  ["IRN", "Irán",                "AFC",       21],
  ["SAU", "Arabia Saudita",      "AFC",       53],
  ["QAT", "Catar",               "AFC",       50],
  ["UZB", "Uzbekistán",          "AFC",       62],
  ["IRQ", "Irak",                "AFC",       55],
  ["CHN", "China",               "AFC",       80],
  ["IND", "India",               "AFC",      100],
  // ── CONCACAF (10) ──
  ["USA", "Estados Unidos",      "CONCACAF",  16],
  ["MEX", "México",              "CONCACAF",  27],
  ["CAN", "Canadá",              "CONCACAF",  34],
  ["CRC", "Costa Rica",          "CONCACAF",  43],
  ["JAM", "Jamaica",             "CONCACAF",  57],
  ["HON", "Honduras",            "CONCACAF",  73],
  ["PAN", "Panamá",              "CONCACAF",  49],
  ["SLV", "El Salvador",         "CONCACAF",  78],
  ["TRI", "Trinidad y Tobago",   "CONCACAF",  99],
  ["HAI", "Haití",               "CONCACAF", 101],
  // ── OFC (4) ──
  ["NZL", "Nueva Zelanda",       "OFC",       93],
  ["FIJ", "Fiyi",                "OFC",      155],
  ["PNG", "Papúa Nueva Guinea",  "OFC",      161],
  ["NCL", "Nueva Caledonia",     "OFC",      170]
];

// ── Grupos A-P (se asignan en orden: primeros 4 → A, siguientes 4 → B, …)
const GRUPOS = "ABCDEFGHIJKLMNOP".split("");

// ── Entrenadores ficticios por equipo (para agregar color a los datos) ──
const ENTRENADORES = [
  "Lionel Scaloni", "Dorival Júnior", "Marcelo Bielsa", "Néstor Lorenzo",
  "Ricardo Gareca", "Alfaro Gustavo", "Jorge Fossati", "Félix Sánchez",
  "Fernando Batista", "Óscar Villegas",
  "Luis de la Fuente", "Didier Deschamps", "Julian Nagelsmann", "Luciano Spalletti",
  "Roberto Martínez", "Ronald Koeman", "Thomas Tuchel", "Domenico Tedesco",
  "Zlatko Dalić", "Dragan Stojković", "Murat Yakin", "Kasper Hjulmand",
  "Ralf Rangnick", "Michał Probierz", "Serhiy Rebrov", "Ivan Hašek",
  "Jon Dahl Tomasson", "Vincenzo Montella", "Steve Clarke", "Marco Rossi",
  "Walid Regragui", "Aliou Cissé", "José Peseiro", "Rigobert Song",
  "Chris Hughton", "Jean-Louis Gasset", "Jalel Kadri", "Djamel Belmadi",
  "Rui Vitória", "Hugo Broos",
  "Hajime Moriyasu", "Jürgen Klinsmann", "Graham Arnold", "Amir Ghalenoei",
  "Roberto Mancini", "Félix Sánchez Bas", "Srecko Katanec", "Jesús Casas",
  "Branko Ivanković", "Igor Stimac",
  "Gregg Berhalter", "Jaime Lozano", "Jesse Marsch", "Gustavo Alfaro",
  "Heimir Hallgrímsson", "Diego Vázquez", "Thomas Christiansen", "Hugo Pérez",
  "Angus Eve", "Nicolas Délépine",
  "Darren Bazeley", "Rob Sherman", "Marcos Gusmão", "Thierry Henry"
];

// Sedes ficticias repartidas
const SEDES = [
  "Madrid", "Rabat", "Lisboa", "Barcelona", "Casablanca",
  "Sevilla", "Marrakech", "Bilbao", "Tánger", "Oporto",
  "Valencia", "Fez", "Málaga", "Agadir", "Vigo", "Buenos Aires"
];

// ── Posiciones válidas 
const POSICIONES = ["Arquero", "Defensor", "Mediocampista", "Delantero"];

// ── Colores de camiseta genéricos
const COLORES_PRINCIPALES = [
  "Blanco", "Azul", "Rojo", "Amarillo", "Verde",
  "Celeste", "Naranja", "Negro", "Borgoña", "Dorado"
];
const COLORES_ALTERNATIVOS = [
  "Negro", "Blanco", "Azul", "Rojo", "Gris",
  "Amarillo", "Verde", "Celeste", "Naranja", "Borgoña"
];

// ── Funciones auxiliares 

/**
 * Genera un DNI de 8 dígitos como string, usando un Set para evitar colisiones.
 */
const dnisGenerados = new Set();
function generarDniUnico() {
  let dni;
  do {
    // Generar número entre 10000000 y 99999999
    dni = faker.number.int({ min: 10000000, max: 99999999 }).toString();
  } while (dnisGenerados.has(dni));
  dnisGenerados.add(dni);
  return dni;
}

/**
 * Genera una fecha de nacimiento entre 18 y 38 años atrás.
 */
function generarFechaNacimiento() {
  const hoy = new Date();
  const desde = new Date(hoy.getFullYear() - 38, hoy.getMonth(), hoy.getDate());
  const hasta = new Date(hoy.getFullYear() - 18, hoy.getMonth(), hoy.getDate());
  return faker.date.between({ from: desde, to: hasta });
}

// =============================================================================
// MAIN
// =============================================================================
async function main() {
  const client = new MongoClient(MONGO_URI);

  try {
    await client.connect();
    console.log("✔ Conectado a MongoDB en", MONGO_URI);

    const db = client.db(DB_NAME);
    const colEquipos   = db.collection("equipos");
    const colJugadores = db.collection("jugadores");

    // ────────────────────────────────────────────────────────────────────────
    // PASO 1: Generar y cargar equipos (bulkWrite con upsert por _id)
    // ────────────────────────────────────────────────────────────────────────
    console.log("\n── Cargando equipos ──");

    const equiposOps = EQUIPOS_DATA.map(([codigo, nombre, confederacion, ranking], i) => {
      const grupoIndex = Math.floor(i / 4);
      const grupo = GRUPOS[grupoIndex];

      return {
        updateOne: {
          filter: { _id: codigo },
          update: {
            $set: {
              nombre,
              confederacion,
              rankingFifa: new Int32(ranking),
              grupo,
              entrenador: ENTRENADORES[i] || faker.person.fullName(),
              sede: SEDES[i % SEDES.length],
              colores: {
                principal:   COLORES_PRINCIPALES[i % COLORES_PRINCIPALES.length],
                alternativo: COLORES_ALTERNATIVOS[i % COLORES_ALTERNATIVOS.length]
              }
              // cantidadJugadores se actualiza después
            }
          },
          upsert: true
        }
      };
    });

    const resultEquipos = await colEquipos.bulkWrite(equiposOps, { ordered: false });
    console.log(`  Equipos insertados: ${resultEquipos.upsertedCount}`);
    console.log(`  Equipos actualizados: ${resultEquipos.modifiedCount}`);

    // ────────────────────────────────────────────────────────────────────────
    // PASO 2: Generar y cargar jugadores (bulkWrite con upsert por dni)
    // ────────────────────────────────────────────────────────────────────────
    console.log("\n── Cargando jugadores ──");

    const jugadoresOps = [];

    for (const [codigo] of EQUIPOS_DATA) {
      // Entre 15 y 26 jugadores por equipo
      const cantJugadores = faker.number.int({ min: 15, max: 26 });

      for (let dorsal = 1; dorsal <= cantJugadores; dorsal++) {
        const dni = generarDniUnico();
        const posicion = faker.helpers.arrayElement(POSICIONES);

        jugadoresOps.push({
          updateOne: {
            filter: { dni },
            update: {
              $set: {
                nombre:           faker.person.firstName(),
                apellido:         faker.person.lastName(),
                fechaNacimiento:  generarFechaNacimiento(),
                posicion,
                dorsal:           new Int32(dorsal),
                equipoId:         codigo,
                estadisticas: {
                  partidos:    new Int32(0),
                  goles:       new Int32(0),
                  asistencias: new Int32(0)
                }
              }
            },
            upsert: true
          }
        });
      }
    }

    // Ejecutar en lotes de 500 para evitar problemas de tamaño
    const BATCH_SIZE = 500;
    let totalInsertados   = 0;
    let totalActualizados = 0;

    for (let i = 0; i < jugadoresOps.length; i += BATCH_SIZE) {
      const batch = jugadoresOps.slice(i, i + BATCH_SIZE);
      const res = await colJugadores.bulkWrite(batch, { ordered: false });
      totalInsertados   += res.upsertedCount;
      totalActualizados += res.modifiedCount;
    }

    console.log(`  Jugadores insertados: ${totalInsertados}`);
    console.log(`  Jugadores actualizados: ${totalActualizados}`);
    console.log(`  Total de operaciones: ${jugadoresOps.length}`);

    // ────────────────────────────────────────────────────────────────────────
    // PASO 3: Actualizar cantidadJugadores en cada equipo
    // ────────────────────────────────────────────────────────────────────────
    console.log("\n── Actualizando cantidadJugadores por equipo ──");

    const conteos = await colJugadores.aggregate([
      { $group: { _id: "$equipoId", total: { $sum: 1 } } }
    ]).toArray();

    const updateOps = conteos.map(({ _id: equipoId, total }) => ({
      updateOne: {
        filter: { _id: equipoId },
        update: { $set: { cantidadJugadores: new Int32(total) } }
      }
    }));

    if (updateOps.length > 0) {
      await colEquipos.bulkWrite(updateOps, { ordered: false });
    }

    console.log(`  Equipos actualizados con conteo de jugadores: ${updateOps.length}`);

    // ────────────────────────────────────────────────────────────────────────
    // PASO 4: Verificación final
    // ────────────────────────────────────────────────────────────────────────
    console.log("\n══════════════════════════════════════════════");
    console.log("  VERIFICACIÓN FINAL");
    console.log("══════════════════════════════════════════════");

    const cantEquipos   = await colEquipos.countDocuments();
    const cantJugadores = await colJugadores.countDocuments();

    console.log(`  Cantidad de equipos:   ${cantEquipos}   (esperado: 64)`);
    console.log(`  Cantidad de jugadores: ${cantJugadores} (esperado: >= 1000)`);

    // Verificar jugadores "huérfanos" (equipoId que no existe en equipos)
    // Usa $lookup + $match + $count
    const huerfanos = await colJugadores.aggregate([
      {
        $lookup: {
          from:         "equipos",
          localField:   "equipoId",
          foreignField: "_id",
          as:           "equipo"
        }
      },
      {
        $match: {
          equipo: { $size: 0 }   // Sin coincidencia → huérfano
        }
      },
      {
        $count: "huerfanos"
      }
    ]).toArray();

    const cantHuerfanos = huerfanos.length > 0 ? huerfanos[0].huerfanos : 0;
    console.log(`  Jugadores huérfanos:   ${cantHuerfanos}   (esperado: 0)`);
    console.log("══════════════════════════════════════════════\n");

    if (cantEquipos !== 64) {
      console.warn("⚠ ADVERTENCIA: La cantidad de equipos no es 64.");
    }
    if (cantJugadores < 1000) {
      console.warn("⚠ ADVERTENCIA: La cantidad de jugadores es menor a 1000.");
    }
    if (cantHuerfanos > 0) {
      console.warn("⚠ ADVERTENCIA: Existen jugadores huérfanos sin equipo válido.");
    }

    console.log("✔ Carga completada exitosamente.");

  } catch (err) {
    console.error("✖ Error durante la carga:", err);
    process.exit(1);
  } finally {
    await client.close();
    console.log("✔ Conexión cerrada.");
  }
}

main();
