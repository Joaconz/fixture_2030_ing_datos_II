import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { getPartido } from '../../api/endpoints'
import { ErrorPanel } from '../../components/ErrorPanel'
import { Icon } from '../../components/Icon'
import { Skeleton } from '../../components/States'
import { useApi } from '../../hooks/useApi'
import { MesaControlPanel } from './MesaControlPanel'

/**
 * Mesa de control (CU6, CU7): vista de operación, fuera de la navegación del
 * hincha. Se llega por URL (/partidos/:id/mesa) y conserva el detalle técnico
 * (status HTTP, Idempotency-Key, X-Request-Id) de la versión anterior del front.
 */
export function MesaPage() {
  const { id: raw = '' } = useParams()
  const partidoId = raw.toUpperCase()
  const detalle = useApi(`partido:${partidoId}`, (s) => getPartido(partidoId, s))
  const [cerradoAqui, setCerradoAqui] = useState(false)
  const res = detalle.result ?? detalle.stale
  const p = res?.ok ? res.data : null

  return (
    <div className="page operacion">
      <nav aria-label="Ruta" className="crumbs">
        <Link to={`/partidos/${encodeURIComponent(partidoId)}`}>
          <Icon name="arrowLeft" size={14} /> Volver al partido
        </Link>
      </nav>
      <header className="page-head">
        <div>
          <p className="eyebrow">Operación · {partidoId}</p>
          <h1>Mesa de control</h1>
        </div>
      </header>
      {!res ? (
        <Skeleton lines={4} label="Cargando partido…" />
      ) : !res.ok ? (
        <ErrorPanel error={res.error} onRetry={detalle.reload} recurso={`el partido ${partidoId}`} />
      ) : p && (p.estado === 'PROGRAMADO' || cerradoAqui) ? (
        <MesaControlPanel
          partido={p}
          onChange={(cambio) => {
            if (cambio === 'cierre') setCerradoAqui(true)
            detalle.reload()
          }}
        />
      ) : (
        <p className="note" role="status">
          <Icon name="info" size={16} />
          <span>La mesa de control sólo está disponible mientras el partido está PROGRAMADO; este partido ya está FINALIZADO.</span>
        </p>
      )}
    </div>
  )
}
