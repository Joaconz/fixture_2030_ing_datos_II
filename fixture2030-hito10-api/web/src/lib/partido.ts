/**
 * Presentación de partidos y eventos para el hincha: nada de esto inventa
 * datos, sólo arma textos con lo que entrega la API.
 */
import { ETIQUETA_TIPO } from '../api/enums'
import type { Evento, PartidoDeEquipo, PartidoDetalle, TipoEvento } from '../api/types'

export type EstadoPartido = PartidoDetalle['estado']

/** La API sólo informa PROGRAMADO y FINALIZADO: no hay estado "en vivo". */
export const ETIQUETA_ESTADO: Record<EstadoPartido, string> = {
  PROGRAMADO: 'Programado',
  FINALIZADO: 'Finalizado',
}

export interface Marcador {
  local: number
  visitante: number
}

/** Marcador del detalle (CU4): la API lo deriva de los goles y lo publica al cerrar el partido. */
export function marcadorDeDetalle(p: PartidoDetalle): Marcador | null {
  const m = p.marcador
  return m ? { local: m.golesLocal, visitante: m.golesVisitante } : null
}

/** Marcador de un partido de la lista del equipo (CU3): sólo si vienen los dos goles. */
export function marcadorDePartidoDeEquipo(p: PartidoDeEquipo): Marcador | null {
  if (typeof p.golesLocal !== 'number' || typeof p.golesVisitante !== 'number') return null
  return { local: p.golesLocal, visitante: p.golesVisitante }
}

const FASES: Record<string, string> = {
  GRUPOS: 'Fase de grupos',
  DIECISEISAVOS: 'Dieciseisavos de final',
  OCTAVOS: 'Octavos de final',
  CUARTOS: 'Cuartos de final',
  SEMIFINAL: 'Semifinal',
  SEMIFINALES: 'Semifinal',
  TERCER_PUESTO: 'Tercer puesto',
  FINAL: 'Final',
  DEMO: 'Partido de demostración',
}

/** "GRUPOS" → "Fase de grupos"; una fase desconocida se muestra en minúsculas legibles. */
export function etiquetaFase(fase: string): string {
  const conocida = FASES[fase.trim().toUpperCase()]
  if (conocida) return conocida
  const texto = fase.trim().replaceAll('_', ' ').toLowerCase()
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

/** "Fase de grupos · Grupo A · Jornada 2", con lo que haya. */
export function descripcionFase(p: { fase: string; grupo?: string | null; jornada?: number | null }): string {
  const partes = [etiquetaFase(p.fase)]
  if (p.grupo) partes.push(`Grupo ${p.grupo}`)
  if (typeof p.jornada === 'number') partes.push(`Jornada ${p.jornada}`)
  return partes.join(' · ')
}

/** Código del equipo que protagoniza el evento, o null si el evento es del partido (inicio, fin). */
export function equipoDeEvento(ev: Evento, p: PartidoDetalle): { codigo: string; nombre: string } | null {
  if (ev.condicionEquipo === 'LOCAL') return { codigo: p.local.equipoCodigo, nombre: p.local.nombre }
  if (ev.condicionEquipo === 'VISITANTE') return { codigo: p.visitante.equipoCodigo, nombre: p.visitante.nombre }
  return null
}

/** "L. Messi #10", "Dorsal #10" o null si el evento no tiene protagonista. */
export function protagonistaCorto(ev: Evento): string | null {
  const dorsal = typeof ev.dorsalProtagonista === 'number' ? ` #${ev.dorsalProtagonista}` : ''
  if (ev.protagonista) {
    const inicial = ev.protagonista.nombre.trim().charAt(0)
    const nombre = inicial ? `${inicial}. ${ev.protagonista.apellido}` : ev.protagonista.apellido
    return `${nombre}${dorsal}`
  }
  return dorsal ? `Dorsal${dorsal}` : null
}

/** Título de la tarjeta del timeline: "L. Messi #10 · Gol" o sólo el tipo. */
export function tituloEvento(ev: Evento): string {
  const quien = protagonistaCorto(ev)
  return quien ? `${quien} · ${ETIQUETA_TIPO[ev.tipo]}` : ETIQUETA_TIPO[ev.tipo]
}

/** Familia visual de cada tipo (ícono y color del eje). */
export type FamiliaEvento = 'gol' | 'amarilla' | 'roja' | 'cambio' | 'marco' | 'juego'

export function familiaEvento(tipo: TipoEvento): FamiliaEvento {
  switch (tipo) {
    case 'GOL':
    case 'PENAL':
      return 'gol'
    case 'TARJETA_AMARILLA':
      return 'amarilla'
    case 'TARJETA_ROJA':
      return 'roja'
    case 'SUSTITUCION':
      return 'cambio'
    case 'INICIO_PARTIDO':
    case 'FIN_PARTIDO':
      return 'marco'
    default:
      return 'juego'
  }
}

/** Filtros principales como chips; el resto de los 12 tipos va en un selector. */
export const TIPOS_DESTACADOS: readonly TipoEvento[] = ['GOL', 'TARJETA_AMARILLA', 'TARJETA_ROJA', 'SUSTITUCION']

/** Partidos de un equipo ordenados por fecha (la API no garantiza el orden). */
export function ordenarPorFecha<T extends { fechaHora: string }>(partidos: readonly T[]): T[] {
  return [...partidos].sort((a, b) => Date.parse(a.fechaHora) - Date.parse(b.fechaHora))
}
