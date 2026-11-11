# Evidencia · 127 partidos y relaciones del enunciado (Neo4j)

- **Fecha:** 2026-11-11 18:09 UTC
- **Commit:** `2bbe340` (rama `claude/neo4j-127-partidos-0bafaa`)
- **Motor:**  · imagen `neo4j@sha256:91fb0bf237c41b7b3dcbe84703aa0b82e0d7d067b16e1c8ab21f03fc679edf4e`
- **Ambiente:** contenedor de prueba propio (`docker compose -p neo127`, Bolt en `127.0.0.1:27688`, sin plugins APOC/GDS porque ninguna consulta los usa), con `queries/` montado en `/queries` igual que el `docker-compose.yml` del módulo. Para reproducirlo con el compose del módulo, reemplazar `docker exec neo127-neo4j` por `docker compose exec neo4j`.
- **Generado por:** un script de la sesión que ejecuta, en orden, los comandos de cada sección. Toda la salida es la real, sin editar.

## 1. Base vacía, estructura y primera carga

```bash
docker compose -p neo127 down -v && docker compose -p neo127 up -d   # volumen nuevo
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 "MATCH (n) RETURN count(n) AS nodosAntes"
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/estructura.cypher
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/carga.cypher
```

```text
nodosAntes
0
```

Restricciones e índices creados por `estructura.cypher` (resumen):

```text
restricciones de unicidad: 7
índices RANGE: 16  (7 de respaldo de las restricciones + 9 propios)
exit=0
```

Salida de la primera corrida de `carga.cypher` (paso 19):

```text
etiqueta, cantidad
"Equipo", 64
"Evento", 1572
"Grupo", 16
"Jugador", 1282
"Partido", 127
"Sede", 16
"TipoEvento", 12
relacion, cantidad
"ANOTA", 220
"ASISTE", 220
"CAUSA_DE", 702
"CORRESPONDE_A", 96
"ES_DE_TIPO", 1572
"JUEGA_EN", 1282
"OCURRE_EN", 1572
"PARTICIPA", 1248
"PARTICIPA_EN", 254
"PERTENECE_A", 64
"PROTAGONIZADO_POR", 1572
"RECIBE_TARJETA", 136
"REEMPLAZA", 136
"SE_JUEGA_EN", 127
"SIGUIENTE_EVENTO", 1446
fase, estado, partidos, eventos
"GRUPOS", "FINALIZADO", 96, 1152
"DIECISEISAVOS", "FINALIZADO", 16, 220
"OCTAVOS", "FINALIZADO", 8, 116
"CUARTOS", "FINALIZADO", 4, 52
"SEMIFINAL", "FINALIZADO", 2, 32
"FINAL", "PROGRAMADO", 1, 0
exit=0 · 12 s
```

## 2. Segunda corrida (idempotencia, RNF4)

```bash
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/carga.cypher
diff carga1.out carga2.out
```

```text
exit=0
diff: sin diferencias (conteos idénticos en las dos corridas)
```

## 3. Todas las consultas (`consultas_grafo.cypher`)

Incluye las 19 consultas numeradas, la auditoría 6.1–6.9 (todo lo que espera 0 da 0) y el análisis de relaciones 8.1–8.3. Cada tabla empieza con su línea de encabezados; el orden es el del archivo.

```bash
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/consultas_grafo.cypher
```

```text
jugador, equipo, partido, jornada, condicion, sede, regionSede, fecha
"Dubois, Facundo", "Argentina", "PAR-A-1", 1, "LOCAL", "Estadio Centenario (Montevideo)", "AMERICAS", 2030-06-09T13:00Z
"Dubois, Facundo", "Argentina", "PAR-A-3", 2, "LOCAL", "Defensores del Chaco (Asunción)", "AMERICAS", 2030-06-14T13:00Z
"Dubois, Facundo", "Argentina", "PAR-A-5", 3, "LOCAL", "Camp Nou (Barcelona)", "EUROPA", 2030-06-19T13:00Z
"Dubois, Facundo", "Argentina", "PAR-D16-01", 4, "LOCAL", "Estadio Centenario (Montevideo)", "AMERICAS", 2030-06-29T16:00Z
"Dubois, Facundo", "Argentina", "PAR-OCT-01", 5, "LOCAL", "Santiago Bernabéu (Madrid)", "EUROPA", 2030-07-04T16:00Z
equipoSegundoGrado, confederacion, rivalesEnComun, partidosDeContacto
"Brasil", "CONMEBOL", ["Croacia"], 2
"Uruguay", "CONMEBOL", ["Croacia", "Bélgica"], 2
"Arabia Saudita", "AFC", ["Croacia"], 1
"Australia", "AFC", ["Bélgica"], 1
"Gales", "UEFA", ["Bélgica"], 1
"Italia", "UEFA", ["Países Bajos"], 1
"Marruecos", "CAF", ["Croacia"], 1
"Ucrania", "UEFA", ["Croacia"], 1
confederacion, regionDeReplica, partidos, sedesDistintas
"AFC", "EUROPA", 19, 10
"AFC", "AMERICAS", 4, 3
"AFC", "AFRICA", 4, 2
"CAF", "EUROPA", 21, 10
"CAF", "AFRICA", 9, 3
"CAF", "AMERICAS", 6, 3
"CONCACAF", "EUROPA", 12, 9
"CONCACAF", "AFRICA", 5, 3
"CONCACAF", "AMERICAS", 4, 3
"CONMEBOL", "EUROPA", 31, 9
"CONMEBOL", "AMERICAS", 11, 3
"CONMEBOL", "AFRICA", 7, 2
"OFC", "EUROPA", 4, 4
"OFC", "AFRICA", 2, 2
"UEFA", "EUROPA", 57, 10
"UEFA", "AFRICA", 20, 3
"UEFA", "AMERICAS", 16, 3
gol, minutoDelGol, eslabonesDeLaCadena, secuenciaCausal
"PAR-A-2-EV-05", 13, 3, ["PASE (min 12 · #5 Sorensen)", "PASE (min 12 · #8 Mensah)", "ASISTENCIA (min 13 · #10 Vargas)", "GOL (min 13 · #9 Bianchi)"]
"PAR-A-2-EV-12", 75, 2, ["PASE (min 74 · #6 Bianchi)", "ASISTENCIA (min 75 · #7 Vargas)", "GOL (min 75 · #11 Bekele)"]
violacionesDeOrdenCausal, cadenasQueCruzanParticion
0, 0
jugador, equipo, posicion, goles, asistencias
"Tanaka, Facundo", "Bolivia", "Mediocampista", 7, 0
"Andersen, Bautista", "Brasil", "Mediocampista", 5, 0
"Fernández, Agustín", "Argentina", "Mediocampista", 5, 0
"Müller, Marcos", "Inglaterra", "Mediocampista", 5, 0
"Novak, Rodrigo", "Chile", "Mediocampista", 5, 0
"Petrov, Bautista", "Bolivia", "Delantero", 5, 0
"Rossi, Franco", "Portugal", "Mediocampista", 5, 0
"Bekele, Nicolás", "Paraguay", "Mediocampista", 4, 0
"Bianchi, Alejandro", "Venezuela", "Mediocampista", 4, 0
"Costa, Joaquín", "Alemania", "Mediocampista", 4, 0
"Costa, Valentino", "Ucrania", "Delantero", 4, 0
"Dubois, Julián", "Francia", "Mediocampista", 4, 0
"Gómez, Mateo", "Croacia", "Mediocampista", 4, 0
"Haddad, Lucas", "Polonia", "Mediocampista", 4, 0
"Kovac, Bautista", "Ucrania", "Mediocampista", 4, 0
desde, hasta, gradosDeSeparacion, camino
"Argentina", "Uruguay", 2, ["Argentina", "PAR-OCT-01", "Croacia", "PAR-D16-02", "Uruguay"]
escenario, equiposAlcanzables, alcanzados
"Solo fase de grupos", 3, ["Rumania", "Países Bajos", "Irán"]
escenario, equiposAlcanzables
"Grupos + eliminatorias", 44
grupo, equipos, partidos
"A", 4, 6
"B", 4, 6
"C", 4, 6
"D", 4, 6
"E", 4, 6
"F", 4, 6
"G", 4, 6
"H", 4, 6
"I", 4, 6
"J", 4, 6
"K", 4, 6
"L", 4, 6
"M", 4, 6
"N", 4, 6
"O", 4, 6
"P", 4, 6
jugador, equipo, posicion, golesEnLosQueIntervino, eventosCausalesPropios, impactoPorIntervencion
"Haddad, Rodrigo", "Ucrania", "Mediocampista", 9, 14, 0.6428571428571429
"Andersen, Marcos", "Bolivia", "Defensor", 7, 7, 1.0
"Gómez, Emiliano", "Bolivia", "Mediocampista", 7, 7, 1.0
"Haddad, Tomás", "Bolivia", "Mediocampista", 7, 7, 1.0
"Andersen, Lucas", "Inglaterra", "Mediocampista", 5, 5, 1.0
"Bekele, Santiago", "Bolivia", "Mediocampista", 5, 10, 0.5
"Costa, Alejandro", "Argentina", "Mediocampista", 5, 5, 1.0
"Fernández, Santiago", "Chile", "Defensor", 5, 5, 1.0
"Kovac, Ignacio", "Portugal", "Mediocampista", 5, 5, 1.0
"Kovac, Marcos", "Hungría", "Mediocampista", 5, 8, 0.625
"Mensah, Diego", "Chile", "Mediocampista", 5, 5, 1.0
"Mensah, Rodrigo", "Brasil", "Defensor", 5, 5, 1.0
"Moreno, Nicolás", "Portugal", "Mediocampista", 5, 5, 1.0
"Müller, Joaquín", "Brasil", "Mediocampista", 5, 5, 1.0
"Novak, Valentino", "Inglaterra", "Defensor", 5, 5, 1.0
"Okafor, Julián", "Argentina", "Mediocampista", 5, 5, 1.0
"Petrov, Thiago", "Argentina", "Defensor", 5, 5, 1.0
"Silva, Tomás", "Chile", "Mediocampista", 5, 5, 1.0
"Tanaka, Mateo", "Portugal", "Defensor", 5, 5, 1.0
"Van Dijk, Agustín", "Croacia", "Mediocampista", 5, 8, 0.625
sede, ciudad, regionDeReplica, partidos, equiposDistintos, confederacionesDistintas
"Grand Stade Hassan II", "Casablanca", "AFRICA", 11, 19, 6
"Santiago Bernabéu", "Madrid", "EUROPA", 10, 18, 5
"Estádio da Luz", "Lisboa", "EUROPA", 9, 18, 5
"Camp Nou", "Barcelona", "EUROPA", 9, 17, 5
"Metropolitano", "Madrid", "EUROPA", 8, 16, 6
"Estadio Moulay Abdellah", "Rabat", "AFRICA", 8, 16, 5
"Estádio do Dragão", "Oporto", "EUROPA", 8, 15, 5
"La Cartuja", "Sevilla", "EUROPA", 8, 14, 5
"San Mamés", "Bilbao", "EUROPA", 7, 14, 6
"Mestalla", "Valencia", "EUROPA", 7, 14, 5
"Riazor", "A Coruña", "EUROPA", 7, 14, 5
"Grand Stade de Marrakech", "Marrakech", "AFRICA", 7, 14, 4
"Estadio Centenario", "Montevideo", "AMERICAS", 7, 13, 5
"Estadio Monumental", "Buenos Aires", "AMERICAS", 7, 13, 5
"Defensores del Chaco", "Asunción", "AMERICAS", 7, 13, 5
"Estádio José Alvalade", "Lisboa", "EUROPA", 7, 13, 5
grupo, resultado, sede, region, fecha
"A", "Argentina 1 - 0 Países Bajos", "Estadio Centenario", "AMERICAS", 2030-06-09T13:00Z
"A", "Rumania 1 - 1 Irán", "Estadio Monumental", "AMERICAS", 2030-06-09T13:00Z
"E", "Ecuador 1 - 0 Suiza", "Mestalla", "EUROPA", 2030-06-09T16:00Z
"E", "Egipto 1 - 1 Irak", "Riazor", "EUROPA", 2030-06-09T16:00Z
"I", "Bolivia 1 - 0 Ucrania", "Estadio Centenario", "AMERICAS", 2030-06-09T19:00Z
"I", "Camerún 1 - 1 Estados Unidos", "Estadio Monumental", "AMERICAS", 2030-06-09T19:00Z
"M", "Inglaterra 1 - 0 Turquía", "Mestalla", "EUROPA", 2030-06-09T22:00Z
"M", "Sudáfrica 1 - 1 Panamá", "Riazor", "EUROPA", 2030-06-09T22:00Z
"B", "Uruguay 1 - 0 Bélgica", "La Cartuja", "EUROPA", 2030-06-10T13:00Z
"B", "Gales 1 - 1 Australia", "San Mamés", "EUROPA", 2030-06-10T13:00Z
"F", "Paraguay 1 - 0 Polonia", "Estadio Moulay Abdellah", "AFRICA", 2030-06-10T16:00Z
"F", "Nigeria 1 - 1 Uzbekistán", "Grand Stade de Marrakech", "AFRICA", 2030-06-10T16:00Z
"J", "Venezuela 1 - 0 Escocia", "La Cartuja", "EUROPA", 2030-06-10T19:00Z
"J", "Ghana 1 - 1 Canadá", "San Mamés", "EUROPA", 2030-06-10T19:00Z
"N", "Alemania 1 - 0 Chequia", "Estadio Moulay Abdellah", "AFRICA", 2030-06-10T22:00Z
"N", "RD Congo 1 - 1 Honduras", "Grand Stade de Marrakech", "AFRICA", 2030-06-10T22:00Z
"C", "Brasil 1 - 0 Croacia", "Estádio do Dragão", "EUROPA", 2030-06-11T13:00Z
"C", "Marruecos 1 - 1 Arabia Saudita", "Grand Stade Hassan II", "AFRICA", 2030-06-11T13:00Z
"G", "Chile 1 - 0 Serbia", "Camp Nou", "EUROPA", 2030-06-11T16:00Z
"G", "Argelia 1 - 1 Emiratos Árabes Unidos", "Metropolitano", "EUROPA", 2030-06-11T16:00Z
"K", "España 1 - 0 Noruega", "Estádio do Dragão", "EUROPA", 2030-06-11T19:00Z
"K", "Costa de Marfil 1 - 1 Costa Rica", "Grand Stade Hassan II", "AFRICA", 2030-06-11T19:00Z
"O", "Portugal 1 - 0 Hungría", "Camp Nou", "EUROPA", 2030-06-11T22:00Z
"O", "Japón 1 - 1 Nueva Zelanda", "Metropolitano", "EUROPA", 2030-06-11T22:00Z
"D", "Colombia 1 - 0 Dinamarca", "Defensores del Chaco", "AMERICAS", 2030-06-12T13:00Z
"D", "Senegal 1 - 1 Qatar", "Santiago Bernabéu", "EUROPA", 2030-06-12T13:00Z
"H", "Perú 1 - 0 Austria", "Estádio da Luz", "EUROPA", 2030-06-12T16:00Z
"H", "Túnez 1 - 1 México", "Estádio José Alvalade", "EUROPA", 2030-06-12T16:00Z
"L", "Francia 1 - 0 Suecia", "Defensores del Chaco", "AMERICAS", 2030-06-12T19:00Z
"L", "Malí 1 - 1 Jamaica", "Santiago Bernabéu", "EUROPA", 2030-06-12T19:00Z
"P", "Italia 1 - 0 Grecia", "Estádio da Luz", "EUROPA", 2030-06-12T22:00Z
"P", "Corea del Sur 1 - 1 Fiyi", "Estádio José Alvalade", "EUROPA", 2030-06-12T22:00Z
sede, partidoA, fechaA, partidoB, fechaB
"Camp Nou", "PAR-G-1", 2030-06-11T16:00Z, "PAR-O-1", 2030-06-11T22:00Z
"Camp Nou", "PAR-D-3", 2030-06-17T13:00Z, "PAR-L-3", 2030-06-17T19:00Z
"Camp Nou", "PAR-A-5", 2030-06-19T13:00Z, "PAR-I-5", 2030-06-19T19:00Z
"Defensores del Chaco", "PAR-D-1", 2030-06-12T13:00Z, "PAR-L-1", 2030-06-12T19:00Z
"Defensores del Chaco", "PAR-A-3", 2030-06-14T13:00Z, "PAR-I-3", 2030-06-14T19:00Z
"Defensores del Chaco", "PAR-F-5", 2030-06-20T16:00Z, "PAR-N-5", 2030-06-20T22:00Z
"Estadio Centenario", "PAR-A-1", 2030-06-09T13:00Z, "PAR-I-1", 2030-06-09T19:00Z
"Estadio Centenario", "PAR-F-3", 2030-06-15T16:00Z, "PAR-N-3", 2030-06-15T22:00Z
"Estadio Centenario", "PAR-C-5", 2030-06-21T13:00Z, "PAR-K-5", 2030-06-21T19:00Z
"Estadio Monumental", "PAR-A-2", 2030-06-09T13:00Z, "PAR-I-2", 2030-06-09T19:00Z
"Estadio Monumental", "PAR-F-4", 2030-06-15T16:00Z, "PAR-N-4", 2030-06-15T22:00Z
"Estadio Monumental", "PAR-C-6", 2030-06-21T13:00Z, "PAR-K-6", 2030-06-21T19:00Z
"Estadio Moulay Abdellah", "PAR-F-1", 2030-06-10T16:00Z, "PAR-N-1", 2030-06-10T22:00Z
"Estadio Moulay Abdellah", "PAR-C-3", 2030-06-16T13:00Z, "PAR-K-3", 2030-06-16T19:00Z
"Estadio Moulay Abdellah", "PAR-H-5", 2030-06-22T16:00Z, "PAR-P-5", 2030-06-22T22:00Z
"Estádio José Alvalade", "PAR-H-2", 2030-06-12T16:00Z, "PAR-P-2", 2030-06-12T22:00Z
"Estádio José Alvalade", "PAR-E-4", 2030-06-14T16:00Z, "PAR-M-4", 2030-06-14T22:00Z
"Estádio José Alvalade", "PAR-B-6", 2030-06-20T13:00Z, "PAR-J-6", 2030-06-20T19:00Z
"Estádio da Luz", "PAR-H-1", 2030-06-12T16:00Z, "PAR-P-1", 2030-06-12T22:00Z
"Estádio da Luz", "PAR-E-3", 2030-06-14T16:00Z, "PAR-M-3", 2030-06-14T22:00Z
"Estádio da Luz", "PAR-B-5", 2030-06-20T13:00Z, "PAR-J-5", 2030-06-20T19:00Z
"Estádio do Dragão", "PAR-C-1", 2030-06-11T13:00Z, "PAR-K-1", 2030-06-11T19:00Z
"Estádio do Dragão", "PAR-H-3", 2030-06-17T16:00Z, "PAR-P-3", 2030-06-17T22:00Z
"Estádio do Dragão", "PAR-E-5", 2030-06-19T16:00Z, "PAR-M-5", 2030-06-19T22:00Z
"Grand Stade Hassan II", "PAR-C-2", 2030-06-11T13:00Z, "PAR-K-2", 2030-06-11T19:00Z
"Grand Stade Hassan II", "PAR-H-4", 2030-06-17T16:00Z, "PAR-P-4", 2030-06-17T22:00Z
"Grand Stade Hassan II", "PAR-E-6", 2030-06-19T16:00Z, "PAR-M-6", 2030-06-19T22:00Z
"Grand Stade de Marrakech", "PAR-F-2", 2030-06-10T16:00Z, "PAR-N-2", 2030-06-10T22:00Z
"Grand Stade de Marrakech", "PAR-C-4", 2030-06-16T13:00Z, "PAR-K-4", 2030-06-16T19:00Z
"Grand Stade de Marrakech", "PAR-H-6", 2030-06-22T16:00Z, "PAR-P-6", 2030-06-22T22:00Z
"La Cartuja", "PAR-B-1", 2030-06-10T13:00Z, "PAR-J-1", 2030-06-10T19:00Z
"La Cartuja", "PAR-G-3", 2030-06-16T16:00Z, "PAR-O-3", 2030-06-16T22:00Z
"La Cartuja", "PAR-D-5", 2030-06-22T13:00Z, "PAR-L-5", 2030-06-22T19:00Z
"Mestalla", "PAR-E-1", 2030-06-09T16:00Z, "PAR-M-1", 2030-06-09T22:00Z
"Mestalla", "PAR-B-3", 2030-06-15T13:00Z, "PAR-J-3", 2030-06-15T19:00Z
"Mestalla", "PAR-G-5", 2030-06-21T16:00Z, "PAR-O-5", 2030-06-21T22:00Z
"Metropolitano", "PAR-G-2", 2030-06-11T16:00Z, "PAR-O-2", 2030-06-11T22:00Z
"Metropolitano", "PAR-D-4", 2030-06-17T13:00Z, "PAR-L-4", 2030-06-17T19:00Z
"Metropolitano", "PAR-A-6", 2030-06-19T13:00Z, "PAR-I-6", 2030-06-19T19:00Z
"Riazor", "PAR-E-2", 2030-06-09T16:00Z, "PAR-M-2", 2030-06-09T22:00Z
"Riazor", "PAR-B-4", 2030-06-15T13:00Z, "PAR-J-4", 2030-06-15T19:00Z
"Riazor", "PAR-G-6", 2030-06-21T16:00Z, "PAR-O-6", 2030-06-21T22:00Z
"San Mamés", "PAR-B-2", 2030-06-10T13:00Z, "PAR-J-2", 2030-06-10T19:00Z
"San Mamés", "PAR-G-4", 2030-06-16T16:00Z, "PAR-O-4", 2030-06-16T22:00Z
"San Mamés", "PAR-D-6", 2030-06-22T13:00Z, "PAR-L-6", 2030-06-22T19:00Z
"Santiago Bernabéu", "PAR-D-2", 2030-06-12T13:00Z, "PAR-L-2", 2030-06-12T19:00Z
"Santiago Bernabéu", "PAR-A-4", 2030-06-14T13:00Z, "PAR-I-4", 2030-06-14T19:00Z
"Santiago Bernabéu", "PAR-F-6", 2030-06-20T16:00Z, "PAR-N-6", 2030-06-20T22:00Z
eventosHuerfanos
0
eventosConTipoDesconocido
0
jugadoresSinEquipo
0
partidosMalFormados
0
eventosSinSucesorIndebido
0
partidosConMarcadorInconsistente
0
golesSinAnota, asistenciasSinAsiste, tarjetasSinRecibeTarjeta, sustitucionesSinReemplaza, proyeccionesSinEvento, actuacionesSinParticipa
0, 0, 0, 0, 0, 0
empatesEnEliminatoria, ganadoresQueNoAvanzaron
0, 0
etiqueta, nodos
"Equipo", 64
"Evento", 1572
"Grupo", 16
"Jugador", 1282
"Partido", 127
"Sede", 16
"TipoEvento", 12
relacion, relaciones
"ANOTA", 220
"ASISTE", 220
"CAUSA_DE", 702
"CORRESPONDE_A", 96
"ES_DE_TIPO", 1572
"JUEGA_EN", 1282
"OCURRE_EN", 1572
"PARTICIPA", 1248
"PARTICIPA_EN", 254
"PERTENECE_A", 64
"PROTAGONIZADO_POR", 1572
"RECIBE_TARJETA", 136
"REEMPLAZA", 136
"SE_JUEGA_EN", 127
"SIGUIENTE_EVENTO", 1446
fase, estado, partidos, eventos
"GRUPOS", "FINALIZADO", 96, 1152
"DIECISEISAVOS", "FINALIZADO", 16, 220
"OCTAVOS", "FINALIZADO", 8, 116
"CUARTOS", "FINALIZADO", 4, 52
"SEMIFINAL", "FINALIZADO", 2, 32
"FINAL", "PROGRAMADO", 1, 0
goleador, equipo, goles, asistidores
"Tanaka, Facundo", "Bolivia", 7, ["Haddad #10 (7)"]
"Andersen, Bautista", "Brasil", 5, ["Van Dijk #10 (5)"]
"Fernández, Agustín", "Argentina", 5, ["Costa #10 (5)"]
"Müller, Marcos", "Inglaterra", 5, ["Andersen #10 (5)"]
"Novak, Rodrigo", "Chile", 5, ["Mensah #10 (5)"]
"Petrov, Bautista", "Bolivia", 5, ["Bekele #7 (5)"]
"Rossi, Franco", "Portugal", 5, ["Kovac #10 (5)"]
"Bekele, Nicolás", "Paraguay", 4, ["Gómez #10 (4)"]
"Bianchi, Alejandro", "Venezuela", 4, ["Vargas #10 (4)"]
"Costa, Joaquín", "Alemania", 4, ["Sorensen #10 (4)"]
"Costa, Valentino", "Ucrania", 4, ["Haddad #7 (4)"]
"Dubois, Julián", "Francia", 4, ["Moreno #10 (4)"]
"Gómez, Mateo", "Croacia", 4, ["Tanaka #10 (4)"]
"Haddad, Lucas", "Polonia", 4, ["Dubois #10 (4)"]
"Kovac, Bautista", "Ucrania", 4, ["Haddad #7 (4)"]
partido, fase, tarjetas, amarillas, rojas, detalle
"PAR-D16-03", "DIECISEISAVOS", 2, 1, 1, ["DEN · Fernández #4 · AMARILLA 31'", "DEN · Costa #5 · ROJA 86'"]
"PAR-D16-06", "DIECISEISAVOS", 2, 1, 1, ["SRB · Sorensen #4 · AMARILLA 31'", "SRB · Silva #5 · ROJA 86'"]
"PAR-D16-09", "DIECISEISAVOS", 2, 1, 1, ["SCO · Novak #4 · AMARILLA 31'", "SCO · Mensah #5 · ROJA 86'"]
"PAR-D16-12", "DIECISEISAVOS", 2, 1, 1, ["TUR · Bianchi #4 · AMARILLA 31'", "TUR · Vargas #5 · ROJA 86'"]
"PAR-D16-15", "DIECISEISAVOS", 2, 1, 1, ["GRE · Müller #4 · AMARILLA 31'", "GRE · Andersen #5 · ROJA 86'"]
"PAR-OCT-02", "OCTAVOS", 2, 1, 1, ["COL · Nakamura #4 · AMARILLA 31'", "COL · Álvarez #5 · ROJA 86'"]
"PAR-OCT-05", "OCTAVOS", 2, 1, 1, ["VEN · Costa #4 · AMARILLA 31'", "VEN · Sorensen #5 · ROJA 86'"]
"PAR-OCT-08", "OCTAVOS", 2, 1, 1, ["ITA · Mensah #4 · AMARILLA 31'", "ITA · Bianchi #5 · ROJA 86'"]
"PAR-CUA-03", "CUARTOS", 2, 1, 1, ["SWE · Tanaka #4 · AMARILLA 31'", "SWE · Haddad #5 · ROJA 86'"]
"PAR-SEM-02", "SEMIFINAL", 2, 1, 1, ["HUN · Dubois #4 · AMARILLA 31'", "HUN · Moreno #5 · ROJA 86'"]
"PAR-A-1", "GRUPOS", 1, 1, 0, ["NED · Álvarez #4 · AMARILLA 31'"]
"PAR-A-2", "GRUPOS", 1, 1, 0, ["IRN · Novak #4 · AMARILLA 31'"]
"PAR-A-3", "GRUPOS", 1, 1, 0, ["ROU · Costa #4 · AMARILLA 31'"]
"PAR-A-4", "GRUPOS", 1, 1, 0, ["IRN · Novak #4 · AMARILLA 31'"]
"PAR-A-5", "GRUPOS", 1, 1, 0, ["IRN · Novak #4 · AMARILLA 31'"]
"PAR-A-6", "GRUPOS", 1, 1, 0, ["ROU · Costa #4 · AMARILLA 31'"]
"PAR-B-1", "GRUPOS", 1, 1, 0, ["BEL · Haddad #4 · AMARILLA 31'"]
"PAR-B-2", "GRUPOS", 1, 1, 0, ["AUS · Nakamura #4 · AMARILLA 31'"]
"PAR-B-3", "GRUPOS", 1, 1, 0, ["WAL · Rossi #4 · AMARILLA 31'"]
"PAR-B-4", "GRUPOS", 1, 1, 0, ["AUS · Nakamura #4 · AMARILLA 31'"]
fase, partidos, amarillas, rojas, tarjetasPorPartido
"GRUPOS", 96, 96, 0, 1.0
"DIECISEISAVOS", 16, 16, 5, 1.31
"OCTAVOS", 8, 8, 3, 1.38
"CUARTOS", 4, 4, 1, 1.25
"SEMIFINAL", 2, 2, 1, 1.5
equipo, cadena, eslabones, combinacionesDePartidos, ejemplo
"Croacia", ["Nakamura #17", "Petrov #16", "Bekele #8"], 2, 8, ["PAR-OCT-01 80'", "PAR-SEM-01 62'"]
"Hungría", ["Mensah #17", "Novak #16", "Petrov #8"], 2, 6, ["PAR-OCT-07 80'", "PAR-O-4 62'"]
"Polonia", ["Okafor #17", "Álvarez #16", "Tanaka #8"], 2, 4, ["PAR-D16-05 80'", "PAR-OCT-03 62'"]
"Suecia", ["Silva #17", "Sorensen #16", "Rossi #8"], 2, 3, ["PAR-D16-11 80'", "PAR-L-4 62'"]
"Ucrania", ["Costa #17", "Fernández #16", "Dubois #8"], 2, 8, ["PAR-CUA-02 80'", "PAR-I-6 62'"]
finalista, ronda, partido, rival, resultado, goleadores
"Bolivia", "DIECISEISAVOS", "PAR-D16-09", "Escocia", "2-0", ["Tanaka 13'", "Petrov 82'"]
"Bolivia", "OCTAVOS", "PAR-OCT-05", "Venezuela", "2-0", ["Tanaka 13'", "Petrov 82'"]
"Bolivia", "CUARTOS", "PAR-CUA-03", "Suecia", "2-0", ["Tanaka 13'", "Petrov 82'"]
"Bolivia", "SEMIFINAL", "PAR-SEM-02", "Hungría", "2-0", ["Tanaka 13'", "Petrov 82'"]
"Bolivia", "FINAL", "PAR-FINAL", "Ucrania", "por jugar", []
"Ucrania", "DIECISEISAVOS", "PAR-D16-08", "Perú", "2-1", ["Kovac 75'", "Costa 89'"]
"Ucrania", "OCTAVOS", "PAR-OCT-04", "Chile", "2-1", ["Kovac 75'", "Costa 89'"]
"Ucrania", "CUARTOS", "PAR-CUA-02", "Polonia", "2-1", ["Kovac 75'", "Costa 89'"]
"Ucrania", "SEMIFINAL", "PAR-SEM-01", "Croacia", "2-1", ["Kovac 75'", "Costa 89'"]
"Ucrania", "FINAL", "PAR-FINAL", "Bolivia", "por jugar", []
jugador, equipo, posicion, partidos, goles, asistencias, tarjetas, entroDesdeElBanco, salioReemplazado, aporteDeGolPorPartido
"Haddad, Rodrigo", "Ucrania", "Mediocampista", 5, 0, 9, 0, 0, 0, 1.8
"Haddad, Tomás", "Bolivia", "Mediocampista", 7, 0, 7, 0, 0, 0, 1.0
"Tanaka, Facundo", "Bolivia", "Mediocampista", 7, 7, 0, 0, 0, 0, 1.0
"Andersen, Bautista", "Brasil", "Mediocampista", 5, 5, 0, 0, 0, 0, 1.0
"Andersen, Lucas", "Inglaterra", "Mediocampista", 5, 0, 5, 0, 0, 0, 1.0
"Bekele, Santiago", "Bolivia", "Mediocampista", 5, 0, 5, 0, 0, 0, 1.0
"Costa, Alejandro", "Argentina", "Mediocampista", 5, 0, 5, 0, 0, 0, 1.0
"Fernández, Agustín", "Argentina", "Mediocampista", 5, 5, 0, 0, 0, 0, 1.0
"Kovac, Ignacio", "Portugal", "Mediocampista", 5, 0, 5, 0, 0, 0, 1.0
"Mensah, Diego", "Chile", "Mediocampista", 5, 0, 5, 0, 0, 0, 1.0
"Müller, Marcos", "Inglaterra", "Mediocampista", 5, 5, 0, 0, 0, 0, 1.0
"Novak, Rodrigo", "Chile", "Mediocampista", 5, 5, 0, 0, 0, 0, 1.0
"Petrov, Bautista", "Bolivia", "Delantero", 5, 5, 0, 0, 0, 0, 1.0
"Rossi, Franco", "Portugal", "Mediocampista", 5, 5, 0, 0, 0, 0, 1.0
"Van Dijk, Julián", "Brasil", "Mediocampista", 5, 0, 5, 0, 0, 0, 1.0
"Kovac, Marcos", "Hungría", "Mediocampista", 3, 0, 5, 0, 0, 0, 1.67
"Van Dijk, Agustín", "Croacia", "Mediocampista", 3, 0, 5, 0, 0, 0, 1.67
"Bekele, Nicolás", "Paraguay", "Mediocampista", 4, 4, 0, 0, 0, 0, 1.0
"Bekele, Thiago", "Italia", "Mediocampista", 4, 0, 4, 0, 0, 0, 1.0
"Bianchi, Alejandro", "Venezuela", "Mediocampista", 4, 4, 0, 0, 0, 0, 1.0
tipo, direccion, relaciones, origenes, destinos, gradoSalidaMedio, gradoSalidaMax
"PARTICIPA", "Jugador -> Partido", 1248, 486, 126, 2.57, 7
"ANOTA", "Jugador -> Partido", 220, 106, 126, 2.08, 7
"ASISTE", "Jugador -> Jugador", 220, 96, 106, 2.29, 9
"RECIBE_TARJETA", "Jugador -> Partido", 136, 65, 126, 2.09, 5
"REEMPLAZA", "Jugador -> Jugador", 136, 53, 53, 2.57, 7
partidosJugados, jugadores
0, 796
1, 142
2, 142
3, 67
4, 78
5, 42
6, 6
7, 9
fase, minimo, maximo, promedio
"GRUPOS", 8, 11, 9.67
"DIECISEISAVOS", 8, 13, 10.5
"OCTAVOS", 8, 13, 11.0
"CUARTOS", 8, 13, 10.0
"SEMIFINAL", 11, 13, 12.0
golesDeLaSociedad, sociedades
7, 1
5, 6
4, 14
3, 4
2, 34
1, 47
patron, casos
"Entró desde el banco y convirtió", 10
"Convirtió y fue amonestado o expulsado", 0
"Asistencia recíproca (A asiste a B y B a A)", 0
"Expulsado en un partido que su equipo perdió", 10
exit=0
```

## 4. CRUD repetible (`crud.cypher`) y vuelta al estado de la carga

```bash
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/crud.cypher
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/carga.cypher   # conteos == primera corrida
```

```text
partidosResiduales, eventosResiduales, jugadorDemoResidual
0, 0, 0
mensaje
"crud.cypher finalizado · el grafo volvió al estado que dejó carga.cypher"
exit=0
```

```text
diff con la primera corrida: sin diferencias
```

## 5. API del Hito 10 contra este Neo4j

Pruebas unitarias (no necesitan bases; Python 3.13 local con `pyasyncore`, que el driver de Cassandra necesita fuera de 3.12):

```bash
cd fixture2030-hito10-api && .venv/Scripts/python.exe -m pytest -q
```

```text
.                                                                        [100%]
217 passed in 10.85s
```

La API corriendo con `uvicorn app.main:app --port 8127` y `NEO4J_URI=bolt://127.0.0.1:27688`; Mongo, Redis, Cassandra e InfluxDB apuntados a puertos sin servicio para no tocar las bases compartidas (las rutas de partidos solo usan Neo4j; la caché de Redis falla en silencio). Los tests de integración no se corrieron: usan los contenedores compartidos `fixture2030-*` y resiembran datos.

```bash
curl -s -w " [%{http_code}]\n" http://127.0.0.1:8127/partidos/<id>
```

```text
calentamiento (la API ya estaba levantada y el contenedor se recreó en la sección 1): GET /partidos/PAR-A-1 → 200
GET /partidos/PAR-A-1
{"partidoId":"PAR-A-1","fase":"GRUPOS","grupo":"A","jornada":1,"fechaHora":"2030-06-09T13:00:00Z","estado":"FINALIZADO","sede":{"sedeId":"URU-CEN","nombre":"Estadio Centenario","ciudad":"Montevideo","pais":"Uruguay","region":"AMERICAS"},"local":{"equipoCodigo":"ARG","nombre":"Argentina"},"visitante":{"equipoCodigo":"NED","nombre":"Países Bajos"},"marcador":{"golesLocal":1,"golesVisitante":0},"cantidadEventos":10} [200]
GET /partidos/PAR-D16-01
{"partidoId":"PAR-D16-01","fase":"DIECISEISAVOS","grupo":null,"jornada":4,"fechaHora":"2030-06-29T16:00:00Z","estado":"FINALIZADO","sede":{"sedeId":"URU-CEN","nombre":"Estadio Centenario","ciudad":"Montevideo","pais":"Uruguay","region":"AMERICAS"},"local":{"equipoCodigo":"ARG","nombre":"Argentina"},"visitante":{"equipoCodigo":"BEL","nombre":"Bélgica"},"marcador":{"golesLocal":1,"golesVisitante":0},"cantidadEventos":10} [200]
GET /partidos/PAR-OCT-01
{"partidoId":"PAR-OCT-01","fase":"OCTAVOS","grupo":null,"jornada":5,"fechaHora":"2030-07-04T16:00:00Z","estado":"FINALIZADO","sede":{"sedeId":"ESP-BER","nombre":"Santiago Bernabéu","ciudad":"Madrid","pais":"España","region":"EUROPA"},"local":{"equipoCodigo":"ARG","nombre":"Argentina"},"visitante":{"equipoCodigo":"CRO","nombre":"Croacia"},"marcador":{"golesLocal":1,"golesVisitante":2},"cantidadEventos":17} [200]
GET /partidos/PAR-CUA-02
{"partidoId":"PAR-CUA-02","fase":"CUARTOS","grupo":null,"jornada":6,"fechaHora":"2030-07-10T20:00:00Z","estado":"FINALIZADO","sede":{"sedeId":"POR-LUZ","nombre":"Estádio da Luz","ciudad":"Lisboa","pais":"Portugal","region":"EUROPA"},"local":{"equipoCodigo":"POL","nombre":"Polonia"},"visitante":{"equipoCodigo":"UKR","nombre":"Ucrania"},"marcador":{"golesLocal":1,"golesVisitante":2},"cantidadEventos":17} [200]
GET /partidos/PAR-SEM-02
{"partidoId":"PAR-SEM-02","fase":"SEMIFINAL","grupo":null,"jornada":7,"fechaHora":"2030-07-16T19:00:00Z","estado":"FINALIZADO","sede":{"sedeId":"MAR-HAS","nombre":"Grand Stade Hassan II","ciudad":"Casablanca","pais":"Marruecos","region":"AFRICA"},"local":{"equipoCodigo":"BOL","nombre":"Bolivia"},"visitante":{"equipoCodigo":"HUN","nombre":"Hungría"},"marcador":{"golesLocal":2,"golesVisitante":0},"cantidadEventos":15} [200]
GET /partidos/PAR-FINAL
{"partidoId":"PAR-FINAL","fase":"FINAL","grupo":null,"jornada":8,"fechaHora":"2030-07-21T19:00:00Z","estado":"PROGRAMADO","sede":{"sedeId":"MAR-HAS","nombre":"Grand Stade Hassan II","ciudad":"Casablanca","pais":"Marruecos","region":"AFRICA"},"local":{"equipoCodigo":"UKR","nombre":"Ucrania"},"visitante":{"equipoCodigo":"BOL","nombre":"Bolivia"},"marcador":null,"cantidadEventos":0} [200]
GET /partidos/PAR-X-99
{"code":"MATCH_NOT_FOUND","message":"No existe el partido PAR-X-99.","requestId":"req-683acb36b48347d2"} [404]
GET /partidos/PAR-FINAL/eventos      (caso de test_eventos_partido_sin_eventos_200_vacio)
{"partidoId":"PAR-FINAL","items":[],"limit":50,"nextCursor":null} [200]
GET /partidos/PAR-SEM-02/eventos?tipo=TARJETA_ROJA
{"partidoId":"PAR-SEM-02","items":[{"eventoId":"PAR-SEM-02-EV-14","partidoId":"PAR-SEM-02","secuencia":14,"tipo":"TARJETA_ROJA","minuto":86,"condicionEquipo":"VISITANTE","dorsalProtagonista":5,"protagonista":{"dni":"30690685","nombre":"Franco","apellido":"Moreno"},"timestamp":"2030-07-16T20:26:00Z","origen":"CARGA"}],"limit":50,"nextCursor":null} [200]
GET /partidos/PAR-OCT-01/eventos?limit=50  → cantidad de items y última secuencia
17 eventos; 17 FIN_PARTIDO
GET /equipos/UKR/partidos  → fases del recorrido
[('PAR-I-1', 'GRUPOS', 'FINALIZADO'), ('PAR-I-4', 'GRUPOS', 'FINALIZADO'), ('PAR-I-6', 'GRUPOS', 'FINALIZADO'), ('PAR-D16-08', 'DIECISEISAVOS', 'FINALIZADO'), ('PAR-OCT-04', 'OCTAVOS', 'FINALIZADO'), ('PAR-CUA-02', 'CUARTOS', 'FINALIZADO'), ('PAR-SEM-01', 'SEMIFINAL', 'FINALIZADO'), ('PAR-FINAL', 'FINAL', 'PROGRAMADO')]
```

## 6. Actualizar una base que tenía la carga anterior (112 partidos)

Volumen nuevo, carga del commit anterior (`33bc8c4`) y encima la carga nueva, sin borrar nada. Los conteos tienen que coincidir con los de la sección 1.

```bash
docker compose -p neo127 down -v && docker compose -p neo127 up -d
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/estructura.cypher
git show 33bc8c4:fixture2030-neo4j/queries/carga.cypher | docker exec -i neo127-neo4j cypher-shell -u neo4j -p fixture2030
docker exec neo127-neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/carga.cypher
```

Después de la carga anterior:

```text
"Evento", 1152
"Partido", 112
```

Después de correr la carga nueva encima:

```text
diff con la carga desde vacío (sección 1): sin diferencias
```

## 7. Limpieza

Al terminar se apagaron la API de prueba y el contenedor (`docker compose -p neo127 down -v`, que borra solo su volumen anónimo). No se tocó `fixture2030-neo4j` ni ningún otro contenedor.
