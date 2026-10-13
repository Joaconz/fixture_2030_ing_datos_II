import { describe, expect, it } from 'vitest'
import spec from '../../../openapi/openapi.yaml?raw'
import { IDEMPOTENCY_KEY_PATTERN, esIdempotencyKeyValida, nuevaIdempotencyKey } from './idempotency'

describe('Idempotency-Key', () => {
  it('usa el mismo patrón que declara el contrato OpenAPI', () => {
    const declarados = Array.from(spec.matchAll(/name: Idempotency-Key[\s\S]*?pattern: (\S+)/g), (m) => m[1])
    expect(declarados.length).toBeGreaterThanOrEqual(2) // POST eventos y POST comentarios
    for (const p of declarados) expect(p).toBe(IDEMPOTENCY_KEY_PATTERN.source)
  })

  it('genera claves válidas y distintas en cada envío', () => {
    const claves = new Set(Array.from({ length: 200 }, () => nuevaIdempotencyKey('evt')))
    expect(claves.size).toBe(200)
    for (const k of claves) {
      expect(esIdempotencyKeyValida(k)).toBe(true)
      expect(k).toMatch(/^evt-[0-9a-f]{32}$/)
    }
  })

  it('rechaza prefijos que romperían el patrón', () => {
    expect(() => nuevaIdempotencyKey('con espacio')).toThrow()
    expect(esIdempotencyKeyValida('corta')).toBe(false)
  })
})
