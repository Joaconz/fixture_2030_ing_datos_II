import { describe, expect, it } from 'vitest'
import { addMinutes, isoToUtcInput, utcInputToIso } from './time'

describe('fechas en UTC', () => {
  it('precarga creadoEn = fechaHora + 47 min, en UTC', () => {
    expect(isoToUtcInput(addMinutes('2030-06-09T13:00:00Z', 47))).toBe('2030-06-09T13:47')
  })
  it('convierte el datetime-local (leído como UTC) a ISO con Z', () => {
    expect(utcInputToIso('2030-06-09T13:47')).toBe('2030-06-09T13:47:00Z')
    expect(utcInputToIso('2030-06-09T13:47:30')).toBe('2030-06-09T13:47:30Z')
    expect(utcInputToIso('')).toBeNull()
  })
  it('respeta el offset de la fuente', () => {
    expect(isoToUtcInput('2030-06-09T10:00:00-03:00')).toBe('2030-06-09T13:00')
  })
})
