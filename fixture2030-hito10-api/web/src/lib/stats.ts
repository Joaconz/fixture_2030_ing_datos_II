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
