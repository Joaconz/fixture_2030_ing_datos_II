/// Persona del dominio del torneo: clase persistente base de la herencia (RF4).
/// <p>Es abstracta porque en el Fixture no existe "una persona" suelta: siempre es un
/// Jugador o un Árbitro. Las dos subclases comparten esta estructura y el mismo
/// extent, así que en SQL <code>Fixture.Persona</code> devuelve a todas y
/// <code>Fixture.Jugador</code> sólo a los jugadores.</p>
/// <p>Las subclases representan tipos, no estados (nota 7 del enunciado).</p>
Class Fixture.Persona Extends %Persistent [ Abstract ]
{

/// Para un Jugador es <code>jugadores.dni</code> del Hito 4 (MongoDB).
Property Documento As %String(MAXLEN = 20) [ Required ];

Property Nombre As %String(MAXLEN = 60) [ Required ];

Property Apellido As %String(MAXLEN = 60) [ Required ];

Index DocumentoIdx On Documento [ Unique ];

Method NombreCompleto() As %String
{
	quit ..Nombre_" "_..Apellido
}

}
