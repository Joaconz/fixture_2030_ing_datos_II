import { describe, expect, it } from 'vitest'
import type { PartidoDetalle, PuntoEstadistica } from '../api/types'
import { comparativa, minutoDeJuego, promedio, ultimoValor, ventanaDePeriodo } from './stats'

const partido: PartidoDetalle = {
  partidoId: 'PAR-A-1',
  fase: 'Fase de grupos',
  fechaHora: '2030-06-09T13:00:00Z',
  estado: 'FINALIZADO',
  local: { equipoCodigo: 'URU', nombre: 'Uruguay' },
  visitante: { equipoCodigo: 'POR', nombre: 'Portugal' },
  cantidadEventos: 0,
}

const p = (time: string, equipoCodigo: string, over: Partial<PuntoEstadistica>): PuntoEstadistica => ({
  time,
  equipoCodigo,
  ...over,
})

const puntos: PuntoEstadistica[] = [
  p('2030-06-09T13:01:00Z', 'URU', { golesAcum: 0, tirosAcum: 1, posesionPct: 60 }),
  p('2030-06-09T13:20:00Z', 'URU', { golesAcum: 1, tirosAcum: 4, posesionPct: 50 }),
  p('2030-06-09T13:10:00Z', 'URU', { golesAcum: 0, tirosAcum: null, posesionPct: 55 }),
  p('2030-06-09T13:20:00Z', 'POR', { golesAcum: 0, tirosAcum: 2, posesionPct: 50 }),
]

describe('ventanaDePeriodo', () => {
  it('arma ventanas UTC por tiempo de juego, todas por debajo de 3 h', () => {
    expect(ventanaDePeriodo(partido.fechaHora, 'primer')).toEqual({
      desde: '2030-06-09T13:00:00Z',
      hasta: '2030-06-09T13:48:00Z',
    })
    expect(ventanaDePeriodo(partido.fechaHora, 'segundo')).toEqual({
      desde: '2030-06-09T14:00:00Z',
      hasta: '2030-06-09T14:52:00Z',
    })
    const c = ventanaDePeriodo(partido.fechaHora, 'completo')
    expect(Date.parse(c.hasta) - Date.parse(c.desde)).toBeLessThanOrEqual(3 * 3600_000)
  })
})

describe('resúmenes', () => {
  it('toma el último valor no nulo de cada equipo, sin depender del orden', () => {
    expect(ultimoValor(puntos, 'URU', 'golesAcum')).toBe(1)
    expect(ultimoValor(puntos, 'URU', 'tirosAcum')).toBe(4)
    expect(ultimoValor(puntos, 'ARG', 'golesAcum')).toBeNull()
  })

  it('promedia la posesión de la ventana', () => {
    expect(promedio(puntos, 'URU', 'posesionPct')).toBe(55)
    expect(promedio([], 'URU', 'posesionPct')).toBeNull()
  })

  it('compara local y visitante; con ceros reparte la barra al 50 %', () => {
    const filas = comparativa(puntos, partido)
    const goles = filas.find((f) => f.metrica === 'golesAcum')
    const tiros = filas.find((f) => f.metrica === 'tirosAcum')
    const pases = filas.find((f) => f.metrica === 'pasesAcum')
    expect(goles).toMatchObject({ local: 1, visitante: 0, pctLocal: 100 })
    expect(tiros?.pctLocal).toBeCloseTo(66.67, 1)
    expect(pases).toMatchObject({ local: null, visitante: null, pctLocal: 50 })
  })
})

describe('minutoDeJuego', () => {
  const t0 = Date.parse(partido.fechaHora)
  it('respeta el entretiempo del reloj de las estadísticas', () => {
    expect(minutoDeJuego(t0 + 30 * 60_000, partido.fechaHora)).toBe(30)
    expect(minutoDeJuego(t0 + 55 * 60_000, partido.fechaHora)).toBe(45)
    expect(minutoDeJuego(t0 + 92 * 60_000, partido.fechaHora)).toBe(75)
    expect(minutoDeJuego(t0 - 60_000, partido.fechaHora)).toBe(0)
  })
})
