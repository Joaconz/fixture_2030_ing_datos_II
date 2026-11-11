import { POSICIONES } from '../api/enums'
import type { Jugador, Posicion } from '../api/types'

/** Plural de cada línea, en el orden del campo (arco → ataque). */
export const NOMBRE_LINEA: Record<Posicion, string> = {
  Arquero: 'Arqueros',
  Defensor: 'Defensores',
  Mediocampista: 'Mediocampistas',
  Delantero: 'Delanteros',
}

/** Abreviatura de la posición para las listas compactas (POR, DEF, MED, DEL). */
export const SIGLA_POSICION: Record<Posicion, string> = {
  Arquero: 'POR',
  Defensor: 'DEF',
  Mediocampista: 'MED',
  Delantero: 'DEL',
}

export interface Linea {
  posicion: Posicion
  titulo: string
  jugadores: Jugador[]
}

/** Agrupa jugadores por posición en el orden del campo y por dorsal; omite las líneas vacías. */
export function lineasDelPlantel(jugadores: readonly Jugador[]): Linea[] {
  return POSICIONES.map((posicion) => ({
    posicion,
    titulo: NOMBRE_LINEA[posicion],
    jugadores: jugadores.filter((j) => j.posicion === posicion).sort((a, b) => a.dorsal - b.dorsal),
  })).filter((l) => l.jugadores.length > 0)
}

/** "L. Messi" */
export function nombreCorto(j: Pick<Jugador, 'nombre' | 'apellido'>): string {
  const inicial = j.nombre.trim().charAt(0)
  return inicial ? `${inicial}. ${j.apellido}` : j.apellido
}
