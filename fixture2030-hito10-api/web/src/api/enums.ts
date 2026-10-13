/**
 * Listas en tiempo de ejecución de los enums del contrato (para selects y filtros).
 *
 * `todosLos<T>()` exige que el arreglo contenga TODOS los valores del tipo
 * generado: si el contrato agrega o quita un valor, esto deja de compilar.
 */
import type { Agregacion, Condicion, NombreDependencia, Posicion, TipoEvento } from './types'

type Faltantes<T extends string, A extends readonly T[]> = Exclude<T, A[number]>

function todosLos<T extends string>() {
  return <const A extends readonly T[]>(
    valores: A & ([Faltantes<T, A>] extends [never] ? unknown : { faltan: Faltantes<T, A> }),
  ): A => valores
}

export const TIPOS_EVENTO = todosLos<TipoEvento>()([
  'INICIO_PARTIDO',
  'PASE',
  'CORNER',
  'ATAJADA',
  'ASISTENCIA',
  'GOL',
  'PENAL',
  'FALTA',
  'TARJETA_AMARILLA',
  'TARJETA_ROJA',
  'SUSTITUCION',
  'FIN_PARTIDO',
])

export const ETIQUETA_TIPO: Record<TipoEvento, string> = {
  INICIO_PARTIDO: 'Inicio del partido',
  FIN_PARTIDO: 'Fin del partido',
  PASE: 'Pase',
  CORNER: 'Córner',
  ATAJADA: 'Atajada',
  ASISTENCIA: 'Asistencia',
  GOL: 'Gol',
  PENAL: 'Penal',
  FALTA: 'Falta',
  TARJETA_AMARILLA: 'Tarjeta amarilla',
  TARJETA_ROJA: 'Tarjeta roja',
  SUSTITUCION: 'Sustitución',
}

export const POSICIONES = todosLos<Posicion>()(['Arquero', 'Defensor', 'Mediocampista', 'Delantero'])

export const CONDICIONES = todosLos<Condicion>()(['LOCAL', 'VISITANTE'])

export const ETIQUETA_CONDICION: Record<Condicion, string> = {
  LOCAL: 'Local',
  VISITANTE: 'Visitante',
}

export const AGREGACIONES = todosLos<Agregacion>()(['raw', '1m', '5m'])

export const ETIQUETA_AGREGACION: Record<Agregacion, string> = {
  raw: 'Crudo',
  '1m': '1 min',
  '5m': '5 min',
}

export const DEPENDENCIAS = todosLos<NombreDependencia>()(['mongodb', 'neo4j', 'cassandra', 'redis', 'influxdb'])
