import { Link, Navigate, useParams, useSearchParams } from 'react-router'
import { getPartido } from '../../api/endpoints'
import type { PartidoDetalle } from '../../api/types'
import { Cargando, EstadoError } from '../../components/Estados'
import { CodigoEquipo, EstadoPill } from '../../components/Fixture'
import { Icon } from '../../components/Icon'
import { TabPanel, Tabs, type TabDef } from '../../components/Tabs'
import { useApi } from '../../hooks/useApi'
import { descripcionFase, marcadorDeDetalle } from '../../lib/partido'
import { formatFechaHoraUtc, formatHoraUtc } from '../../lib/time'
import { AlineacionesTab } from './AlineacionesTab'
import { EstadisticasTab } from './EstadisticasTab'
import { EventosComentariosTab } from './EventosComentariosTab'

type TabKey = 'eventos' | 'estadisticas' | 'alineaciones'

/** Las tres pestañas del detalle (stitch/DESIGN.md §5); ninguna otra. */
const TABS: TabDef<TabKey>[] = [
  { key: 'eventos', label: 'Eventos y comentarios', icon: 'list' },
  { key: 'estadisticas', label: 'Estadísticas', icon: 'chart' },
  { key: 'alineaciones', label: 'Alineaciones', icon: 'shirt' },
]

function esTab(v: string | null): v is TabKey {
  return v === 'eventos' || v === 'estadisticas' || v === 'alineaciones'
}

function Marcador({ p }: { p: PartidoDetalle }) {
  const m = marcadorDeDetalle(p)
  const resumen = m
    ? `${p.local.nombre} ${m.local}, ${p.visitante.nombre} ${m.visitante}`
    : `${p.local.nombre} contra ${p.visitante.nombre}, sin marcador publicado`
  return (
    <div className="marcador" aria-label={resumen}>
      <Link to={`/equipos/${encodeURIComponent(p.local.equipoCodigo)}`} className="marcador-equipo marcador-local">
        <span className="marcador-nombre-wrap">
          <span className="marcador-nombre">{p.local.nombre}</span>
          <span className="marcador-rol">Local{p.grupo ? ` · Grupo ${p.grupo}` : ''}</span>
        </span>
        <CodigoEquipo codigo={p.local.equipoCodigo} />
      </Link>
      <div className="marcador-centro" aria-hidden="true">
        <EstadoPill estado={p.estado} />
        {m ? (
          <span className="marcador-goles num">
            {m.local}
            <span className="marcador-sep">–</span>
            {m.visitante}
          </span>
        ) : (
          <span className="marcador-goles marcador-vs">vs</span>
        )}
        <span className="marcador-nota">
          {m ? 'Resultado final' : p.estado === 'PROGRAMADO' ? `${formatHoraUtc(p.fechaHora)} UTC` : 'Marcador sin publicar'}
        </span>
      </div>
      <Link to={`/equipos/${encodeURIComponent(p.visitante.equipoCodigo)}`} className="marcador-equipo marcador-visitante">
        <CodigoEquipo codigo={p.visitante.equipoCodigo} />
        <span className="marcador-nombre-wrap">
          <span className="marcador-nombre">{p.visitante.nombre}</span>
          <span className="marcador-rol">Visitante{p.grupo ? ` · Grupo ${p.grupo}` : ''}</span>
        </span>
      </Link>
    </div>
  )
}

export function PartidoPage() {
  const { id: raw = '' } = useParams()
  const partidoId = raw.toUpperCase()
  const [params, setParams] = useSearchParams()

  const detalle = useApi(`partido:${partidoId}`, (s) => getPartido(partidoId, s))
  const res = detalle.result ?? detalle.stale
  const p = res?.ok ? res.data : null

  const pedido = params.get('tab')
  // La mesa de control vive en su propia ruta (operación, no es parte de la UX del hincha).
  if (pedido === 'mesa') return <Navigate to={`/partidos/${encodeURIComponent(partidoId)}/mesa`} replace />
  const tab: TabKey = esTab(pedido) ? pedido : 'eventos'

  function cambiarTab(k: TabKey) {
    const next = new URLSearchParams(params)
    next.set('tab', k)
    setParams(next, { replace: true })
  }

  if (!res) {
    return (
      <div className="page">
        <section className="partido-cabecera" aria-label={`Partido ${partidoId}`}>
          <h1 className="sr-only">Partido {partidoId}</h1>
          <div className="marcador marcador-cargando">
            <Cargando lineas={3} etiqueta="Cargando el partido…" />
          </div>
        </section>
      </div>
    )
  }

  if (!res.ok || !p) {
    return (
      <div className="page">
        <section className="card card-pad" aria-labelledby="partido-titulo">
          <h1 id="partido-titulo" className="titulo-seccion">
            Partido {partidoId}
          </h1>
          {!res.ok && (
            <EstadoError
              error={res.error}
              onRetry={detalle.reload}
              recurso="ese partido"
              que="el partido"
              accion={
                <Link to="/" className="btn btn-secondary btn-sm">
                  <Icon name="arrowLeft" size={16} />
                  Volver al inicio
                </Link>
              }
            />
          )}
        </section>
      </div>
    )
  }

  return (
    <div className="page">
      <section className="partido-cabecera" aria-labelledby="partido-titulo">
        <h1 id="partido-titulo" className="sr-only">
          {p.local.nombre} contra {p.visitante.nombre}
        </h1>
        <ul className="partido-meta" aria-label="Datos del partido">
          {p.sede ? (
            <li>
              <Icon name="mapPin" size={16} />
              {p.sede.nombre}, {p.sede.ciudad}
            </li>
          ) : null}
          <li>
            <Icon name="calendar" size={16} />
            <span className="num">{formatFechaHoraUtc(p.fechaHora)}</span>
          </li>
          <li className="partido-meta-fase">{descripcionFase(p)}</li>
        </ul>
        <Marcador p={p} />
        <Tabs tabs={TABS} value={tab} onChange={cambiarTab} label="Secciones del partido" idPrefix="partido" />
      </section>

      <TabPanel idPrefix="partido" tabKey={tab}>
        {tab === 'eventos' && <EventosComentariosTab partido={p} />}
        {tab === 'estadisticas' && <EstadisticasTab partido={p} />}
        {tab === 'alineaciones' && <AlineacionesTab partido={p} />}
      </TabPanel>
    </div>
  )
}
