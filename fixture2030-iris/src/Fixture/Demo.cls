/// Demostración desde la terminal de IRIS (§5.3, RF7, RF8, RF9). Requiere haber corrido
/// Fixture.Carga.
/// <example>
/// do ##class(Fixture.Demo).Todo()
/// </example>
/// Cada bloque también se puede invocar solo: ArbolAtomico, RequeridoOmitido,
/// Navegacion, TransicionIlegal, ProyeccionSQL.
Class Fixture.Demo Extends %RegisteredObject
{

ClassMethod Todo()
{
	do ..ArbolAtomico()
	do ..RequeridoOmitido()
	do ..Navegacion()
	do ..TransicionIlegal()
	do ..ProyeccionSQL()
	do ..BorrarPartidoDemo()
}

ClassMethod Titulo(texto As %String)
{
	write !,"=== ",texto," ===",!
}

ClassMethod Resultado(descripcion As %String, sc As %Status)
{
	if $SYSTEM.Status.IsOK(sc) { write "  OK · ",descripcion,! quit }
	write "  RECHAZADO · ",descripcion,!
	write "    ",$SYSTEM.Status.GetErrorText(sc),!
}

/// §5.3: se asigna estado al padre, luego al hijo, y un solo %Save() del padre guarda
/// los dos (RF6).
ClassMethod ArbolAtomico()
{
	do ..Titulo("1. Padre e hijo guardados con un solo %Save() del padre (RF6)")
	do ..BorrarPartidoDemo()
	set partido = ##class(Fixture.Partido).%New()
	set partido.Codigo = "PAR-DEMO-01", partido.FechaHora = "2030-07-05 16:00:00", partido.Sede = "ARG-MON"
	set partido.EquipoLocal = "ARG", partido.EquipoVisitante = "URY"
	set partido.Arbitro = ##class(Fixture.Arbitro).DocumentoIdxOpen("ARB-01")
	do ..Resultado("Padre: partido.Iniciar()", partido.Iniciar())
	set gol = ##class(Fixture.Carga).NuevoEvento("GOL", 23, ##class(Fixture.Carga).Jugador("ARG", 9))
	do ..Resultado("Hijo: partido.RegistrarEvento(gol al 23')", partido.RegistrarEvento(gol))
	write "  Antes de guardar: ID partido = """,partido.%Id(),""" · ID evento = """,gol.%Id(),"""",!
	do ..Resultado("partido.%Save()  (única invocación)", partido.%Save())
	write "  Después: ID partido = ",partido.%Id()," · ID evento = ",gol.%Id()," (padre||hijo)",!
	set id = partido.%Id()
	kill partido, gol
	set partido = ##class(Fixture.Partido).%OpenId(id)
	write "  Releído de la base: ",partido.Codigo," · ",partido.Estado," · eventos: ",partido.Eventos.Count(),!
}

/// §5.3: carga que falla de forma controlada por una propiedad requerida omitida.
ClassMethod RequeridoOmitido()
{
	do ..Titulo("2. Carga que falla por una propiedad requerida omitida (RF5)")
	set partido = ##class(Fixture.Partido).%New()
	set partido.Codigo = "PAR-DEMO-02", partido.FechaHora = "2030-07-06 16:00:00"
	set partido.EquipoLocal = "BRA", partido.EquipoVisitante = "COL"
	set partido.Arbitro = ##class(Fixture.Arbitro).DocumentoIdxOpen("ARB-02")
	do ..Resultado("Partido sin Sede: partido.%Save()", partido.%Save())
	write "  ¿Se guardó PAR-DEMO-02? ",$select(##class(Fixture.Partido).CodigoIdxExists("PAR-DEMO-02"): "sí", 1: "no"),!
}

/// RF7: consulta navegando referencias de objetos, sin SQL.
ClassMethod Navegacion()
{
	do ..Titulo("3. Navegación por referencias de objetos, sin SQL (RF7)")
	set partido = ##class(Fixture.Partido).CodigoIdxOpen("PAR-A-3")
	write "  partido.Codigo → ",partido.Codigo," · ",partido.EquipoLocal," ",partido.GolesLocal,"-",partido.GolesVisitante," ",partido.EquipoVisitante," · ",partido.Estado,!
	write "  partido.Arbitro.NombreCompleto() → ",partido.Arbitro.NombreCompleto(),!
	write "  partido.Eventos (hijos):",!
	set clave = ""
	for {
		set evento = partido.Eventos.GetNext(.clave)
		quit:clave=""
		write "    ",evento.Minuto,"' ",evento.Tipo," · evento.Jugador.NombreCompleto() → ",evento.Jugador.NombreCompleto()
		write " (#",evento.Jugador.Dorsal,", ",evento.Jugador.Equipo,") · evento.Partido.Codigo → ",evento.Partido.Codigo,!
	}
}

/// RF9: la operación encapsulada rechaza una transición ilegal.
ClassMethod TransicionIlegal()
{
	do ..Titulo("4. Transición de estado ilegal (RF9)")
	set partido = ##class(Fixture.Partido).CodigoIdxOpen("PAR-A-1")
	write "  PAR-A-1 está ",partido.Estado," con ",partido.Eventos.Count()," eventos",!
	set evento = ##class(Fixture.Carga).NuevoEvento("GOL", 0, ##class(Fixture.Carga).Jugador("ARG", 9))
	do ..Resultado("partido.RegistrarEvento(gol en el minuto 0)", partido.RegistrarEvento(evento))
	write "  PAR-A-1 sigue con ",partido.Eventos.Count()," eventos",!
	set partido.Estado = "EN_JUEGO"
	do ..Resultado("Cambiar el estado a mano y guardar (%OnBeforeSave)", partido.%Save())
	do partido.%Reload()
}

/// §5.3 y RF8: los objetos cargados son visibles y operables por SQL.
ClassMethod ProyeccionSQL()
{
	do ..Titulo("5. Las mismas entidades por SQL (RF8)")
	set sql(1) = "SELECT Codigo, EquipoLocal, GolesLocal, GolesVisitante, EquipoVisitante, Estado, Arbitro->Apellido AS Arbitro FROM Fixture.Partido ORDER BY Codigo"
	set sql(2) = "SELECT Partido->Codigo AS Partido, Minuto, Tipo, Jugador->Documento AS Dni, Jugador->Apellido AS Jugador FROM Fixture.Evento WHERE Partido->Codigo = 'PAR-A-3' ORDER BY Minuto"
	set sql(3) = "SELECT $PIECE(%EXACT(x__classname), '~', 2) AS Clase, COUNT(*) AS Cantidad FROM Fixture.Persona GROUP BY x__classname"
	for i = 1:1:3 {
		write !,"SQL> ",sql(i),!
		do ##class(%SQL.Statement).%ExecDirect(, sql(i)).%Display()
		write !
	}
	write !,"SQL> UPDATE Fixture.Arbitro SET Categoria = 'FIFA_ELITE' WHERE Documento = 'ARB-03'",!
	write "  Filas: ",##class(%SQL.Statement).%ExecDirect(, "UPDATE Fixture.Arbitro SET Categoria = 'FIFA_ELITE' WHERE Documento = 'ARB-03'").%ROWCOUNT,!
	write "  Leído como objeto: ##class(Fixture.Arbitro).DocumentoIdxOpen(""ARB-03"").Categoria → ",##class(Fixture.Arbitro).DocumentoIdxOpen("ARB-03").Categoria,!
	do ##class(%SQL.Statement).%ExecDirect(, "UPDATE Fixture.Arbitro SET Categoria = 'FIFA' WHERE Documento = 'ARB-03'")
}

/// Borra el partido de demostración: sus eventos se borran con él (relación padre-hijo).
ClassMethod BorrarPartidoDemo()
{
	set partido = ##class(Fixture.Partido).CodigoIdxOpen("PAR-DEMO-01")
	quit:'$isobject(partido)
	set id = partido.%Id(), idEvento = partido.Eventos.GetNext("").%Id()
	kill partido
	do ##class(Fixture.Partido).%DeleteId(id)
	write !,"=== Limpieza: se borra PAR-DEMO-01 ===",!
	write "  ¿Existe todavía su evento ",idEvento,"? ",$select(##class(Fixture.Evento).%ExistsId(idEvento): "sí", 1: "no (se borró con el partido)"),!
}

}
