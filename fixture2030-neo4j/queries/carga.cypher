// ============================================================================
//  Fixture 2030 — Hito 5 · Módulo de Grafos (Neo4j)
//  ARCHIVO: queries/carga.cypher
//  PROPÓSITO: carga reproducible e IDEMPOTENTE del subgrafo del torneo.
//  CUBRE: RF3, RF4, RF5, RF6, RNF3, RNF4, RNF6.
//
//  EJECUCIÓN (después de estructura.cypher):
//      docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 \
//          -f /queries/carga.cypher
//
//  IDEMPOTENCIA (RNF4)
//  -------------------
//  Todo nodo y toda relación se escriben con MERGE sobre su clave natural.
//  Ningún valor se genera con rand(), randomUUID(), timestamp() ni datetime()
//  "de ahora": todos los datos derivan de fórmulas deterministas sobre el
//  índice de la entidad. Consecuencia: correr este archivo 1 vez o 10 veces
//  deja EXACTAMENTE el mismo grafo, con los mismos conteos. Es la misma
//  estrategia que el Hito 4 resolvió con bulkWrite + upsert por clave natural.
//
//  VOLUMEN RESULTANTE
//  ------------------
//     64 Equipos       (código FIFA, = equipos._id del Hito 4)
//  1.282 Jugadores     (18 a 22 por equipo, dentro del rango 15-26 del Hito 4)
//     16 Grupos        (A..P, = equipos.grupo del Hito 4)
//     16 Sedes         (estadios reales de la candidatura 2030)
//    112 Partidos      (96 de grupos: 16 x 6 cruces + 16 dieciseisavos)
//  1.152 Eventos       (10 a 13 por partido de grupos, encadenados causalmente)
//     12 TipoEvento    (catálogo N8 del Hito 2/3)
// ============================================================================


// ============================================================================
//  PASO 1 — GRUPOS  (A..P)
//  El atributo escalar `grupo` de equipos en MongoDB se convierte acá en un
//  NODO propio: en el grafo, "estar en el mismo grupo" es una pregunta de
//  recorrido, no de igualdad de strings.
// ============================================================================
WITH ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P'] AS letras
UNWIND range(0, 15) AS i
MERGE (g:Grupo {grupoId: letras[i]})
  ON CREATE SET g.nombre = 'Grupo ' + letras[i], g.orden = i + 1, g.fase = 'GRUPOS'
  ON MATCH  SET g.nombre = 'Grupo ' + letras[i], g.orden = i + 1, g.fase = 'GRUPOS';


// ============================================================================
//  PASO 2 — SEDES  (16 estadios de la candidatura 2030)
//  `region` no es decorativo: es la región de réplica definida en el Hito 3
//  (réplica multi-región asíncrona) y se propaga a cada Evento del partido.
// ============================================================================
WITH [
  {id:'URU-CEN', nombre:'Estadio Centenario',        ciudad:'Montevideo',   pais:'Uruguay',   region:'AMERICAS', capacidad:60000},
  {id:'ARG-MON', nombre:'Estadio Monumental',        ciudad:'Buenos Aires', pais:'Argentina', region:'AMERICAS', capacidad:83000},
  {id:'PAR-DCH', nombre:'Defensores del Chaco',      ciudad:'Asunción',     pais:'Paraguay',  region:'AMERICAS', capacidad:42000},
  {id:'ESP-BER', nombre:'Santiago Bernabéu',         ciudad:'Madrid',       pais:'España',    region:'EUROPA',   capacidad:81000},
  {id:'ESP-CAM', nombre:'Camp Nou',                  ciudad:'Barcelona',    pais:'España',    region:'EUROPA',   capacidad:99000},
  {id:'ESP-MET', nombre:'Metropolitano',             ciudad:'Madrid',       pais:'España',    region:'EUROPA',   capacidad:68000},
  {id:'ESP-CAR', nombre:'La Cartuja',                ciudad:'Sevilla',      pais:'España',    region:'EUROPA',   capacidad:70000},
  {id:'ESP-SMA', nombre:'San Mamés',                 ciudad:'Bilbao',       pais:'España',    region:'EUROPA',   capacidad:53000},
  {id:'ESP-MES', nombre:'Mestalla',                  ciudad:'Valencia',     pais:'España',    region:'EUROPA',   capacidad:55000},
  {id:'ESP-RIA', nombre:'Riazor',                    ciudad:'A Coruña',     pais:'España',    region:'EUROPA',   capacidad:32000},
  {id:'POR-LUZ', nombre:'Estádio da Luz',            ciudad:'Lisboa',       pais:'Portugal',  region:'EUROPA',   capacidad:64000},
  {id:'POR-ALV', nombre:'Estádio José Alvalade',     ciudad:'Lisboa',       pais:'Portugal',  region:'EUROPA',   capacidad:50000},
  {id:'POR-DRA', nombre:'Estádio do Dragão',         ciudad:'Oporto',       pais:'Portugal',  region:'EUROPA',   capacidad:50000},
  {id:'MAR-HAS', nombre:'Grand Stade Hassan II',     ciudad:'Casablanca',   pais:'Marruecos', region:'AFRICA',   capacidad:115000},
  {id:'MAR-MOU', nombre:'Estadio Moulay Abdellah',   ciudad:'Rabat',        pais:'Marruecos', region:'AFRICA',   capacidad:69000},
  {id:'MAR-MAR', nombre:'Grand Stade de Marrakech',  ciudad:'Marrakech',    pais:'Marruecos', region:'AFRICA',   capacidad:45000}
] AS sedes
UNWIND sedes AS sd
MERGE (s:Sede {sedeId: sd.id})
  ON CREATE SET s.nombre = sd.nombre, s.ciudad = sd.ciudad, s.pais = sd.pais,
                s.region = sd.region, s.capacidad = sd.capacidad
  ON MATCH  SET s.nombre = sd.nombre, s.ciudad = sd.ciudad, s.pais = sd.pais,
                s.region = sd.region, s.capacidad = sd.capacidad;


// ============================================================================
//  PASO 3 — CATÁLOGO DE TIPOS DE EVENTO
//  Corresponde a la necesidad N8 del Hito 2/3 ("entidades complejas / tipos de
//  evento"), que allí se asignó a un motor de objetos con prioridad CP. Acá se
//  replica como catálogo de referencia LOCAL Y DE SOLO LECTURA, para que el
//  módulo de grafos pueda validar y agrupar eventos sin depender en tiempo de
//  consulta de otro subsistema. El nodo autoritativo del catálogo NO es este.
// ============================================================================
WITH [
  {id:'INICIO_PARTIDO',  nombre:'Inicio del partido',  categoria:'ADMINISTRATIVO', marcador:false},
  {id:'FIN_PARTIDO',     nombre:'Fin del partido',     categoria:'ADMINISTRATIVO', marcador:false},
  {id:'PASE',            nombre:'Pase',                categoria:'JUEGO',          marcador:false},
  {id:'CORNER',          nombre:'Tiro de esquina',     categoria:'JUEGO',          marcador:false},
  {id:'ATAJADA',         nombre:'Atajada',             categoria:'JUEGO',          marcador:false},
  {id:'ASISTENCIA',      nombre:'Asistencia',          categoria:'JUEGO',          marcador:false},
  {id:'GOL',             nombre:'Gol',                 categoria:'JUEGO',          marcador:true},
  {id:'PENAL',           nombre:'Penal',               categoria:'DISCIPLINA',     marcador:false},
  {id:'FALTA',           nombre:'Falta',               categoria:'DISCIPLINA',     marcador:false},
  {id:'TARJETA_AMARILLA',nombre:'Tarjeta amarilla',    categoria:'DISCIPLINA',     marcador:false},
  {id:'TARJETA_ROJA',    nombre:'Tarjeta roja',        categoria:'DISCIPLINA',     marcador:false},
  {id:'SUSTITUCION',     nombre:'Sustitución',         categoria:'ADMINISTRATIVO', marcador:false}
] AS tipos
UNWIND tipos AS t
MERGE (te:TipoEvento {tipoEventoId: t.id})
  ON CREATE SET te.nombre = t.nombre, te.categoria = t.categoria,
                te.afectaMarcador = t.marcador, te.origen = 'N8 · catálogo replicado'
  ON MATCH  SET te.nombre = t.nombre, te.categoria = t.categoria,
                te.afectaMarcador = t.marcador, te.origen = 'N8 · catálogo replicado';


// ============================================================================
//  PASO 4 — EQUIPOS (64) + pertenencia a grupo
//  equipoId = código FIFA = equipos._id del Hito 4 (RF5 / RNF6).
//  El reparto en grupos usa i % 16 sobre la lista ordenada por confederación:
//  es una distribución determinista y reproducible, no el sorteo real.
// ============================================================================
WITH [
  {id:'ARG', nombre:'Argentina',            conf:'CONMEBOL', dt:'L. Scaloni',   ciudad:'Buenos Aires', color:'Celeste y blanco'},
  {id:'URU', nombre:'Uruguay',              conf:'CONMEBOL', dt:'M. Bielsa',    ciudad:'Montevideo',   color:'Celeste'},
  {id:'BRA', nombre:'Brasil',               conf:'CONMEBOL', dt:'D. Ancelotti', ciudad:'Río de Janeiro', color:'Verde y amarillo'},
  {id:'COL', nombre:'Colombia',             conf:'CONMEBOL', dt:'N. Lorenzo',   ciudad:'Bogotá',       color:'Amarillo'},
  {id:'ECU', nombre:'Ecuador',              conf:'CONMEBOL', dt:'S. Beccacece', ciudad:'Quito',        color:'Amarillo'},
  {id:'PAR', nombre:'Paraguay',             conf:'CONMEBOL', dt:'G. Alfaro',    ciudad:'Asunción',     color:'Rojo y blanco'},
  {id:'CHI', nombre:'Chile',                conf:'CONMEBOL', dt:'R. Córdova',   ciudad:'Santiago',     color:'Rojo'},
  {id:'PER', nombre:'Perú',                 conf:'CONMEBOL', dt:'O. Ibáñez',    ciudad:'Lima',         color:'Blanco y rojo'},
  {id:'BOL', nombre:'Bolivia',              conf:'CONMEBOL', dt:'O. Villegas',  ciudad:'La Paz',       color:'Verde'},
  {id:'VEN', nombre:'Venezuela',            conf:'CONMEBOL', dt:'F. Batista',   ciudad:'Caracas',      color:'Vinotinto'},
  {id:'ESP', nombre:'España',               conf:'UEFA',     dt:'L. de la Fuente', ciudad:'Madrid',    color:'Rojo'},
  {id:'FRA', nombre:'Francia',              conf:'UEFA',     dt:'D. Deschamps', ciudad:'París',        color:'Azul'},
  {id:'ENG', nombre:'Inglaterra',           conf:'UEFA',     dt:'T. Tuchel',    ciudad:'Londres',      color:'Blanco'},
  {id:'GER', nombre:'Alemania',             conf:'UEFA',     dt:'J. Nagelsmann',ciudad:'Berlín',       color:'Blanco'},
  {id:'POR', nombre:'Portugal',             conf:'UEFA',     dt:'R. Martínez',  ciudad:'Lisboa',       color:'Rojo'},
  {id:'ITA', nombre:'Italia',               conf:'UEFA',     dt:'G. Gattuso',   ciudad:'Roma',         color:'Azul'},
  {id:'NED', nombre:'Países Bajos',         conf:'UEFA',     dt:'R. Koeman',    ciudad:'Ámsterdam',    color:'Naranja'},
  {id:'BEL', nombre:'Bélgica',              conf:'UEFA',     dt:'R. García',    ciudad:'Bruselas',     color:'Rojo'},
  {id:'CRO', nombre:'Croacia',              conf:'UEFA',     dt:'Z. Dalic',     ciudad:'Zagreb',       color:'Cuadros rojos'},
  {id:'DEN', nombre:'Dinamarca',            conf:'UEFA',     dt:'B. Riemer',    ciudad:'Copenhague',   color:'Rojo'},
  {id:'SUI', nombre:'Suiza',                conf:'UEFA',     dt:'M. Yakin',     ciudad:'Berna',        color:'Rojo'},
  {id:'POL', nombre:'Polonia',              conf:'UEFA',     dt:'J. Urban',     ciudad:'Varsovia',     color:'Blanco y rojo'},
  {id:'SRB', nombre:'Serbia',               conf:'UEFA',     dt:'V. Paunovic',  ciudad:'Belgrado',     color:'Rojo'},
  {id:'AUT', nombre:'Austria',              conf:'UEFA',     dt:'R. Rangnick',  ciudad:'Viena',        color:'Rojo'},
  {id:'UKR', nombre:'Ucrania',              conf:'UEFA',     dt:'S. Rebrov',    ciudad:'Kiev',         color:'Amarillo'},
  {id:'SCO', nombre:'Escocia',              conf:'UEFA',     dt:'S. Clarke',    ciudad:'Glasgow',      color:'Azul'},
  {id:'NOR', nombre:'Noruega',              conf:'UEFA',     dt:'S. Solbakken', ciudad:'Oslo',         color:'Rojo'},
  {id:'SWE', nombre:'Suecia',               conf:'UEFA',     dt:'G. Poyet',     ciudad:'Estocolmo',    color:'Amarillo'},
  {id:'TUR', nombre:'Turquía',              conf:'UEFA',     dt:'V. Montella',  ciudad:'Estambul',     color:'Rojo'},
  {id:'CZE', nombre:'Chequia',              conf:'UEFA',     dt:'I. Hasek',     ciudad:'Praga',        color:'Rojo'},
  {id:'HUN', nombre:'Hungría',              conf:'UEFA',     dt:'M. Rossi',     ciudad:'Budapest',     color:'Rojo'},
  {id:'GRE', nombre:'Grecia',               conf:'UEFA',     dt:'I. Jovanovic', ciudad:'Atenas',       color:'Azul y blanco'},
  {id:'ROU', nombre:'Rumania',              conf:'UEFA',     dt:'M. Lucescu',   ciudad:'Bucarest',     color:'Amarillo'},
  {id:'WAL', nombre:'Gales',                conf:'UEFA',     dt:'C. Bellamy',   ciudad:'Cardiff',      color:'Rojo'},
  {id:'MAR', nombre:'Marruecos',            conf:'CAF',      dt:'W. Regragui',  ciudad:'Rabat',        color:'Rojo'},
  {id:'SEN', nombre:'Senegal',              conf:'CAF',      dt:'P. Sarr',      ciudad:'Dakar',        color:'Verde'},
  {id:'EGY', nombre:'Egipto',               conf:'CAF',      dt:'H. Hassan',    ciudad:'El Cairo',     color:'Rojo'},
  {id:'NGA', nombre:'Nigeria',              conf:'CAF',      dt:'E. Chelle',    ciudad:'Abuya',        color:'Verde'},
  {id:'ALG', nombre:'Argelia',              conf:'CAF',      dt:'V. Petkovic',  ciudad:'Argel',        color:'Verde y blanco'},
  {id:'TUN', nombre:'Túnez',                conf:'CAF',      dt:'S. Trabelsi',  ciudad:'Túnez',        color:'Rojo'},
  {id:'CMR', nombre:'Camerún',              conf:'CAF',      dt:'M. Brys',      ciudad:'Yaundé',       color:'Verde'},
  {id:'GHA', nombre:'Ghana',                conf:'CAF',      dt:'O. Addo',      ciudad:'Acra',         color:'Blanco'},
  {id:'CIV', nombre:'Costa de Marfil',      conf:'CAF',      dt:'E. Fae',       ciudad:'Abiyán',       color:'Naranja'},
  {id:'MLI', nombre:'Malí',                 conf:'CAF',      dt:'T. Sissoko',   ciudad:'Bamako',       color:'Verde'},
  {id:'RSA', nombre:'Sudáfrica',            conf:'CAF',      dt:'H. Broos',     ciudad:'Pretoria',     color:'Amarillo'},
  {id:'COD', nombre:'RD Congo',             conf:'CAF',      dt:'S. Desabre',   ciudad:'Kinsasa',      color:'Azul'},
  {id:'JPN', nombre:'Japón',                conf:'AFC',      dt:'H. Moriyasu',  ciudad:'Tokio',        color:'Azul'},
  {id:'KOR', nombre:'Corea del Sur',        conf:'AFC',      dt:'H. Myung-bo',  ciudad:'Seúl',         color:'Rojo'},
  {id:'IRN', nombre:'Irán',                 conf:'AFC',      dt:'A. Ghalenoei', ciudad:'Teherán',      color:'Blanco'},
  {id:'AUS', nombre:'Australia',            conf:'AFC',      dt:'T. Popovic',   ciudad:'Canberra',     color:'Amarillo'},
  {id:'KSA', nombre:'Arabia Saudita',       conf:'AFC',      dt:'H. Renard',    ciudad:'Riad',         color:'Verde'},
  {id:'QAT', nombre:'Qatar',                conf:'AFC',      dt:'J. López',     ciudad:'Doha',         color:'Granate'},
  {id:'IRQ', nombre:'Irak',                 conf:'AFC',      dt:'G. Arnold',    ciudad:'Bagdad',       color:'Verde'},
  {id:'UZB', nombre:'Uzbekistán',           conf:'AFC',      dt:'T. Kapadze',   ciudad:'Taskent',      color:'Blanco'},
  {id:'UAE', nombre:'Emiratos Árabes Unidos',conf:'AFC',     dt:'C. Queiroz',   ciudad:'Abu Dabi',     color:'Blanco'},
  {id:'MEX', nombre:'México',               conf:'CONCACAF', dt:'J. Aguirre',   ciudad:'Ciudad de México', color:'Verde'},
  {id:'USA', nombre:'Estados Unidos',       conf:'CONCACAF', dt:'M. Pochettino',ciudad:'Washington',   color:'Blanco'},
  {id:'CAN', nombre:'Canadá',               conf:'CONCACAF', dt:'J. Marsch',    ciudad:'Ottawa',       color:'Rojo'},
  {id:'CRC', nombre:'Costa Rica',           conf:'CONCACAF', dt:'M. Herrera',   ciudad:'San José',     color:'Rojo'},
  {id:'JAM', nombre:'Jamaica',              conf:'CONCACAF', dt:'S. McClaren',  ciudad:'Kingston',     color:'Amarillo'},
  {id:'PAN', nombre:'Panamá',               conf:'CONCACAF', dt:'T. Christiansen', ciudad:'Panamá',    color:'Rojo'},
  {id:'HON', nombre:'Honduras',             conf:'CONCACAF', dt:'R. Rueda',     ciudad:'Tegucigalpa',  color:'Azul'},
  {id:'NZL', nombre:'Nueva Zelanda',        conf:'OFC',      dt:'D. Hay',       ciudad:'Wellington',   color:'Blanco'},
  {id:'FIJ', nombre:'Fiyi',                 conf:'OFC',      dt:'R. Krishna',   ciudad:'Suva',         color:'Blanco'}
] AS equipos
UNWIND range(0, size(equipos) - 1) AS i
WITH equipos[i] AS eq,
     ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P'][i % 16] AS letra,
     i
MATCH (g:Grupo {grupoId: letra})
MERGE (e:Equipo {equipoId: eq.id})
  ON CREATE SET e.nombre = eq.nombre, e.confederacion = eq.conf, e.rankingFifa = i + 1,
                e.entrenador = eq.dt, e.ciudadBase = eq.ciudad, e.colorPrincipal = eq.color,
                e.fechaAlta = datetime('2026-01-01T00:00:00Z')
  ON MATCH  SET e.nombre = eq.nombre, e.confederacion = eq.conf, e.rankingFifa = i + 1,
                e.entrenador = eq.dt, e.ciudadBase = eq.ciudad, e.colorPrincipal = eq.color
MERGE (e)-[:PERTENECE_A]->(g);


// ============================================================================
//  PASO 5 — JUGADORES (1.282) + relación JUEGA_EN
//  Clave natural = dni (mismo criterio e igual patrón ^[0-9]{7,8}$ del Hito 4).
//  El tamaño del plantel varía entre 18 y 22 según el ranking del equipo, para
//  respetar el rango 15-26 declarado en el Hito 4 sin usar aleatoriedad.
//  El campo `jugadores.equipoId` de MongoDB NO se replica como propiedad: su
//  equivalente en el grafo es la relación (:Jugador)-[:JUEGA_EN]->(:Equipo).
// ============================================================================
MATCH (e:Equipo)
WITH e, e.rankingFifa AS ie, 18 + (e.rankingFifa % 5) AS plantel
UNWIND range(1, plantel) AS d
WITH e, ie, d,
     ['Mateo','Lucas','Thiago','Benjamín','Santiago','Joaquín','Valentino','Emiliano',
      'Bautista','Nicolás','Facundo','Julián','Franco','Tomás','Agustín','Ignacio',
      'Rodrigo','Alejandro','Marcos','Diego'] AS nombres,
     ['Álvarez','Gómez','Silva','Rossi','Müller','Okafor','Tanaka','Novak','Kovac',
      'Andersen','Fernández','Haddad','Mensah','Petrov','Van Dijk','Costa','Dubois',
      'Bianchi','Nakamura','Bekele','Sorensen','Moreno','Vargas'] AS apellidos
WITH e, ie, d,
     nombres[(ie * 7 + d * 3) % size(nombres)]     AS nom,
     apellidos[(ie * 11 + d * 5) % size(apellidos)] AS ape,
     toString(30000000 + (ie - 1) * 23000 + d * 137) AS dniGenerado,
     CASE
       WHEN d = 1 OR d = 12 THEN 'Arquero'
       WHEN d <= 6          THEN 'Defensor'
       WHEN d <= 14         THEN 'Mediocampista'
       ELSE                      'Delantero'
     END AS pos
MERGE (j:Jugador {dni: dniGenerado})
  ON CREATE SET j.nombre = nom, j.apellido = ape, j.posicion = pos, j.dorsal = d,
                j.nacionalidad = e.nombre,
                j.fechaNacimiento = date('2010-06-01') - duration({days: (ie * 29 + d * 61) % 4380}),
                j.fechaAlta = datetime('2026-01-01T00:00:00Z')
  ON MATCH  SET j.nombre = nom, j.apellido = ape, j.posicion = pos, j.dorsal = d,
                j.nacionalidad = e.nombre
MERGE (j)-[r:JUEGA_EN]->(e)
  ON CREATE SET r.dorsal = d, r.desde = date('2026-01-01'),
                r.rol = CASE WHEN d = 10 THEN 'CAPITAN' ELSE 'PLANTEL' END
  ON MATCH  SET r.dorsal = d,
                r.rol = CASE WHEN d = 10 THEN 'CAPITAN' ELSE 'PLANTEL' END;


// ============================================================================
//  PASO 6 — PARTIDOS (96) + participación, sede y grupo
//  Cada grupo de 4 juega los 6 cruces de todos contra todos, repartidos en 3
//  jornadas. `ordenGlobal` numera el partido dentro del torneo y es el valor
//  determinista del que se derivan fecha, sede y guion de eventos.
// ============================================================================
MATCH (g:Grupo)<-[:PERTENECE_A]-(e:Equipo)
WITH g, e ORDER BY e.rankingFifa
WITH g, collect(e) AS eqs
WITH g, eqs, [[0,1],[2,3],[0,2],[1,3],[0,3],[1,2]] AS cruces
UNWIND range(0, 5) AS k
WITH g, eqs[cruces[k][0]] AS loc, eqs[cruces[k][1]] AS vis, k
WITH g, loc, vis, k,
     ['URU-CEN','ARG-MON','PAR-DCH','ESP-BER','ESP-CAM','ESP-MET','ESP-CAR','ESP-SMA',
      'ESP-MES','ESP-RIA','POR-LUZ','POR-ALV','POR-DRA','MAR-HAS','MAR-MOU','MAR-MAR'] AS sedeIds
WITH g, loc, vis, k,
     'PAR-' + g.grupoId + '-' + toString(k + 1)        AS pid,
     (k / 2) + 1                                       AS jornada,
     (g.orden - 1) * 6 + k                             AS ordenGlobal,
     sedeIds[(((g.orden - 1) * 6 + k)) % 16]           AS sid
MATCH (s:Sede {sedeId: sid})
MERGE (p:Partido {partidoId: pid})
  ON CREATE SET p.fase = 'GRUPOS', p.grupo = g.grupoId, p.jornada = jornada,
                p.ordenGlobal = ordenGlobal, p.estado = 'PROGRAMADO',
                p.fechaHora = datetime('2030-06-09T13:00:00Z')
                             + duration({days:  (jornada - 1) * 5 + ((g.orden - 1) % 4),
                                         hours: ((g.orden - 1) / 4) * 3})
  ON MATCH  SET p.fase = 'GRUPOS', p.grupo = g.grupoId, p.jornada = jornada,
                p.ordenGlobal = ordenGlobal,
                p.fechaHora = datetime('2030-06-09T13:00:00Z')
                             + duration({days:  (jornada - 1) * 5 + ((g.orden - 1) % 4),
                                         hours: ((g.orden - 1) / 4) * 3})
MERGE (loc)-[:PARTICIPA_EN {condicion: 'LOCAL'}]->(p)
MERGE (vis)-[:PARTICIPA_EN {condicion: 'VISITANTE'}]->(p)
MERGE (p)-[:SE_JUEGA_EN]->(s)
MERGE (p)-[:CORRESPONDE_A]->(g);


// ============================================================================
//  PASO 7 — EVENTOS DEPORTIVOS (1.152)
//  --------------------------------------------------------------------------
//  ACÁ SE MATERIALIZA LA CONSISTENCIA CAUSAL DEL HITO 3.
//  Cada evento lleva:
//    · partidoId          -> CLAVE DE PARTICIÓN (los eventos de un partido
//                            conviven; ningún recorrido causal cruza partidos)
//    · secuencia          -> RELOJ LÓGICO monótono DENTRO de la partición.
//                            No es un timestamp de reloj de pared: es lo que
//                            permite ordenar sin sincronización global, que es
//                            exactamente lo que un sistema AP no puede asumir.
//    · regionOrigen       -> región de ingesta (réplica multi-región asíncrona)
//  El guion tiene 3 variantes deterministas según `ordenGlobal % 3`, para que
//  los marcadores no sean todos iguales sin recurrir a rand().
// ============================================================================
MATCH (p:Partido)-[:SE_JUEGA_EN]->(s:Sede)
WITH p, s,
  [ {sec:1, tipo:'INICIO_PARTIDO',   min:0,  cond:'LOCAL',     dorsal:1},
    {sec:2, tipo:'PASE',             min:12, cond:'LOCAL',     dorsal:5},
    {sec:3, tipo:'PASE',             min:12, cond:'LOCAL',     dorsal:8},
    {sec:4, tipo:'ASISTENCIA',       min:13, cond:'LOCAL',     dorsal:10},
    {sec:5, tipo:'GOL',              min:13, cond:'LOCAL',     dorsal:9},
    {sec:6, tipo:'FALTA',            min:31, cond:'VISITANTE', dorsal:4},
    {sec:7, tipo:'TARJETA_AMARILLA', min:31, cond:'VISITANTE', dorsal:4},
    {sec:8, tipo:'ATAJADA',          min:58, cond:'VISITANTE', dorsal:1},
    {sec:9, tipo:'SUSTITUCION',      min:62, cond:'LOCAL',     dorsal:16}
  ] AS base,
  CASE
    WHEN p.ordenGlobal % 3 = 0 THEN []
    WHEN p.ordenGlobal % 3 = 1 THEN
      [ {sec:10, tipo:'PASE',       min:74, cond:'VISITANTE', dorsal:6},
        {sec:11, tipo:'ASISTENCIA', min:75, cond:'VISITANTE', dorsal:7},
        {sec:12, tipo:'GOL',        min:75, cond:'VISITANTE', dorsal:11} ]
    ELSE
      [ {sec:10, tipo:'CORNER',     min:81, cond:'LOCAL',     dorsal:7},
        {sec:11, tipo:'ASISTENCIA', min:82, cond:'LOCAL',     dorsal:7},
        {sec:12, tipo:'GOL',        min:82, cond:'LOCAL',     dorsal:15} ]
  END AS extra
WITH p, s, base + extra AS parcial
WITH p, s, parcial + [{sec: size(parcial) + 1, tipo:'FIN_PARTIDO', min:90, cond:'LOCAL', dorsal:1}] AS plantilla
UNWIND plantilla AS ev
MERGE (n:Evento {eventoId: p.partidoId + '-EV-' + right('0' + toString(ev.sec), 2)})
  ON CREATE SET n.partidoId = p.partidoId, n.secuencia = ev.sec, n.tipo = ev.tipo,
                n.minuto = ev.min, n.condicionEquipo = ev.cond,
                n.dorsalProtagonista = ev.dorsal,
                n.timestamp = p.fechaHora + duration({minutes: ev.min}),
                n.regionOrigen = s.region
  ON MATCH  SET n.partidoId = p.partidoId, n.secuencia = ev.sec, n.tipo = ev.tipo,
                n.minuto = ev.min, n.condicionEquipo = ev.cond,
                n.dorsalProtagonista = ev.dorsal,
                n.timestamp = p.fechaHora + duration({minutes: ev.min}),
                n.regionOrigen = s.region
MERGE (n)-[:OCURRE_EN]->(p);


// ============================================================================
//  PASO 8 — Evento -> TipoEvento  (validación contra el catálogo N8)
// ============================================================================
MATCH (n:Evento)
MATCH (t:TipoEvento {tipoEventoId: n.tipo})
MERGE (n)-[:ES_DE_TIPO]->(t);


// ============================================================================
//  PASO 9 — Evento -> Jugador protagonista
//  Recorrido de resolución: el evento sabe su condición (LOCAL/VISITANTE) y el
//  dorsal; el equipo se obtiene navegando el partido, y el jugador navegando
//  el plantel. Es un ejemplo de por qué el dato se beneficia de ser un grafo:
//  el vínculo se RESUELVE por recorrido, no por un join declarado a mano.
// ============================================================================
MATCH (n:Evento)-[:OCURRE_EN]->(p:Partido)<-[part:PARTICIPA_EN]-(eq:Equipo)
WHERE part.condicion = n.condicionEquipo
MATCH (j:Jugador)-[jn:JUEGA_EN]->(eq)
WHERE jn.dorsal = n.dorsalProtagonista
MERGE (n)-[:PROTAGONIZADO_POR]->(j);


// ============================================================================
//  PASO 10 — ORDEN TOTAL DENTRO DE LA PARTICIÓN: [:SIGUIENTE_EVENTO]
//  Enlaza cada evento con el inmediato siguiente DEL MISMO PARTIDO. Nunca
//  cruza particiones: es el orden que la región de ingesta puede garantizar
//  localmente sin coordinación global.
// ============================================================================
MATCH (a:Evento)-[:OCURRE_EN]->(p:Partido)<-[:OCURRE_EN]-(b:Evento)
WHERE b.secuencia = a.secuencia + 1
MERGE (a)-[:SIGUIENTE_EVENTO]->(b);


// ============================================================================
//  PASO 11 — DEPENDENCIA CAUSAL EXPLÍCITA: [:CAUSA_DE]
//  Subconjunto del orden total: solo los pares donde un evento es CAUSA del
//  siguiente. Dirección: (causa)-[:CAUSA_DE]->(efecto).
//     pase -> pase -> asistencia -> GOL       (jugada del gol)
//     falta -> tarjeta amarilla               (sanción)
//  Esta relación es la que hace verificable el invariante del Hito 3:
//  "un evento no puede preceder a su causa".
// ============================================================================
MATCH (p:Partido)
WITH p,
     CASE WHEN p.ordenGlobal % 3 = 0
          THEN [[2,3],[3,4],[4,5],[6,7]]
          ELSE [[2,3],[3,4],[4,5],[6,7],[10,11],[11,12]]
     END AS pares
UNWIND pares AS c
MATCH (a:Evento {partidoId: p.partidoId, secuencia: c[0]})
MATCH (b:Evento {partidoId: p.partidoId, secuencia: c[1]})
MERGE (a)-[:CAUSA_DE]->(b);


// ============================================================================
//  PASO 12 — MARCADOR DERIVADO DEL GRAFO
//  El marcador NO se carga como dato suelto: se DERIVA contando los eventos de
//  tipo GOL de cada lado. Así el marcador nunca puede contradecir al timeline.
//  (En el Hito 4, el equivalente `estadisticas` está denormalizado en el
//  documento; acá es una propiedad calculada y recalculable.)
//  Es idempotente: SET a un valor calculado, no un incremento.
// ============================================================================
MATCH (p:Partido {fase: 'GRUPOS'})
OPTIONAL MATCH (gl:Evento)-[:OCURRE_EN]->(p)
  WHERE gl.tipo = 'GOL' AND gl.condicionEquipo = 'LOCAL'
WITH p, count(gl) AS golesL
OPTIONAL MATCH (gv:Evento)-[:OCURRE_EN]->(p)
  WHERE gv.tipo = 'GOL' AND gv.condicionEquipo = 'VISITANTE'
WITH p, golesL, count(gv) AS golesV
SET p.golesLocal = golesL,
    p.golesVisitante = golesV,
    p.estado = 'FINALIZADO';


// ============================================================================
//  PASO 13 — DIECISEISAVOS DE FINAL (16 partidos, aún sin jugar)
//  --------------------------------------------------------------------------
//  POR QUÉ SE CARGAN, si el hito no los exige:
//  sin fase eliminatoria, el grafo del torneo son 16 COMPONENTES CONEXAS
//  AISLADAS (un grupo cada una) y toda consulta de camino entre equipos de
//  distinto grupo devuelve vacío. Los dieciseisavos son las aristas que unen
//  esas componentes, y sin ellas las consultas de camino y conectividad del
//  bloque 3 de consultas_grafo.cypher no tendrían nada que mostrar.
//
//  Clasificados: 1° y 2° de cada grupo, calculados RECORRIENDO EL GRAFO
//  (puntos, diferencia de gol, goles a favor y equipoId como desempate final,
//  para que el resultado sea totalmente determinista y la carga siga siendo
//  idempotente). Cruce: 1° del grupo N contra 2° del grupo N+1, en anillo.
//  Quedan en estado PROGRAMADO y sin eventos: todavía no se jugaron.
// ============================================================================
MATCH (e:Equipo)-[part:PARTICIPA_EN]->(p:Partido {fase: 'GRUPOS'})
MATCH (e)-[:PERTENECE_A]->(g:Grupo)
WITH g, e,
     CASE part.condicion WHEN 'LOCAL' THEN p.golesLocal     ELSE p.golesVisitante END AS gf,
     CASE part.condicion WHEN 'LOCAL' THEN p.golesVisitante ELSE p.golesLocal     END AS gc
WITH g, e,
     sum(CASE WHEN gf > gc THEN 3 WHEN gf = gc THEN 1 ELSE 0 END) AS pts,
     sum(gf) - sum(gc) AS dif,
     sum(gf) AS gfav
ORDER BY g.orden, pts DESC, dif DESC, gfav DESC, e.equipoId
WITH g, collect(e) AS tabla
WITH collect({orden: g.orden, primero: tabla[0], segundo: tabla[1]}) AS clasif
UNWIND range(0, 15) AS i
WITH clasif, i,
     [c IN clasif WHERE c.orden = i + 1][0]              AS grupoLocal,
     [c IN clasif WHERE c.orden = ((i + 1) % 16) + 1][0] AS grupoVisita
WITH i, grupoLocal.primero AS loc, grupoVisita.segundo AS vis,
     ['URU-CEN','ARG-MON','PAR-DCH','ESP-BER','ESP-CAM','ESP-MET','ESP-CAR','ESP-SMA',
      'ESP-MES','ESP-RIA','POR-LUZ','POR-ALV','POR-DRA','MAR-HAS','MAR-MOU','MAR-MAR'][i] AS sid
MATCH (s:Sede {sedeId: sid})
MERGE (p:Partido {partidoId: 'PAR-D16-' + right('0' + toString(i + 1), 2)})
  ON CREATE SET p.fase = 'DIECISEISAVOS', p.jornada = 4, p.ordenGlobal = 96 + i,
                p.estado = 'PROGRAMADO',
                p.fechaHora = datetime('2030-06-29T16:00:00Z')
                             + duration({days: i / 4, hours: (i % 4) * 3})
  ON MATCH  SET p.fase = 'DIECISEISAVOS', p.jornada = 4, p.ordenGlobal = 96 + i,
                p.fechaHora = datetime('2030-06-29T16:00:00Z')
                             + duration({days: i / 4, hours: (i % 4) * 3})
MERGE (loc)-[:PARTICIPA_EN {condicion: 'LOCAL'}]->(p)
MERGE (vis)-[:PARTICIPA_EN {condicion: 'VISITANTE'}]->(p)
MERGE (p)-[:SE_JUEGA_EN]->(s);


// ============================================================================
//  PASO 14 — VERIFICACIÓN DE LA CARGA (RF11 / RNF4 / RNF7)
//  Correr este bloque DOS VECES seguidas debe devolver los mismos números.
//  Esa es la evidencia de idempotencia que pide el enunciado.
// ============================================================================
MATCH (n)
RETURN labels(n)[0] AS etiqueta, count(*) AS cantidad
ORDER BY etiqueta;

MATCH ()-[r]->()
RETURN type(r) AS relacion, count(*) AS cantidad
ORDER BY relacion;
