import { describe, expect, it } from 'vitest'
import { validarCodigoFifa } from './fifa'

describe('validarCodigoFifa', () => {
  it('normaliza mayúsculas y espacios', () => {
    expect(validarCodigoFifa('  arg ')).toEqual({ ok: true, codigo: 'ARG' })
  })

  it('distingue vacío de formato inválido (mismo patrón que la API: ^[A-Z]{3}$)', () => {
    expect(validarCodigoFifa('   ')).toMatchObject({ ok: false, motivo: 'vacio' })
    expect(validarCodigoFifa('123')).toMatchObject({ ok: false, motivo: 'formato' })
    expect(validarCodigoFifa('ARGE')).toMatchObject({ ok: false, motivo: 'formato' })
    expect(validarCodigoFifa('AR')).toMatchObject({ ok: false, motivo: 'formato' })
  })
})
