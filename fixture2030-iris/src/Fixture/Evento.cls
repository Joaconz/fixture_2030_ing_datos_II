/// Evento de un partido (gol o tarjeta). Es <b>hijo</b> de Fixture.Partido (relación
/// padre-hijo, RF3): no existe sin su partido, se guarda con él y se borra con él.
/// <p>Los códigos de tipo son los mismos del catálogo de tipos de evento del Hito 5
/// (Neo4j). En IRIS se guardan los goles y las tarjetas que definen el resultado del
/// partido; el flujo completo de eventos para recorrer como grafo sigue en Neo4j.</p>
Class Fixture.Evento Extends %Persistent
{

/// Lado hijo de la relación padre-hijo.
Relationship Partido As Fixture.Partido [ Cardinality = parent, Inverse = Eventos ];

Property Tipo As %String(VALUELIST = ",GOL,TARJETA_AMARILLA,TARJETA_ROJA") [ Required ];

/// El tipo admite 0: el rechazo del minuto 0 es una regla del partido (RegistrarEvento).
Property Minuto As %Integer(MINVAL = 0, MAXVAL = 130) [ Required ];

Property Jugador As Fixture.Jugador [ Required ];

/// RNF3: índice sobre la propiedad relacional del lado "muchos".
Index PartidoIdx On Partido;

}
