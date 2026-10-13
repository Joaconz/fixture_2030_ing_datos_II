/**
 * Normalización de errores. Toda respuesta de error de la API tiene la forma
 * `{code, message, requestId, details?}` (RF12); acá se le agrega la "clase"
 * de error que decide cómo se muestra (404 ≠ 400 ≠ 409 ≠ 403 ≠ 503).
 */
import type { ErrorDetalle, ErrorResponse } from './types'

export type ErrorKind =
  | 'validation' // 400: entrada inválida (con details por campo)
  | 'forbidden' // 403
  | 'not_found' // 404: el recurso no existe
  | 'conflict' // 409: el estado del recurso impide la operación
  | 'unavailable' // 503: la fuente de datos está caída
  | 'server' // 500 y otros 5xx
  | 'network' // no hubo respuesta HTTP (API apagada, CORS, red local, mixed content)
  | 'unexpected' // cualquier otro status
  | 'aborted' // la request se canceló (cambio de ruta): no se muestra

export interface ApiFailure {
  kind: ErrorKind
  status: number | null
  code: string
  message: string
  requestId: string | null
  details: ErrorDetalle[]
  /** Fuente caída (sólo 503), p. ej. "mongodb". */
  dependency: string | null
  /** Segundos sugeridos por `Retry-After` (sólo 503). */
  retryAfter: number | null
}

export function isErrorResponse(body: unknown): body is ErrorResponse {
  if (typeof body !== 'object' || body === null) return false
  const b = body as Record<string, unknown>
  return typeof b.code === 'string' && typeof b.message === 'string' && typeof b.requestId === 'string'
}

function esDetalle(d: unknown): d is ErrorDetalle {
  if (typeof d !== 'object' || d === null) return false
  const r = d as Record<string, unknown>
  return typeof r.campo === 'string' && typeof r.problema === 'string'
}

export function kindFromStatus(status: number): ErrorKind {
  if (status === 400) return 'validation'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not_found'
  if (status === 409) return 'conflict'
  if (status === 503) return 'unavailable'
  if (status >= 500) return 'server'
  return 'unexpected'
}

const MENSAJE_POR_DEFECTO: Record<ErrorKind, string> = {
  validation: 'La request no cumple el contrato.',
  forbidden: 'Acceso denegado.',
  not_found: 'El recurso no existe.',
  conflict: 'El estado actual del recurso impide la operación.',
  unavailable: 'Una fuente de datos no está disponible.',
  server: 'Error interno de la API.',
  network: 'No se pudo conectar con la API.',
  unexpected: 'Respuesta inesperada de la API.',
  aborted: 'Request cancelada.',
}

export function parseRetryAfter(valor: string | null): number | null {
  if (valor === null || valor.trim() === '') return null
  const n = Number(valor)
  if (Number.isFinite(n) && n >= 0) return Math.round(n)
  const fecha = Date.parse(valor)
  if (Number.isNaN(fecha)) return null
  return Math.max(0, Math.round((fecha - Date.now()) / 1000))
}

/** Extrae la fuente caída de un 503: primero `details[campo=dependencia]`, si no del mensaje. */
export function dependencyFrom(details: ErrorDetalle[], message: string): string | null {
  const det = details.find((d) => d.campo === 'dependencia')
  if (det) return det.problema
  const m = /fuente\s+'([^']+)'/i.exec(message)
  return m?.[1] ?? null
}

/** Convierte una respuesta HTTP de error (status + cuerpo + cabeceras) en un ApiFailure. */
export function parseApiError(status: number, body: unknown, headers: Headers | null): ApiFailure {
  const kind = kindFromStatus(status)
  const headerId = headers?.get('X-Request-Id') ?? null
  const retryAfter = parseRetryAfter(headers?.get('Retry-After') ?? null)

  if (isErrorResponse(body)) {
    const details = Array.isArray(body.details) ? body.details.filter(esDetalle) : []
    return {
      kind,
      status,
      code: body.code,
      message: body.message,
      requestId: body.requestId || headerId,
      details,
      dependency: kind === 'unavailable' ? dependencyFrom(details, body.message) : null,
      retryAfter,
    }
  }
  return {
    kind,
    status,
    code: `HTTP_${status}`,
    message: MENSAJE_POR_DEFECTO[kind],
    requestId: headerId,
    details: [],
    dependency: null,
    retryAfter,
  }
}

export function networkFailure(causa: unknown): ApiFailure {
  const aborted = causa instanceof DOMException && causa.name === 'AbortError'
  return {
    kind: aborted ? 'aborted' : 'network',
    status: null,
    code: aborted ? 'ABORTED' : 'NETWORK_ERROR',
    message: aborted ? MENSAJE_POR_DEFECTO.aborted : MENSAJE_POR_DEFECTO.network,
    requestId: null,
    details: [],
    dependency: null,
    retryAfter: null,
  }
}

const NOMBRE_FUENTE: Record<string, string> = {
  mongodb: 'MongoDB',
  mongo: 'MongoDB',
  neo4j: 'Neo4j',
  cassandra: 'Cassandra',
  redis: 'Redis',
  influxdb: 'InfluxDB',
  influx: 'InfluxDB',
}

/** "mongodb" → "MongoDB"; un nombre desconocido se devuelve tal cual. */
export function nombreFuente(dep: string): string {
  return NOMBRE_FUENTE[dep.trim().toLowerCase()] ?? dep
}
