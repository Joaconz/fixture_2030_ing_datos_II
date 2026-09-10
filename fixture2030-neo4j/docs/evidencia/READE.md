REGISTRO DE EVIDENCIAS TÉCNICAS - HITO 5: MÓDULO DE GRAFOS (Neo4j)

Este documento reune las evidencias de ejecucion, validacion de carga y consultas del subgrafo del Fixture 2030 en Neo4j Browser.

==================================================

1. Despliegue del Entorno Local (RF1, RNF1, RNF2)

* Estado del Servicio: Contenedor Neo4j ejecutandose en Docker mediante la imagen neo4j:latest con acceso web en http://localhost:7474.
* Persistencia: Verificacion de puertos expuestos (7474 y 7687) y volumenes nombrados activos.


Imagen asociada: 01_ambiente_docker.png

==================================================

2. Restricciones de Integridad e Indices (RF10)

* Unicidad: Confirmacion en consola mediante SHOW CONSTRAINTS; de las restricciones aplicadas sobre los identificadores unicos de Equipo, Evento, Grupo, Jugador y Partido.
* Modelo Cargado: Menu lateral desplegando la totalidad de las etiquetas (2.654 nodos) y tipos de relaciones (6.802 relaciones) del torneo.


Imagen asociada: 02_restricciones_indices.png

==================================================

3. Carga de Datos e Idempotencia (RF6, RNF3, RNF4)

* Poblado del Grafo: Verificacion del recuento total de 2.654 nodos generados en el subgrafo del Fixture 2030.
* Reproducibilidad: Ejecucion de verificacion mediante Cypher MATCH (n) RETURN count(n) AS TotalNodos;.


Imagen asociada: 03_carga_idempotente.png

==================================================

4. Consultas con Patrones Multi-salto (RF8)

* Visualizacion de Grafo: Consulta con recorrido de multiples relaciones consecutivas entre entidades del torneo mediante la sentencia MATCH p=(:Partido)-[:PARTICIPA_EN]-(:Equipo)-[:PERTENECE_A]-(:Grupo) RETURN p LIMIT 15;.
* Analisis del Recorrido: La consulta navega a traves de dos saltos relacionales para conectar los partidos disputados con sus respectivos equipos y la asignacion de estos a los grupos del Mundial 2030, permitiendo explorar la estructura del fixture de manera visual e interactiva en Neo4j Browser.


Imagen asociada: 04_consultas_multisalto.jpg
