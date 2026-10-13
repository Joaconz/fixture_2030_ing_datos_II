import { afterEach, describe, expect, it, vi } from 'vitest'

function respuesta(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

async function conFetch(fn: (req: Request) => Response) {
  vi.resetModules()
  vi.stubGlobal('fetch', vi.fn(async (req: Request) => fn(req)))
  return import('./endpoints')
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('cliente tipado', () => {
  it('expone X-Request-Id y X-Cache del detalle de partido', async () => {
    const { getPartido } = await conFetch(() =>
      respuesta(
        200,
        {
          partidoId: 'PAR-A-1',
          fase: 'GRUPOS',
          fechaHora: '2030-06-09T13:00:00Z',
          estado: 'FINALIZADO',
          local: { equipoCodigo: 'URU', nombre: 'Uruguay' },
          visitante: { equipoCodigo: 'ARG', nombre: 'Argentina' },
          cantidadEventos: 10,
        },
        { 'X-Request-Id': 'req-1', 'X-Cache': 'HIT' },
      ),
    )
    const r = await getPartido('PAR-A-1')
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.meta.requestId).toBe('req-1')
    expect(r.meta.cache).toBe('HIT')
    expect(r.data.local.equipoCodigo).toBe('URU')
  })

  it('envía Idempotency-Key y reconoce Idempotent-Replayed', async () => {
    let clave: string | null = null
    const { registrarEvento } = await conFetch((req) => {
      clave = req.headers.get('Idempotency-Key')
      return respuesta(
        200,
        { eventoId: 'PAR-X-EV-1', partidoId: 'PAR-X', secuencia: 3, tipo: 'GOL', minuto: 88 },
        { 'Idempotent-Replayed': 'true', 'X-Request-Id': 'req-2' },
      )
    })
    const r = await registrarEvento('PAR-X', 'evt-1234567890', { tipo: 'GOL', minuto: 88 })
    expect(clave).toBe('evt-1234567890')
    expect(r.ok && r.meta.replayed && r.meta.status === 200).toBe(true)
  })

  it('un 409 llega como ApiFailure con su code', async () => {
    const { cerrarPartido } = await conFetch(() =>
      respuesta(409, { code: 'MISSING_FIN_PARTIDO', message: 'Falta FIN_PARTIDO.', requestId: 'req-3' }),
    )
    const r = await cerrarPartido('PAR-DEMO-API')
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.error.kind).toBe('conflict')
    expect(r.error.code).toBe('MISSING_FIN_PARTIDO')
  })

  it('/health/dependencias con 503 devuelve el detalle como dato, no como error', async () => {
    const { getSaludDependencias } = await conFetch(() =>
      respuesta(503, {
        estado: 'DEGRADADO',
        dependencias: [
          { nombre: 'mongodb', estado: 'UP', latenciaMs: 2.1 },
          { nombre: 'cassandra', estado: 'DOWN', detalle: 'timeout' },
        ],
      }),
    )
    const r = await getSaludDependencias()
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.meta.status).toBe(503)
    expect(r.data.dependencias.find((d) => d.nombre === 'cassandra')?.estado).toBe('DOWN')
  })

  it('sin respuesta HTTP (API apagada o CORS) es un error de red', async () => {
    vi.resetModules()
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    const { getHealth } = await import('./endpoints')
    const r = await getHealth()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.kind).toBe('network')
  })
})
