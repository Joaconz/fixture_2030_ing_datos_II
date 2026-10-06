/// Jugador (RF4: subclase de Fixture.Persona). Usa la identidad del Hito 4: Documento =
/// <code>jugadores.dni</code> y Equipo = <code>jugadores.equipoId</code> (código FIFA),
/// cargados desde data/jugadores.csv, que se exporta de MongoDB.
Class Fixture.Jugador Extends Fixture.Persona
{

Property Dorsal As %Integer(MINVAL = 1, MAXVAL = 99) [ Required ];

Property Posicion As %String(VALUELIST = ",Arquero,Defensor,Mediocampista,Delantero") [ Required ];

/// Código FIFA del equipo (= equipos._id del Hito 4).
Property Equipo As %String(PATTERN = "3U") [ Required ];

}
