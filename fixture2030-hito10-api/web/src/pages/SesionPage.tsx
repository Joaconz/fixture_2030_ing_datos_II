import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import type { ApiResult } from '../api/client'
import { getSesion, invalidarSesion } from '../api/endpoints'
import type { Sesion } from '../api/types'
import { HttpBadge, SourceBadge } from '../components/Badges'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorPanel } from '../components/ErrorPanel'
import { Icon } from '../components/Icon'
import { Panel } from '../components/Panel'
import { RequestId } from '../components/RequestId'
import { Skeleton, Spinner } from '../components/States'
import { useApi } from '../hooks/useApi'
import { formatDuracion, formatFechaHoraUtc } from '../lib/time'

/** TTL que corre en pantalla a partir del valor leído (la consulta no lo renueva). */
function TtlRestante({ ttl, leidoEn }: { ttl: number; leidoEn: number }) {
  const [ahora, setAhora] = useState(leidoEn)
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  if (ttl < 0) return <span>{ttl === -1 ? 'sin vencimiento' : '—'}</span>
  const restante = Math.max(0, ttl - Math.floor((ahora - leidoEn) / 1000))
  return (
    <span>
      <strong className="num ttl">{formatDuracion(restante)}</strong>
      <span className="muted small block">
        {ttl} s al consultar · cuenta regresiva local
      </span>
    </span>
  )
}

function Datos({ s, leidoEn }: { s: Sesion; leidoEn: number }) {
  return (
    <dl className="kv-grid">
      <div>
        <dt>usuarioId</dt>
        <dd className="mono">{s.usuarioId}</dd>
      </div>
      <div>
        <dt>Rol</dt>
        <dd>{s.rol}</dd>
      </div>
      <div>
        <dt>Estado</dt>
        <dd>
          <span className="badge badge-done">
            <Icon name="check" size={14} />
            {s.estado}
          </span>
        </dd>
      </div>
      <div>
        <dt>Región</dt>
        <dd>{s.region}</dd>
      </div>
      <div>
        <dt>Dispositivo</dt>
        <dd>{s.dispositivo}</dd>
      </div>
      <div>
        <dt>TTL restante</dt>
        <dd>
          <TtlRestante ttl={s.ttlSegundos} leidoEn={leidoEn} />
        </dd>
      </div>
      <div>
        <dt>Creada</dt>
        <dd className="num">{formatFechaHoraUtc(s.creadaEn)}</dd>
      </div>
      <div>
        <dt>Última actividad</dt>
        <dd className="num">{formatFechaHoraUtc(s.ultimaActividad)}</dd>
      </div>
      <div>
        <dt>Vence (absoluto)</dt>
        <dd className="num">{formatFechaHoraUtc(s.expiraAbsoluta)}</dd>
      </div>
    </dl>
  )
}

export function SesionPage() {
  const { id = '' } = useParams()
  const consulta = useApi(`sesion:${id}`, async (signal) => {
    const r = await getSesion(id, signal)
    return r.ok ? { ...r, data: { sesion: r.data, leidoEn: Date.now() } } : r
  })
  const [confirmar, setConfirmar] = useState(false)
  const [borrando, setBorrando] = useState(false)
  const [borrado, setBorrado] = useState<ApiResult<undefined> | null>(null)

  async function invalidar() {
    setConfirmar(false)
    setBorrando(true)
    try {
      const r = await invalidarSesion(id)
      setBorrado(r)
      consulta.reload()
    } finally {
      setBorrando(false)
    }
  }

  const res = consulta.result ?? consulta.stale

  return (
    <div className="page">
      <nav aria-label="Ruta" className="crumbs">
        <Link to="/">Inicio</Link>
        <Icon name="chevronRight" size={14} />
        <span aria-current="page">Sesión</span>
      </nav>
      <header className="page-head">
        <div>
          <p className="eyebrow">Moderación y soporte</p>
          <h1>
            Sesión <span className="mono break">{id}</span>
          </h1>
        </div>
        <p className="note">
          <Icon name="info" size={16} />
          <span>
            Consultar no renueva el TTL. Una sesión vencida y una inexistente responden igual (404); una bloqueada,
            403.
          </span>
        </p>
      </header>

      <div className="grid-2 grid-form">
        <Panel
          title="Datos de la sesión"
          id="sesion"
          badges={<SourceBadge fuente="Redis" rol="HGETALL + TTL" />}
          meta={res?.meta}
          actions={
            <button type="button" className="btn btn-secondary btn-sm" onClick={consulta.reload} disabled={consulta.loading}>
              {consulta.loading ? <Spinner /> : <Icon name="refresh" size={16} />}
              Volver a consultar
            </button>
          }
        >
          {!res ? (
            <Skeleton lines={6} label="Consultando sesión…" />
          ) : !res.ok ? (
            <ErrorPanel error={res.error} onRetry={consulta.reload} recurso="una sesión vigente con ese id" />
          ) : (
            <Datos s={res.data.sesion} leidoEn={res.data.leidoEn} />
          )}
        </Panel>

        <Panel title="Invalidar sesión" id="invalidar" badges={<SourceBadge fuente="Redis" rol="MULTI/EXEC" />}>
          <p>
            Borra la sesión y la quita del índice del usuario en una transacción. El efecto es idempotente; repetirlo
            responde 404.
          </p>
          <div className="form-actions">
            <button type="button" className="btn btn-danger" onClick={() => setConfirmar(true)} disabled={borrando}>
              {borrando ? <Spinner /> : <Icon name="trash" size={16} />}
              Invalidar sesión
            </button>
          </div>
          {borrado && (
            <div className="result" aria-live="polite">
              {borrado.ok ? (
                <div className="result-ok">
                  <p className="result-title">
                    <HttpBadge status={borrado.meta.status} />
                    Sesión invalidada
                  </p>
                  <p className="small muted">La consulta de la izquierda ahora debería responder 404.</p>
                  <RequestId id={borrado.meta.requestId} />
                </div>
              ) : (
                <ErrorPanel error={borrado.error} compact recurso="una sesión vigente con ese id" />
              )}
            </div>
          )}
        </Panel>
      </div>

      <ConfirmDialog
        open={confirmar}
        title="¿Invalidar la sesión?"
        confirmLabel="Sí, invalidar"
        destructive
        onConfirm={() => void invalidar()}
        onCancel={() => setConfirmar(false)}
      >
        <p>
          La sesión <code className="mono">{id}</code> dejará de ser válida y el usuario tendrá que volver a iniciar
          sesión.
        </p>
      </ConfirmDialog>
    </div>
  )
}
