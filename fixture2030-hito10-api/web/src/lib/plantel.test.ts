import { describe, expect, it } from 'vitest'
import type { Jugador } from '../api/types'
import { lineasDelPlantel, nombreCorto } from './plantel'

const j = (dorsal: number, posicion: Jugador['posicion']): Jugador => ({
  dni: `D${dorsal}`,
  nombre: 'Nombre',
  apellido: `Apellido${dorsal}`,
  fechaNacimiento: '1995-01-01',
  posicion,
  dorsal,
  equipoCodigo: 'ARG',
})

describe('lineasDelPlantel', () => {
  it('ordena las líneas del arco al ataque y los jugadores por dorsal', () => {
    const lineas = lineasDelPlantel([j(9, 'Delantero'), j(1, 'Arquero'), j(4, 'Defensor'), j(2, 'Defensor')])
    expect(lineas.map((l) => l.titulo)).toEqual(['Arqueros', 'Defensores', 'Delanteros'])
    expect(lineas[1]?.jugadores.map((x) => x.dorsal)).toEqual([2, 4])
  })

  it('no muestra líneas vacías', () => {
    expect(lineasDelPlantel([])).toEqual([])
  })
})

describe('nombreCorto', () => {
  it('usa la inicial del nombre', () => {
    expect(nombreCorto({ nombre: 'Lionel', apellido: 'Messi' })).toBe('L. Messi')
    expect(nombreCorto({ nombre: '', apellido: 'Messi' })).toBe('Messi')
  })
})
