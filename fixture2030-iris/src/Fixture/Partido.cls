/// Partido del Fixture 2030 (necesidad N2: el Hito 2 lo asignó a Objetos/IRIS y el
/// Hito 3 le exige consistencia fuerte en el cierre).
/// <p>Es una máquina de estados (PROGRAMADO → EN_JUEGO → FINALIZADO) y es el
/// <b>padre</b> de su lista de eventos (relación padre-hijo, RF3): un único
/// <code>%Save()</code> del partido guarda también sus eventos nuevos (RF6), y borrar
/// el partido borra sus eventos.</p>
Class Fixture.Partido Extends %Persistent
{

/// Mismo código que en los Hitos 5 a 8 (ej. PAR-A-1).
Property Codigo As %String(MAXLEN = 20) [ Required ];

Property FechaHora As %TimeStamp [ Required ];

/// Código de la sede (= Sede.sedeId del Hito 5, ej. URU-CEN).
Property Sede As %String(MAXLEN = 7) [ Required ];

/// Códigos FIFA de los equipos (= equipos._id del Hito 4).
Property EquipoLocal As %String(PATTERN = "3U") [ Required ];

Property EquipoVisitante As %String(PATTERN = "3U") [ Required ];

Property Arbitro As Fixture.Arbitro [ Required ];

Property Estado As %String(VALUELIST = ",PROGRAMADO,EN_JUEGO,FINALIZADO") [ InitialExpression = "PROGRAMADO", Required ];

/// Resultado: lo calcula Finalizar() a partir de los goles registrados.
Property GolesLocal As %Integer(MINVAL = 0);

Property GolesVisitante As %Integer(MINVAL = 0);

/// Lista subordinada de eventos (lado padre de la relación padre-hijo).
Relationship Eventos As Fixture.Evento [ Cardinality = children, Inverse = Partido ];

Index CodigoIdx On Codigo [ Unique ];

/// PROGRAMADO → EN_JUEGO.
Method Iniciar() As %Status
{
	if ..Estado '= "PROGRAMADO" quit $$$ERROR($$$GeneralError, "Transición ilegal: "_..Codigo_" está "_..Estado_" y sólo un partido PROGRAMADO puede iniciarse")
	set ..Estado = "EN_JUEGO"
	quit $$$OK
}

/// RF9: agrega un evento a la lista del partido sólo si la transición es legal. Si no,
/// devuelve el error y el partido queda igual.
Method RegistrarEvento(evento As Fixture.Evento) As %Status
{
	if '$isobject(evento) || '$isobject(evento.Jugador) quit $$$ERROR($$$GeneralError, "RegistrarEvento: el evento necesita un jugador")
	if ..Estado '= "EN_JUEGO" {
		quit $$$ERROR($$$GeneralError, "Transición ilegal: "_..Codigo_" está "_..Estado_"; sólo se registran eventos con el partido EN_JUEGO")
	}
	if (evento.Minuto < 1) || (evento.Minuto > 130) {
		quit $$$ERROR($$$GeneralError, "Minuto "_evento.Minuto_" inválido en "_..Codigo_": el minuto 0 es el inicio del partido, no un evento")
	}
	if (evento.Jugador.Equipo '= ..EquipoLocal) && (evento.Jugador.Equipo '= ..EquipoVisitante) {
		quit $$$ERROR($$$GeneralError, "El jugador "_evento.Jugador.Documento_" ("_evento.Jugador.Equipo_") no juega "_..Codigo)
	}
	set evento.Partido = $this
	quit $$$OK
}

/// EN_JUEGO → FINALIZADO: fija el resultado contando los goles de la lista de eventos.
Method Finalizar() As %Status
{
	if ..Estado '= "EN_JUEGO" quit $$$ERROR($$$GeneralError, "Transición ilegal: "_..Codigo_" está "_..Estado_" y sólo un partido EN_JUEGO puede finalizarse")
	set ..GolesLocal = 0, ..GolesVisitante = 0, clave = ""
	for {
		set evento = ..Eventos.GetNext(.clave)
		quit:clave=""
		continue:evento.Tipo'="GOL"
		if evento.Jugador.Equipo = ..EquipoLocal { set ..GolesLocal = ..GolesLocal + 1 } else { set ..GolesVisitante = ..GolesVisitante + 1 }
	}
	set ..Estado = "FINALIZADO"
	quit $$$OK
}

/// RF8 y matriz de integridad: "un partido FINALIZADO no se modifica" tiene que valer
/// también por SQL. %OnBeforeSave sólo se ejecuta en el acceso por objetos (%Save());
/// un UPDATE por SQL no lo llama. Un trigger con Foreach = row/object se ejecuta en los
/// DOS caminos: UPDATE por SQL y %Save() de un partido existente.
Trigger FinalizadoInmutable [ Event = UPDATE, Foreach = row/object, Time = BEFORE ]
{
	if {Estado*O} = "FINALIZADO" {
		set %ok = 0
		set %msg = "El partido "_{Codigo*O}_" está FINALIZADO y no puede modificarse (también por SQL)"
	}
}

/// Validación del objeto entero antes de guardarlo (§5.2): dos equipos distintos, y un
/// partido ya FINALIZADO en la base no se modifica.
Method %OnBeforeSave(insert As %Boolean) As %Status [ Private, ServerOnly = 1 ]
{
	if ..EquipoLocal = ..EquipoVisitante quit $$$ERROR($$$GeneralError, "Un partido necesita dos equipos distintos")
	if 'insert && (..EstadoGetStored(..%Id()) = "FINALIZADO") {
		quit $$$ERROR($$$GeneralError, "El partido "_..Codigo_" está FINALIZADO y no puede modificarse")
	}
	quit $$$OK
}

}
