import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router'
import { getEquipo, listJugadores, listPartidosDeEquipo } from '../api/endpoints'
import { ETIQUETA_CONDICION, POSICIONES } from '../api/enums'
import type { Equipo, Jugador, Posicion } from '../api/types'
import { EstadoPartidoBadge, SourceBadge } from '../components/Badges'
import { ErrorPanel } from '../components/ErrorPanel'
import { Icon } from '../components/Icon'
import { Panel } from '../components/Panel'
import { EmptyState, Skeleton, Spinner } from '../components/States'
import { useApi } from '../hooks/useApi'
import { useCursorList } from '../hooks/useCursorList'
import { formatFecha, formatFechaHoraUtc } from '../lib/time'

function esColorCss(v: string): boolean {
  return typeof CSS !== 'undefined' && CSS.supports('color', v)
}

function Ficha({ equipo }: { equipo: Equipo }) {
  const colores = [equipo.colores?.principal, equipo.colores?.alternativo].filter(
    (c): c is string => typeof c === 'string' && c !== '',
  )
  return (
    <dl className="kv-grid">
      <div>
        <dt>Confederación</dt>
        <dd>{equipo.confederacion}</dd>
      </div>
      <div>
        <dt>Ranking FIFA</dt>
        <dd className="num">#{equipo.rankingFifa}</dd>
      </div>
      <div>
        <dt>Grupo</dt>
        <dd>{equipo.grupo}</dd>
      </div>
      <div>
        <dt>Entrenador</dt>
        <dd>{equipo.entrenador ?? '—'}</dd>
      </div>
      <div>
        <dt>Sede</dt>
        <dd>{equipo.sede ?? '—'}</dd>
      </div>
      <div>
        <dt>Jugadores</dt>
        <dd className="num">{equipo.cantidadJugadores ?? '—'}</dd>
      </div>
      <div className="kv-wide">
        <dt>Colores</dt>
        <dd>
          {colores.length === 0
            ? '—'
            : colores.map((c) => (
                <span key={c} className="color-chip">
                  {esColorCss(c) ? <span className="swatch" style={{ background: c }} aria-hidden="true" /> : null}
                  {c}
                </span>
              ))}
        </dd>
      </div>
    </dl>
  )
}

function Plantel({ codigo, total }: { codigo: string; total: number | null }) {
  const [posicion, setPosicion] = useState<Posicion | null>(null)
  const fetchPage = useCallback(
    (cursor: string | null, signal: AbortSignal) => listJugadores(codigo, { posicion, limit: 8, cursor }, signal),
    [codigo, posicion],
  )
  const lista = useCursorList<Jugador>(`plantel:${codigo}:${posicion ?? '*'}`, fetchPage, (j) => j.dni)

  return (
    <Panel
      title="Plantel"
      id="plantel"
      badges={<SourceBadge fuente="MongoDB" rol="jugadores" />}
      meta={lista.meta}
      actions={
        <button type="button" className="btn btn-ghost btn-sm" onClick={lista.reload} aria-label="Recargar plantel">
          <Icon name="refresh" size={16} />
        </button>
      }
    >
      <fieldset className="segmented" aria-describedby="plantel-ayuda">
        <legend className="sr-only">Filtrar por posición</legend>
        {[null, ...POSICIONES].map((p) => (
          <label key={p ?? 'todas'} className={posicion === p ? 'seg active' : 'seg'}>
            <input
              type="radio"
              name="posicion"
              value={p ?? ''}
              checked={posicion === p}
              onChange={() => setPosicion(p)}
            />
            {p ?? 'Todas'}
          </label>
        ))}
      </fieldset>
      <p id="plantel-ayuda" className="help">
        Páginas de 8 jugadores ordenadas por dorsal; “Cargar más” usa el <code className="mono">nextCursor</code> de la
        página anterior.
      </p>

      {lista.loading ? (
        <Skeleton lines={5} label="Cargando plantel…" />
      ) : lista.error ? (
        <ErrorPanel error={lista.error} onRetry={lista.reload} recurso={`el equipo ${codigo}`} />
      ) : lista.items.length === 0 ? (
        <EmptyState title="Sin jugadores para este filtro" icon="users">
          El equipo existe, pero no tiene jugadores con la posición elegida.
        </EmptyState>
      ) : (
        <>
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Jugadores de {codigo}</caption>
              <thead>
                <tr>
                  <th scope="col" className="num">
                    Dorsal
                  </th>
                  <th scope="col">Jugador</th>
                  <th scope="col">Posición</th>
                  <th scope="col">Nacimiento</th>
                </tr>
              </thead>
              <tbody>
                {lista.items.map((j) => (
                  <tr key={j.dni}>
                    <td className="num dorsal">{j.dorsal}</td>
                    <td>
                      <strong>{j.apellido}</strong>, {j.nombre}
                    </td>
                    <td>{j.posicion}</td>
                    <td className="num">{formatFecha(j.fechaNacimiento)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="list-foot">
            <span className="muted small" aria-live="polite">
              {lista.items.length}
              {posicion === null && total !== null ? ` de ${total}` : ''} jugadores · {lista.pages}{' '}
              {lista.pages === 1 ? 'página' : 'páginas'}
            </span>
            {lista.hasMore ? (
              <button type="button" className="btn btn-secondary" onClick={lista.loadMore} disabled={lista.loadingMore}>
                {lista.loadingMore ? <Spinner label="Cargando…" /> : 'Cargar más'}
              </button>
            ) : (
              <span className="muted small">No hay más páginas.</span>
            )}
          </div>
          {lista.moreError && <ErrorPanel error={lista.moreError} onRetry={lista.loadMore} compact />}
        </>
      )}
    </Panel>
  )
}

function PartidosDelEquipo({ codigo }: { codigo: string }) {
  const { loading, result, reload } = useApi(`partidos-eq:${codigo}`, (s) => listPartidosDeEquipo(codigo, 20, s))
  return (
    <Panel
      title="Partidos"
      id="partidos-equipo"
      badges={<SourceBadge fuente="Neo4j" rol="PARTICIPA_EN" />}
      meta={result?.meta}
      actions={
        <button type="button" className="btn btn-ghost btn-sm" onClick={reload} aria-label="Recargar partidos">
          <Icon name="refresh" size={16} />
        </button>
      }
    >
      {loading || !result ? (
        <Skeleton lines={4} label="Cargando partidos…" />
      ) : !result.ok ? (
        <ErrorPanel error={result.error} onRetry={reload} recurso={`el equipo ${codigo} en el grafo`} />
      ) : result.data.items.length === 0 ? (
        <EmptyState title="Sin partidos" icon="ball">
          El equipo está en el grafo pero no participa en ningún partido.
        </EmptyState>
      ) : (
        <ul className="match-list">
          {result.data.items.map((p) => {
            const marcador =
              p.golesLocal !== null && p.golesLocal !== undefined && p.golesVisitante !== null && p.golesVisitante !== undefined
                ? `${p.golesLocal} – ${p.golesVisitante}`
                : '– : –'
            return (
              <li key={p.partidoId}>
                <Link to={`/partidos/${encodeURIComponent(p.partidoId)}`} className="match-row">
                  <span className="match-when">
                    <span className="num">{formatFechaHoraUtc(p.fechaHora)}</span>
                    <span className="muted small">
                      {p.fase}
                      {p.grupo ? ` · Grupo ${p.grupo}` : ''}
                    </span>
                  </span>
                  <span className="match-vs">
                    <span className="muted small">{ETIQUETA_CONDICION[p.condicion]} vs</span>
                    <strong className="mono">{p.rivalCodigo}</strong>
                  </span>
                  <span className="match-score num" aria-label={`Marcador ${marcador}`}>
                    {marcador}
                  </span>
                  <EstadoPartidoBadge estado={p.estado} />
                  <code className="mono muted small match-id">{p.partidoId}</code>
                  <Icon name="chevronRight" size={16} className="demo-chevron" />
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </Panel>
  )
}

export function EquipoPage() {
  const { codigo: raw = '' } = useParams()
  const codigo = raw.toUpperCase()
  const ficha = useApi(`equipo:${codigo}`, (s) => getEquipo(codigo, s))
  const equipo = ficha.result?.ok ? ficha.result.data : null

  return (
    <div className="page">
      <nav aria-label="Ruta" className="crumbs">
        <Link to="/">Inicio</Link>
        <Icon name="chevronRight" size={14} />
        <span aria-current="page">Equipo {codigo}</span>
      </nav>

      <header className="page-head">
        <div>
          <p className="eyebrow mono">{codigo}</p>
          <h1>{equipo ? equipo.nombre : `Equipo ${codigo}`}</h1>
        </div>
        <p className="note">
          <Icon name="info" size={16} />
          <span>
            La ficha y el plantel vienen de <strong>MongoDB</strong>; los partidos, del grafo de <strong>Neo4j</strong>.
            La API no cruza ambas bases por código de equipo, así que cada panel puede fallar por separado.
          </span>
        </p>
      </header>

      <div className="grid-2">
        <Panel
          title="Ficha"
          id="ficha"
          badges={<SourceBadge fuente="MongoDB" rol="equipos" />}
          meta={ficha.result?.meta}
          actions={
            <button type="button" className="btn btn-ghost btn-sm" onClick={ficha.reload} aria-label="Recargar ficha">
              <Icon name="refresh" size={16} />
            </button>
          }
        >
          {ficha.loading || !ficha.result ? (
            <Skeleton lines={6} label="Cargando ficha…" />
          ) : !ficha.result.ok ? (
            <ErrorPanel error={ficha.result.error} onRetry={ficha.reload} recurso={`el equipo ${codigo}`} />
          ) : (
            <Ficha equipo={ficha.result.data} />
          )}
        </Panel>
        <PartidosDelEquipo codigo={codigo} />
      </div>

      <Plantel codigo={codigo} total={equipo?.cantidadJugadores ?? null} />
    </div>
  )
}
