/// Script de carga (RF6). Desde la terminal de IRIS:
/// <example>
/// do ##class(Fixture.Carga).Ejecutar()
/// </example>
/// <ul>
/// <li>Jugadores: data/jugadores.csv, exportado del Hito 4 (MongoDB) con
/// scripts/exportar_desde_mongo.sh. Mismo dni, nombre, dorsal, posición y equipo.</li>
/// <li>Árbitros: 4 árbitros de ejemplo.</li>
/// <li>Partidos: los 6 del grupo A (equipos del grupo A del Hito 4), con los códigos,
/// fechas y sedes del Hito 5 y el mismo guion de goles y tarjetas que el grafo.</li>
/// </ul>
/// <p>Cada partido es un árbol: el padre (Partido) y sus hijos (Eventos) se arman en
/// memoria y se guardan con <b>una sola invocación</b> de <code>partido.%Save()</code>.</p>
/// <p>Si un jugador, árbitro o partido ya existe, no se vuelve a crear.</p>
Class Fixture.Carga Extends %RegisteredObject
{

ClassMethod Ejecutar(archivo As %String = "/home/irisowner/fixture/data/jugadores.csv") As %Status
{
	set sc = ..CargarJugadores(archivo)
	set:$$$ISOK(sc) sc = ..CargarArbitros()
	set:$$$ISOK(sc) sc = ..CargarPartidos()
	if $$$ISERR(sc) {
		write "✖ Carga detenida",!
		do $SYSTEM.Status.DisplayError(sc)
		write !
		quit sc
	}
	write "✔ Carga completada",!
	quit $$$OK
}

ClassMethod CargarJugadores(archivo As %String) As %Status
{
	set stream = ##class(%Stream.FileCharacter).%New()
	set stream.Filename = archivo, stream.TranslateTable = "UTF8"
	do stream.ReadLine()   // encabezado: dni,nombre,apellido,posicion,dorsal,equipo
	set nuevos = 0
	while 'stream.AtEnd {
		set linea = $translate(stream.ReadLine(), $char(13))
		continue:linea=""
		continue:##class(Fixture.Jugador).DocumentoIdxExists($piece(linea, ",", 1))
		set jugador = ##class(Fixture.Jugador).%New()
		set jugador.Documento = $piece(linea, ",", 1)
		set jugador.Nombre = $piece(linea, ",", 2)
		set jugador.Apellido = $piece(linea, ",", 3)
		set jugador.Posicion = $piece(linea, ",", 4)
		set jugador.Dorsal = $piece(linea, ",", 5)
		set jugador.Equipo = $piece(linea, ",", 6)
		set sc = jugador.%Save()
		return:$$$ISERR(sc) sc
		set nuevos = nuevos + 1
	}
	write "Jugadores (Hito 4) creados: ", nuevos, !
	quit $$$OK
}

ClassMethod CargarArbitros() As %Status
{
	set datos(1) = $listbuild("ARB-01", "Oliver", "Hastings", "FIFA_ELITE")
	set datos(2) = $listbuild("ARB-02", "Julien", "Moreau", "FIFA_ELITE")
	set datos(3) = $listbuild("ARB-03", "Youssef", "Benali", "FIFA")
	set datos(4) = $listbuild("ARB-04", "Kenji", "Sato", "FIFA")
	set nuevos = 0
	for i = 1:1:4 {
		continue:##class(Fixture.Arbitro).DocumentoIdxExists($list(datos(i), 1))
		set arbitro = ##class(Fixture.Arbitro).%New()
		set arbitro.Documento = $list(datos(i), 1), arbitro.Nombre = $list(datos(i), 2)
		set arbitro.Apellido = $list(datos(i), 3), arbitro.Categoria = $list(datos(i), 4)
		set sc = arbitro.%Save()
		return:$$$ISERR(sc) sc
		set nuevos = nuevos + 1
	}
	write "Árbitros creados: ", nuevos, !
	quit $$$OK
}

/// Jugador de un equipo por dorsal. El dni sigue la fórmula del Hito 4 (índice del
/// equipo en la lista del Hito 4 × 100 + dorsal), así que se busca por equipo y dorsal.
ClassMethod Jugador(equipo As %String, dorsal As %Integer) As Fixture.Jugador
{
	set rs = ##class(%SQL.Statement).%ExecDirect(, "SELECT ID FROM Fixture.Jugador WHERE Equipo = ? AND Dorsal = ?", equipo, dorsal)
	quit $select(rs.%Next(): ##class(Fixture.Jugador).%OpenId(rs.ID), 1: "")
}

ClassMethod NuevoEvento(tipo As %String, minuto As %Integer, jugador As Fixture.Jugador) As Fixture.Evento
{
	set evento = ##class(Fixture.Evento).%New()
	set evento.Tipo = tipo, evento.Minuto = minuto, evento.Jugador = jugador
	quit evento
}

/// Los 6 partidos del grupo A. Código, fecha y sede: fórmulas del Hito 5
/// (carga.cypher PASO 6). Guion de eventos: el del Hito 5 (PASO 7), según el orden del
/// partido en el torneo: gol local al 13' (#9) y amarilla al visitante al 31' (#4);
/// el 2.º y el 5.º partido suman gol visitante al 75' (#11); el 3.º y el 6.º, gol local
/// al 82' (#15).
ClassMethod CargarPartidos() As %Status
{
	set datos(1) = $listbuild("PAR-A-1", "2030-06-09 13:00:00", "URU-CEN", "ARG", "BRA")
	set datos(2) = $listbuild("PAR-A-2", "2030-06-09 13:00:00", "ARG-MON", "URY", "COL")
	set datos(3) = $listbuild("PAR-A-3", "2030-06-14 13:00:00", "PAR-DCH", "ARG", "URY")
	set datos(4) = $listbuild("PAR-A-4", "2030-06-14 13:00:00", "ESP-BER", "BRA", "COL")
	set datos(5) = $listbuild("PAR-A-5", "2030-06-19 13:00:00", "ESP-CAM", "ARG", "COL")
	set datos(6) = $listbuild("PAR-A-6", "2030-06-19 13:00:00", "ESP-MET", "BRA", "URY")
	set nuevos = 0
	for i = 1:1:6 {
		set fila = datos(i), local = $list(fila, 4), visita = $list(fila, 5)
		continue:##class(Fixture.Partido).CodigoIdxExists($list(fila, 1))
		// Padre
		set partido = ##class(Fixture.Partido).%New()
		set partido.Codigo = $list(fila, 1), partido.FechaHora = $list(fila, 2), partido.Sede = $list(fila, 3)
		set partido.EquipoLocal = local, partido.EquipoVisitante = visita
		set partido.Arbitro = ##class(Fixture.Arbitro).DocumentoIdxOpen("ARB-0"_(((i - 1) # 4) + 1))
		set sc = partido.Iniciar()
		// Hijos
		set:$$$ISOK(sc) sc = partido.RegistrarEvento(..NuevoEvento("GOL", 13, ..Jugador(local, 9)))
		set:$$$ISOK(sc) sc = partido.RegistrarEvento(..NuevoEvento("TARJETA_AMARILLA", 31, ..Jugador(visita, 4)))
		if (i - 1) # 3 = 1 { set:$$$ISOK(sc) sc = partido.RegistrarEvento(..NuevoEvento("GOL", 75, ..Jugador(visita, 11))) }
		if (i - 1) # 3 = 2 { set:$$$ISOK(sc) sc = partido.RegistrarEvento(..NuevoEvento("GOL", 82, ..Jugador(local, 15))) }
		set:$$$ISOK(sc) sc = partido.Finalizar()
		// Una sola invocación de guardado para todo el árbol
		set:$$$ISOK(sc) sc = partido.%Save()
		return:$$$ISERR(sc) sc
		write "  ", partido.Codigo, " ", local, " ", partido.GolesLocal, "-", partido.GolesVisitante, " ", visita
		write " · ", partido.Eventos.Count(), " eventos guardados con un único %Save()", !
		set nuevos = nuevos + 1
	}
	write "Partidos creados: ", nuevos, !
	quit $$$OK
}

}
