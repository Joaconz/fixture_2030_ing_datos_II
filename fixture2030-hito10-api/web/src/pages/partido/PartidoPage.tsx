import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { getPartido } from '../../api/endpoints'
import type { PartidoDetalle } from '../../api/types'
import { CacheBadge, EstadoPartidoBadge, SourceBadge } from '../../components/Badges'
import { ErrorPanel } from '../../components/ErrorPanel'
import { Icon } from '../../components/Icon'
import { MetaFooter } from '../../components/Panel'
import { Skeleton, Spinner } from '../../components/States'
import { TabPanel, Tabs, type TabDef } from '../../components/Tabs'
import { useApi } from '../../hooks/useApi'
import { formatFechaHoraUtc } from '../../lib/time'
import { ComentariosPanel } from './ComentariosPanel'
import { EstadisticasPanel } from './EstadisticasPanel'
import { EventosPanel } from './EventosPanel'
import { MesaControlPanel, type CambioMesa } from './MesaControlPanel'

type TabKey = 'eventos' | 'comentarios' | 'estadisticas' | 'mesa'

const TABS_BASE: TabDef<TabKey>[] = [
  { key: 'eventos', label: 'Eventos', icon: 'list' },
  { key: 'comentarios', label: 'Comentarios', icon: 'message' },
  { key: 'estadisticas', label: 'Estadísticas', icon: 'chart' },
]
const TAB_MESA: TabDef<TabKey> = { key: 'mesa', label: 'Mesa de control', icon: 'flag' }

function esTab(v: string | null): v is TabKey {
  return v === 'eventos' || v === 'comentarios' || v === 'estadisticas' || v === 'mesa'
}

function Marcador({ p }: { p: PartidoDetalle }) {
  const m = p.marcador
  const texto = m ? `${p.local.nombre} ${m.golesLocal}, ${p.visitante.nombre} ${m.golesVisitante}` : 'Sin marcador hasta el cierre'
  return (
    <div className="scoreboard" aria-label={texto}>
      <Link to={`/equipos/${encodeURIComponent(p.local.equipoCodigo)}`} className="team team-local">
        <span className="team-code mono">{p.local.equipoCodigo}</span>
        <span className="team-name">{p.local.nombre}</span>
        <span className="team-role">Local</span>
      </Link>
      <div className="score" aria-hidden="true">
        {m ? (
          <>
            <span className="num">{m.golesLocal}</span>
            <span className="score-sep">–</span>
            <span className="num">{m.golesVisitante}</span>
          </>
        ) : (
          <span className="score-pending">vs</span>
        )}
      </div>
      <Link to={`/equipos/${encodeURIComponent(p.visitante.equipoCodigo)}`} className="team team-visit">
        <span className="team-code mono">{p.visitante.equipoCodigo}</span>
        <span className="team-name">{p.visitante.nombre}</span>
        <span className="team-role">Visitante</span>
      </Link>
    </div>
  )
}

export function PartidoPage() {
  const { id: raw = '' } = useParams()
  const partidoId = raw.toUpperCase()
  const [params, setParams] = useSearchParams()
  const [version, setVersion] = useState(0)
  // Si el partido se cerró desde esta vista, la mesa sigue visible para ver el 200 y probar el 409.
  const [cerradoAqui, setCerradoAqui] = useState(false)

  const detalle = useApi(`partido:${partidoId}`, (s) => getPartido(partidoId, s))
  // Durante una recarga se sigue mostrando el último detalle (no se desmontan las pestañas).
  const res = detalle.result ?? detalle.stale
  const p = res?.ok ? res.data : null

  const tabs = p?.estado === 'PROGRAMADO' || cerradoAqui ? [...TABS_BASE, TAB_MESA] : TABS_BASE
  const pedido = params.get('tab')
  const tab: TabKey = esTab(pedido) && tabs.some((t) => t.key === pedido) ? pedido : 'eventos'

  function cambiarTab(k: TabKey) {
    const next = new URLSearchParams(params)
    next.set('tab', k)
    setParams(next, { replace: true })
  }

  /** Tras escribir (evento o cierre): se vuelve a pedir el detalle y la lista de eventos. */
  function alEscribir(cambio: CambioMesa) {
    if (cambio === 'cierre') setCerradoAqui(true)
    detalle.reload()
    setVersion((v) => v + 1)
  }

  return (
    <div className="page">
      <nav aria-label="Ruta" className="crumbs">
        <Link to="/">Inicio</Link>
        <Icon name="chevronRight" size={14} />
        <span aria-current="page">Partido {partidoId}</span>
      </nav>

      <section className="panel match-hero" aria-labelledby="partido-titulo">
        <header className="panel-head">
          <div className="panel-title">
            <p className="eyebrow mono">{partidoId}</p>
            <h1 id="partido-titulo">
              {p ? `${p.local.nombre} vs ${p.visitante.nombre}` : `Partido ${partidoId}`}
            </h1>
            <div className="badge-row">
              <SourceBadge fuente="Neo4j" rol="partido" />
              <SourceBadge fuente="Redis" rol="caché 60 s" />
              {res?.ok ? <CacheBadge cache={res.meta.cache} /> : null}
              {p ? <EstadoPartidoBadge estado={p.estado} /> : null}
            </div>
          </div>
          <div className="panel-actions">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={detalle.reload}
              disabled={detalle.loading}
              title="Un segundo pedido dentro de 60 s debería responder X-Cache: HIT"
            >
              {detalle.loading ? <Spinner /> : <Icon name="refresh" size={16} />}
              Volver a pedir
            </button>
          </div>
        </header>
        <div className="panel-body">
          {!res ? (
            <Skeleton lines={4} label="Cargando partido…" />
          ) : !res.ok ? (
            <ErrorPanel error={res.error} onRetry={detalle.reload} recurso={`el partido ${partidoId}`} />
          ) : (
            p && (
              <>
                <Marcador p={p} />
                <dl className="kv-grid kv-compact">
                  <div>
                    <dt>Fecha y hora</dt>
                    <dd className="num">{formatFechaHoraUtc(p.fechaHora)}</dd>
                  </div>
                  <div>
                    <dt>Fase</dt>
                    <dd>
                      {p.fase}
                      {p.grupo ? ` · Grupo ${p.grupo}` : ''}
                      {p.jornada ? ` · Jornada ${p.jornada}` : ''}
                    </dd>
                  </div>
                  <div>
                    <dt>Sede</dt>
                    <dd>
                      {p.sede ? (
                        <>
                          {p.sede.nombre}
                          <span className="muted small block">
                            <Icon name="mapPin" size={12} /> {p.sede.ciudad}, {p.sede.pais}
                          </span>
                        </>
                      ) : (
                        '—'
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Eventos registrados</dt>
                    <dd className="num">{p.cantidadEventos}</dd>
                  </div>
                </dl>
                {p.marcador === null || p.marcador === undefined ? (
                  <p className="help">El marcador se deriva de los eventos GOL y se publica al cerrar el partido.</p>
                ) : null}
              </>
            )
          )}
        </div>
        {res?.meta ? <MetaFooter meta={res.meta} /> : null}
      </section>

      {p && (
        <div className="stack">
          {pedido === 'mesa' && tab !== 'mesa' && (
            <p className="note" role="status">
              <Icon name="info" size={16} />
              <span>
                La mesa de control sólo está disponible mientras el partido está PROGRAMADO; este partido ya está{' '}
                {p.estado}.
              </span>
            </p>
          )}
          <Tabs tabs={tabs} value={tab} onChange={cambiarTab} label="Secciones del partido" idPrefix="partido" />
          <TabPanel idPrefix="partido" tabKey={tab}>
            {tab === 'eventos' && <EventosPanel partido={p} version={version} />}
            {tab === 'comentarios' && <ComentariosPanel partido={p} />}
            {tab === 'estadisticas' && <EstadisticasPanel partido={p} />}
            {tab === 'mesa' && <MesaControlPanel partido={p} onChange={alEscribir} />}
          </TabPanel>
        </div>
      )}
    </div>
  )
}
