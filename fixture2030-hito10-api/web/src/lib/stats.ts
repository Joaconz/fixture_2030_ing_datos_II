import type { PartidoDetalle, PuntoEstadistica } from '../api/types'

export type Metrica = 'posesionPct' | 'golesAcum' | 'pasesAcum' | 'tirosAcum'

export interface SerieEquipo {
  equipoCodigo: string
  label: string
  variant: 0 | 1
  points: Array<{ t: number; v: number }>
}

/** Agrupa los puntos por equipo y extrae una métrica (ignora nulos), local primero. */
export function seriesPorEquipo(puntos: PuntoEstadistica[], metrica: Metrica, partido: PartidoDetalle): SerieEquipo[] {
  const porEquipo = new Map<string, PuntoEstadistica[]>()
  for (const p of puntos) {
    const lista = porEquipo.get(p.equipoCodigo) ?? []
    lista.push(p)
    porEquipo.set(p.equipoCodigo, lista)
  }
  const orden = (codigo: string, cond: string | null | undefined) =>
    cond === 'LOCAL' || codigo === partido.local.equipoCodigo ? 0 : 1

  return Array.from(porEquipo.entries())
    .map(([codigo, lista]) => {
      const variant = orden(codigo, lista[0]?.condicion) as 0 | 1
      const points = lista
        .map((p) => ({ t: Date.parse(p.time), v: p[metrica] }))
        .filter((p): p is { t: number; v: number } => typeof p.v === 'number' && Number.isFinite(p.t))
        .sort((a, b) => a.t - b.t)
      const cond = variant === 0 ? 'local' : 'visitante'
      return { equipoCodigo: codigo, label: `${codigo} (${cond})`, variant, points }
    })
    .sort((a, b) => a.variant - b.variant)
}

/**
 * Períodos del partido sobre el reloj de pared de las estadísticas (Hito 8):
 * el primer tiempo corre de 0′ a 47′, hay 15 min de entretiempo sin datos y el
 * segundo tiempo va de 62′ a 110′. Todas las ventanas quedan bajo el tope de 3 h.
 */
export type Periodo = 'primer' | 'segundo' | 'completo'

export const PERIODOS: ReadonlyArray<{ key: Periodo; label: string; desdeMin: number; hastaMin: number }> = [
  { key: 'primer', label: '1T', desdeMin: 0, hastaMin: 48 },
  { key: 'segundo', label: '2T', desdeMin: 60, hastaMin: 112 },
  { key: 'completo', label: 'Completo', desdeMin: 0, hastaMin: 112 },
]

const isoSinMs = (ms: number) => new Date(ms).toISOString().replace('.000Z', 'Z')

/** Ventana [desde, hasta) en ISO UTC para un período, a partir de la hora de inicio del partido. */
export function ventanaDePeriodo(fechaHora: string, periodo: Periodo): { desde: string; hasta: string } {
  const p = PERIODOS.find((x) => x.key === periodo)
  const desdeMin = p?.desdeMin ?? 0
  const hastaMin = p?.hastaMin ?? 112
  const t0 = Date.parse(fechaHora)
  return { desde: isoSinMs(t0 + desdeMin * 60_000), hasta: isoSinMs(t0 + hastaMin * 60_000) }
}

/** Último valor no nulo de una métrica para un equipo (los acumulados crecen con el tiempo). */
export function ultimoValor(puntos: readonly PuntoEstadistica[], equipoCodigo: string, metrica: Metrica): number | null {
  let mejor: { t: number; v: number } | null = null
  for (const p of puntos) {
    const v = p[metrica]
    const t = Date.parse(p.time)
    if (p.equipoCodigo !== equipoCodigo || typeof v !== 'number' || !Number.isFinite(t)) continue
    if (mejor === null || t >= mejor.t) mejor = { t, v }
  }
  return mejor?.v ?? null
}

/** Promedio de una métrica para un equipo en la ventana (posesión media). */
export function promedio(puntos: readonly PuntoEstadistica[], equipoCodigo: string, metrica: Metrica): number | null {
  const valores = puntos
    .filter((p) => p.equipoCodigo === equipoCodigo)
    .map((p) => p[metrica])
    .filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  if (valores.length === 0) return null
  return valores.reduce((a, b) => a + b, 0) / valores.length
}

export interface FilaComparativa {
  metrica: Metrica
  label: string
  local: number | null
  visitante: number | null
  /** Porcentaje de la barra local (0–100); 50 si los dos valen 0. */
  pctLocal: number
}

const COMPARABLES: ReadonlyArray<{ m: Metrica; label: string }> = [
  { m: 'golesAcum', label: 'Goles' },
  { m: 'tirosAcum', label: 'Tiros' },
  { m: 'pasesAcum', label: 'Pases' },
]

/** Comparativa local/visitante con el último acumulado de la ventana. */
export function comparativa(puntos: readonly PuntoEstadistica[], partido: PartidoDetalle): FilaComparativa[] {
  return COMPARABLES.map(({ m, label }) => {
    const local = ultimoValor(puntos, partido.local.equipoCodigo, m)
    const visitante = ultimoValor(puntos, partido.visitante.equipoCodigo, m)
    const a = local ?? 0
    const b = visitante ?? 0
    return { metrica: m, label, local, visitante, pctLocal: a + b === 0 ? 50 : (a / (a + b)) * 100 }
  })
}

/**
 * Instante del reloj de pared → minuto de juego, con el mismo reloj que la
 * carga del Hito 8 (entretiempo de 15 min entre 47′ y 62′ de pared).
 */
export function minutoDeJuego(t: number, fechaHora: string): number {
  const m = Math.floor((t - Date.parse(fechaHora)) / 60_000)
  if (m <= 47) return Math.max(0, m)
  if (m < 62) return 45
  return 45 + (m - 62)
}
