import { describe, expect, it } from 'vitest'
import { appendPage, emptyCursorState, hayMas, normalizarCursor } from './pagination'

interface J {
  dni: string
}
const id = (j: J) => j.dni

describe('paginación por cursor', () => {
  it('acumula páginas, conserva el último nextCursor y no repite ítems', () => {
    let s = emptyCursorState<J>()
    s = appendPage(s, { items: [{ dni: '1' }, { dni: '2' }], nextCursor: 'abc' }, id)
    expect(hayMas(s)).toBe(true)
    expect(s.nextCursor).toBe('abc')
    s = appendPage(s, { items: [{ dni: '2' }, { dni: '3' }], nextCursor: null }, id)
    expect(s.items.map(id)).toEqual(['1', '2', '3'])
    expect(s.pages).toBe(2)
    expect(hayMas(s)).toBe(false)
  })

  it('trata cursor ausente o vacío como fin de la lista', () => {
    expect(normalizarCursor(undefined)).toBeNull()
    expect(normalizarCursor('')).toBeNull()
    expect(normalizarCursor('eyJ2IjoxfQ==')).toBe('eyJ2IjoxfQ==')
  })
})
