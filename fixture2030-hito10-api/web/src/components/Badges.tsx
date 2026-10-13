import type { CacheStatus, PartidoDetalle } from '../api/types'
import { Icon } from './Icon'

export type Fuente = 'MongoDB' | 'Neo4j' | 'Cassandra' | 'Redis' | 'InfluxDB'

const CLASE_FUENTE: Record<Fuente, string> = {
  MongoDB: 'src-mongo',
  Neo4j: 'src-neo4j',
  Cassandra: 'src-cassandra',
  Redis: 'src-redis',
  InfluxDB: 'src-influx',
}

/** Indica de qué base sale el dato del panel. El nombre va en texto; el punto de color es sólo apoyo. */
export function SourceBadge({ fuente, rol }: { fuente: Fuente; rol?: string }) {
  return (
    <span className={`badge badge-source ${CLASE_FUENTE[fuente]}`} title={rol ? `${fuente}: ${rol}` : `Fuente: ${fuente}`}>
      <span className="dot" aria-hidden="true" />
      <span className="sr-only">Fuente: </span>
      {fuente}
      {rol ? <span className="badge-sub">· {rol}</span> : null}
    </span>
  )
}

const TEXTO_CACHE: Record<CacheStatus, string> = {
  HIT: 'Servido desde la caché de Redis',
  MISS: 'Leído de Neo4j y guardado en Redis (60 s)',
  BYPASS: 'Redis no disponible: servido directo desde Neo4j',
}

export function CacheBadge({ cache }: { cache: CacheStatus | null }) {
  if (!cache) {
    return (
      <span className="badge badge-neutral" title="La respuesta no trajo la cabecera X-Cache">
        X-Cache: —
      </span>
    )
  }
  return (
    <span className={`badge badge-cache cache-${cache.toLowerCase()}`} title={TEXTO_CACHE[cache]}>
      <Icon name={cache === 'HIT' ? 'check' : cache === 'MISS' ? 'database' : 'alert'} size={14} />
      X-Cache: <strong>{cache}</strong>
      <span className="sr-only"> — {TEXTO_CACHE[cache]}</span>
    </span>
  )
}

export function EstadoPartidoBadge({ estado }: { estado: PartidoDetalle['estado'] }) {
  return (
    <span className={`badge ${estado === 'FINALIZADO' ? 'badge-done' : 'badge-scheduled'}`}>
      <Icon name={estado === 'FINALIZADO' ? 'flag' : 'clock'} size={14} />
      {estado === 'FINALIZADO' ? 'Finalizado' : 'Programado'}
    </span>
  )
}

export function HttpBadge({ status }: { status: number | null }) {
  if (status === null) return <span className="badge badge-http http-none">sin respuesta</span>
  const clase = status < 300 ? 'http-ok' : status < 500 ? 'http-warn' : 'http-err'
  return (
    <span className={`badge badge-http ${clase}`}>
      <span className="sr-only">HTTP </span>
      {status}
    </span>
  )
}
