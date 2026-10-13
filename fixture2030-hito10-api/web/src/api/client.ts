/**
 * Cliente tipado de la API: `openapi-fetch` sobre los tipos generados del
 * contrato (`schema.d.ts`). `run()` envuelve cada llamada y devuelve un
 * resultado discriminado con los metadatos HTTP que la UI muestra
 * (status, X-Request-Id, X-Cache, Idempotent-Replayed, Retry-After).
 */
import createClient from 'openapi-fetch'
import { API_URL } from '../config'
import type { paths } from './schema'
import type { CacheStatus } from './types'
import { networkFailure, parseApiError, parseRetryAfter, type ApiFailure } from './errors'

export const api = createClient<paths>({ baseUrl: API_URL })

export interface ResponseMeta {
  status: number
  requestId: string | null
  cache: CacheStatus | null
  replayed: boolean
  retryAfter: number | null
  durationMs: number
}

export type ApiResult<T> =
  | { ok: true; data: T; meta: ResponseMeta }
  | { ok: false; error: ApiFailure; meta: ResponseMeta | null }

/** Forma mínima de lo que devuelve openapi-fetch. */
interface FetchLike<T> {
  data?: T
  error?: unknown
  response: Response
}

function parseCache(valor: string | null): CacheStatus | null {
  return valor === 'HIT' || valor === 'MISS' || valor === 'BYPASS' ? valor : null
}

export function metaFrom(response: Response, durationMs: number): ResponseMeta {
  const h = response.headers
  return {
    status: response.status,
    requestId: h.get('X-Request-Id'),
    cache: parseCache(h.get('X-Cache')),
    replayed: h.get('Idempotent-Replayed') === 'true',
    retryAfter: parseRetryAfter(h.get('Retry-After')),
    durationMs,
  }
}

export interface RunOptions<T> {
  /**
   * Algunas rutas devuelven un cuerpo útil con status de error
   * (`/health/dependencias` responde 503 con el mismo cuerpo que el 200).
   * Si esta función devuelve algo distinto de null, se trata como dato.
   */
  acceptError?: (status: number, body: unknown) => T | null
}

export async function run<T>(exec: () => Promise<FetchLike<T>>, options: RunOptions<T> = {}): Promise<ApiResult<T>> {
  const t0 = performance.now()
  let res: FetchLike<T>
  try {
    res = await exec()
  } catch (causa) {
    return { ok: false, error: networkFailure(causa), meta: null }
  }
  const meta = metaFrom(res.response, Math.round(performance.now() - t0))
  if (res.response.ok) {
    // openapi-fetch garantiza `data` del tipo de la respuesta 2xx del contrato
    // (undefined sólo en 204, donde T es `undefined`).
    return { ok: true, data: res.data as T, meta }
  }
  const aceptado = options.acceptError?.(res.response.status, res.error) ?? null
  if (aceptado !== null) return { ok: true, data: aceptado, meta }
  return { ok: false, error: parseApiError(res.response.status, res.error, res.response.headers), meta }
}
