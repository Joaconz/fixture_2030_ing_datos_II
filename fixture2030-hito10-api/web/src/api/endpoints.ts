/**
 * Una función por caso de uso (docs/casos_de_uso.md). Rutas, parámetros y
 * cuerpos los tipa openapi-fetch a partir del contrato.
 */
import { api, run, type ApiResult } from './client'
import type {
  Agregacion,
  ComentarioNuevo,
  EventoNuevo,
  Posicion,
  SaludDependencias,
  TipoEvento,
} from './types'

type Sig = AbortSignal | undefined

// CU1 — ficha del equipo (MongoDB)
export const getEquipo = (codigo: string, signal?: Sig) =>
  run(() => api.GET('/equipos/{codigo}', { params: { path: { codigo } }, signal }))

// CU2 — plantel paginado (MongoDB)
export const listJugadores = (
  codigo: string,
  q: { posicion?: Posicion | null; limit?: number; cursor?: string | null },
  signal?: Sig,
) =>
  run(() =>
    api.GET('/equipos/{codigo}/jugadores', {
      params: {
        path: { codigo },
        query: { posicion: q.posicion ?? undefined, limit: q.limit, cursor: q.cursor ?? undefined },
      },
      signal,
    }),
  )

// CU3 — partidos del equipo (Neo4j)
export const listPartidosDeEquipo = (codigo: string, limit: number, signal?: Sig) =>
  run(() => api.GET('/equipos/{codigo}/partidos', { params: { path: { codigo }, query: { limit } }, signal }))

// CU4 — detalle del partido (Neo4j + caché Redis, cabecera X-Cache)
export const getPartido = (partidoId: string, signal?: Sig) =>
  run(() => api.GET('/partidos/{partido_id}', { params: { path: { partido_id: partidoId } }, signal }))

// CU5 — timeline de eventos (Neo4j)
export const listEventos = (
  partidoId: string,
  q: { tipo?: TipoEvento | null; limit?: number; cursor?: string | null },
  signal?: Sig,
) =>
  run(() =>
    api.GET('/partidos/{partido_id}/eventos', {
      params: {
        path: { partido_id: partidoId },
        query: { tipo: q.tipo ?? undefined, limit: q.limit, cursor: q.cursor ?? undefined },
      },
      signal,
    }),
  )

// CU6 — registrar evento (Neo4j), idempotente por Idempotency-Key
export const registrarEvento = (partidoId: string, idempotencyKey: string, body: EventoNuevo) =>
  run(() =>
    api.POST('/partidos/{partido_id}/eventos', {
      params: { path: { partido_id: partidoId }, header: { 'Idempotency-Key': idempotencyKey } },
      body,
    }),
  )

// CU7 — cerrar partido (Neo4j), no idempotente a propósito
export const cerrarPartido = (partidoId: string) =>
  run(() =>
    api.PATCH('/partidos/{partido_id}/estado', {
      params: { path: { partido_id: partidoId } },
      body: { estado: 'FINALIZADO' },
    }),
  )

// CU8 — comentarios paginados (Cassandra)
export const listComentarios = (partidoId: string, q: { limit?: number; cursor?: string | null }, signal?: Sig) =>
  run(() =>
    api.GET('/partidos/{partido_id}/comentarios', {
      params: { path: { partido_id: partidoId }, query: { limit: q.limit, cursor: q.cursor ?? undefined } },
      signal,
    }),
  )

// CU9 — publicar comentario (Cassandra), idempotente por Idempotency-Key + creadoEn
export const publicarComentario = (partidoId: string, idempotencyKey: string, body: ComentarioNuevo) =>
  run(() =>
    api.POST('/partidos/{partido_id}/comentarios', {
      params: { path: { partido_id: partidoId }, header: { 'Idempotency-Key': idempotencyKey } },
      body,
    }),
  )

// CU10 — validar sesión (Redis)
export const getSesion = (sesionId: string, signal?: Sig) =>
  run(() => api.GET('/sesiones/{sesion_id}', { params: { path: { sesion_id: sesionId } }, signal }))

// CU11 — invalidar sesión (Redis)
export const invalidarSesion = (sesionId: string) =>
  run(() => api.DELETE('/sesiones/{sesion_id}', { params: { path: { sesion_id: sesionId } } }))

// CU12 — estadísticas en una ventana (InfluxDB)
export const getEstadisticas = (
  partidoId: string,
  q: { desde: string; hasta: string; agregacion: Agregacion; equipo?: string | null; limit?: number },
  signal?: Sig,
) =>
  run(() =>
    api.GET('/partidos/{partido_id}/estadisticas', {
      params: {
        path: { partido_id: partidoId },
        query: {
          desde: q.desde,
          hasta: q.hasta,
          agregacion: q.agregacion,
          equipo: q.equipo ?? undefined,
          limit: q.limit,
        },
      },
      signal,
    }),
  )

// Salud: la API está viva
export const getHealth = (signal?: Sig) => run(() => api.GET('/health', { signal }))

export function isSaludDependencias(body: unknown): body is SaludDependencias {
  if (typeof body !== 'object' || body === null) return false
  const b = body as Record<string, unknown>
  return typeof b.estado === 'string' && Array.isArray(b.dependencias)
}

// CU13 — conectividad de las fuentes: el 503 trae el mismo cuerpo que el 200
export const getSaludDependencias = (signal?: Sig): Promise<ApiResult<SaludDependencias>> =>
  run(() => api.GET('/health/dependencias', { signal }), {
    acceptError: (status, body) => (status === 503 && isSaludDependencias(body) ? body : null),
  })
