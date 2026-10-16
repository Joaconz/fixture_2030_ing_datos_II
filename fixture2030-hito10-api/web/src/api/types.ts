/**
 * Alias de los tipos generados desde `openapi/openapi.yaml` (npm run gen:api).
 * Nada de esto se escribe a mano: si el contrato cambia, `schema.d.ts` cambia
 * y el compilador marca cada uso que quedó desalineado.
 */
import type { components, operations } from './schema'

type S = components['schemas']

export type Equipo = S['Equipo']
export type Jugador = S['Jugador']
export type PaginaJugadores = S['PaginaJugadores']
export type PartidoDeEquipo = S['PartidoDeEquipo']
export type PartidosDeEquipo = S['PartidosDeEquipo']
export type PartidoDetalle = S['PartidoDetalle']
export type Evento = S['Evento']
export type EventoNuevo = S['EventoNuevo']
export type PaginaEventos = S['PaginaEventos']
export type Comentario = S['Comentario']
export type ComentarioNuevo = S['ComentarioNuevo']
export type PaginaComentarios = S['PaginaComentarios']
export type Sesion = S['Sesion']
export type EstadisticasPartido = S['EstadisticasPartido']
export type PuntoEstadistica = S['PuntoEstadistica']
export type SaludDependencias = S['SaludDependencias']
export type EstadoDependencia = S['EstadoDependencia']
export type ErrorResponse = S['ErrorResponse']
export type ErrorDetalle = S['ErrorDetalle']

export type TipoEvento = Evento['tipo']
export type Posicion = Jugador['posicion']
export type Condicion = NonNullable<EventoNuevo['condicionEquipo']>
export type Agregacion = NonNullable<
  NonNullable<operations['getEstadisticasDePartido']['parameters']['query']>['agregacion']
>
export type NombreDependencia = EstadoDependencia['nombre']
export type CacheStatus = NonNullable<
  operations['getPartido']['responses'][200]['headers']['X-Cache']
>
