import { API_URL } from '../config'
import { nombreFuente, type ApiFailure, type ErrorKind } from '../api/errors'
import { HttpBadge } from './Badges'
import { Icon, type IconName } from './Icon'
import { RequestId } from './RequestId'

interface Presentacion {
  titulo: string
  icono: IconName
  tono: 'info' | 'warn' | 'conflict' | 'danger'
}

const PRESENTACION: Record<Exclude<ErrorKind, 'aborted'>, Presentacion> = {
  not_found: { titulo: 'No existe', icono: 'searchX', tono: 'info' },
  validation: { titulo: 'Entrada inválida', icono: 'alert', tono: 'warn' },
  conflict: { titulo: 'Conflicto de estado', icono: 'gitMerge', tono: 'conflict' },
  forbidden: { titulo: 'Acceso denegado', icono: 'lock', tono: 'danger' },
  unavailable: { titulo: 'Fuente no disponible', icono: 'serverOff', tono: 'danger' },
  server: { titulo: 'Error interno de la API', icono: 'alert', tono: 'danger' },
  network: { titulo: 'Sin conexión con la API', icono: 'plugOff', tono: 'danger' },
  unexpected: { titulo: 'Respuesta inesperada', icono: 'info', tono: 'warn' },
}

interface ErrorPanelProps {
  error: ApiFailure
  /** Reintentar la misma request (se ofrece en 503, red y 5xx). */
  onRetry?: (() => void) | undefined
  /** Contexto corto: "el equipo ARG", "los comentarios"… */
  recurso?: string
  compact?: boolean
}

/** Componente común de error: code, message y requestId (copiable), con un tratamiento por clase. */
export function ErrorPanel({ error, onRetry, recurso, compact = false }: ErrorPanelProps) {
  if (error.kind === 'aborted') return null
  const p = PRESENTACION[error.kind]
  const fuente = error.dependency ? nombreFuente(error.dependency) : null
  const reintentable = error.kind === 'unavailable' || error.kind === 'network' || error.kind === 'server'
  const detallesDeCampo = error.kind === 'unavailable' ? [] : error.details

  let titulo = p.titulo
  if (error.kind === 'unavailable' && fuente) titulo = `La fuente ${fuente} no está disponible`
  else if (error.kind === 'not_found' && recurso) titulo = `No existe ${recurso}`

  return (
    <div className={`error-panel tone-${p.tono}${compact ? ' compact' : ''}`} role="alert">
      <div className="error-head">
        <Icon name={p.icono} size={compact ? 18 : 22} />
        <div className="error-title">
          <strong>{titulo}</strong>
          <span className="error-codes">
            <HttpBadge status={error.status} />
            <code className="mono error-code">{error.code}</code>
          </span>
        </div>
      </div>

      <p className="error-message">{error.message}</p>

      {detallesDeCampo.length > 0 && (
        <div className="error-details">
          <p className="error-details-title">Detalle por campo</p>
          <ul>
            {detallesDeCampo.map((d, i) => (
              <li key={`${d.campo}-${i}`}>
                <code className="mono">{d.campo}</code>
                <span>{d.problema}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error.kind === 'unavailable' && (
        <p className="error-hint">
          La API respondió, pero {fuente ? `${fuente} no` : 'una de sus fuentes no'} contestó a tiempo. No es un
          “no existe”: el dato puede estar, sólo que no se pudo leer.
          {error.retryAfter !== null ? ` La API sugiere reintentar en ${error.retryAfter} s.` : ''}
        </p>
      )}

      {error.kind === 'network' && (
        <div className="error-hint">
          <p>
            No hubo respuesta HTTP de <code className="mono">{API_URL}</code>. Causas habituales:
          </p>
          <ul>
            <li>la API no está levantada en la notebook;</li>
            <li>el origen de este front no está en <code className="mono">CORS_ORIGINS</code> de la API;</li>
            <li>el navegador bloqueó el acceso a la red local (Chrome pide permiso; Safari/Firefox pueden bloquear contenido mixto).</li>
          </ul>
        </div>
      )}

      <div className="error-foot">
        <RequestId id={error.requestId} prefix="requestId" />
        {onRetry && reintentable && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
            <Icon name="refresh" size={16} />
            Reintentar
          </button>
        )}
      </div>
    </div>
  )
}
