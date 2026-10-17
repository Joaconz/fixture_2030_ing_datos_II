import { describe, expect, it } from 'vitest'
import { dependencyFrom, kindFromStatus, nombreFuente, parseApiError, parseRetryAfter } from './errors'

const h = (o: Record<string, string>) => new Headers(o)

describe('parseApiError', () => {
  it('respeta {code, message, requestId, details} y clasifica 400 con detalle por campo', () => {
    const e = parseApiError(
      400,
      {
        code: 'VALIDATION_ERROR',
        message: 'La request no cumple el contrato.',
        requestId: 'req-abc',
        details: [{ campo: 'minuto', problema: 'debe ser ≤ 130' }],
      },
      h({ 'X-Request-Id': 'req-header' }),
    )
    expect(e.kind).toBe('validation')
    expect(e.code).toBe('VALIDATION_ERROR')
    expect(e.requestId).toBe('req-abc')
    expect(e.details).toEqual([{ campo: 'minuto', problema: 'debe ser ≤ 130' }])
    expect(e.dependency).toBeNull()
  })

  it('distingue 404, 403 y 409 por status', () => {
    expect(kindFromStatus(404)).toBe('not_found')
    expect(kindFromStatus(403)).toBe('forbidden')
    expect(kindFromStatus(409)).toBe('conflict')
    expect(kindFromStatus(500)).toBe('server')
    expect(kindFromStatus(418)).toBe('unexpected')
  })

  it('en 503 extrae la fuente caída de details y el Retry-After', () => {
    const e = parseApiError(
      503,
      {
        code: 'DEPENDENCY_UNAVAILABLE',
        message: "La fuente 'cassandra' no está disponible. Reintentar más tarde.",
        requestId: 'req-503',
        details: [{ campo: 'dependencia', problema: 'cassandra' }],
      },
      h({ 'Retry-After': '5' }),
    )
    expect(e.kind).toBe('unavailable')
    expect(e.dependency).toBe('cassandra')
    expect(e.retryAfter).toBe(5)
    expect(nombreFuente(e.dependency ?? '')).toBe('Cassandra')
  })

  it('en 504 (timeout de la fuente, Hito 11) conserva el code y extrae la fuente', () => {
    const e = parseApiError(
      504,
      {
        code: 'DEPENDENCY_TIMEOUT',
        message: "La fuente 'influxdb' no respondió dentro del tiempo límite. Reintentar más tarde.",
        requestId: 'req-504',
        details: [{ campo: 'dependencia', problema: 'influxdb' }],
      },
      h({ 'Retry-After': '5' }),
    )
    expect(e.kind).toBe('unavailable')
    expect(e.code).toBe('DEPENDENCY_TIMEOUT')
    expect(e.dependency).toBe('influxdb')
  })

  it('si el cuerpo no cumple el formato usa X-Request-Id y un code sintético', () => {
    const e = parseApiError(502, '<html>Bad gateway</html>', h({ 'X-Request-Id': 'req-hdr' }))
    expect(e.kind).toBe('server')
    expect(e.code).toBe('HTTP_502')
    expect(e.requestId).toBe('req-hdr')
    expect(e.details).toEqual([])
  })

  it('descarta details mal formados', () => {
    const e = parseApiError(400, { code: 'X', message: 'm', requestId: 'r', details: [{ campo: 1 }, { campo: 'a', problema: 'b' }] }, null)
    expect(e.details).toEqual([{ campo: 'a', problema: 'b' }])
  })
})

describe('helpers', () => {
  it('dependencyFrom cae al mensaje si no hay details', () => {
    expect(dependencyFrom([], "La fuente 'neo4j' no respondió dentro del tiempo límite.")).toBe('neo4j')
    expect(dependencyFrom([], 'otro mensaje')).toBeNull()
  })
  it('parseRetryAfter acepta segundos y rechaza basura', () => {
    expect(parseRetryAfter('12')).toBe(12)
    expect(parseRetryAfter(null)).toBeNull()
    expect(parseRetryAfter('mañana')).toBeNull()
  })
})
