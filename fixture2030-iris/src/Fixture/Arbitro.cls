/// Árbitro (RF4: subclase de Fixture.Persona). Cada partido tiene un árbitro asignado.
Class Fixture.Arbitro Extends Fixture.Persona
{

Property Categoria As %String(VALUELIST = ",FIFA,FIFA_ELITE") [ Required ];

}
