import { useCallback, useState } from 'react'
import { listEventos } from '../../api/endpoints'
import { ETIQUETA_CONDICION, ETIQUETA_TIPO, TIPOS_EVENTO } from '../../api/enums'
import type { Evento, PartidoDetalle, TipoEvento } from '../../api/types'
import { SourceBadge } from '../../components/Badges'
import { ErrorPanel } from '../../components/ErrorPanel'
import { Icon } from '../../components/Icon'
import { Panel } from '../../components/Panel'
import { EmptyState, Skeleton, Spinner } from '../../components/States'
import { useCursorList } from '../../hooks/useCursorList'

const CLASE_TIPO: Partial<Record<TipoEvento, string>> = {
  GOL: 'ev-gol',
  TARJETA_AMARILLA: 'ev-amarilla',
  TARJETA_ROJA: 'ev-roja',
  INICIO_PARTIDO: 'ev-marco',
  FIN_PARTIDO: 'ev-marco',
  PENAL: 'ev-penal',
}

function equipoDe(ev: Evento, p: PartidoDetalle): string | null {
  if (ev.condicionEquipo === 'LOCAL') return p.local.equipoCodigo
  if (ev.condicionEquipo === 'VISITANTE') return p.visitante.equipoCodigo
  return null
}

export function EventosPanel({ partido, version }: { partido: PartidoDetalle; version: number }) {
  const [tipo, setTipo] = useState<TipoEvento | null>(null)
  const id = partido.partidoId
  const fetchPage = useCallback(
    (cursor: string | null, signal: AbortSignal) => listEventos(id, { tipo, limit: 25, cursor }, signal),
    [id, tipo],
  )
  const lista = useCursorList<Evento>(`eventos:${id}:${tipo ?? '*'}:${version}`, fetchPage, (e) => e.eventoId)

  return (
    <Panel
      title="Timeline de eventos"
      level={2}
      id="eventos"
      badges={<SourceBadge fuente="Neo4j" rol="OCURRE_EN, por secuencia" />}
      meta={lista.meta}
      actions={
        <button type="button" className="btn btn-ghost btn-sm" onClick={lista.reload} aria-label="Recargar eventos">
          <Icon name="refresh" size={16} />
        </button>
      }
    >
      <div className="filters">
        <div className="field">
          <label htmlFor="filtro-tipo">Tipo de evento</label>
          <select
            id="filtro-tipo"
            value={tipo ?? ''}
            onChange={(e) => {
              const v = e.target.value
              setTipo(TIPOS_EVENTO.find((t) => t === v) ?? null)
            }}
          >
            <option value="">Todos</option>
            {TIPOS_EVENTO.map((t) => (
              <option key={t} value={t}>
                {ETIQUETA_TIPO[t]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {lista.loading ? (
        <Skeleton lines={6} label="Cargando eventos…" />
      ) : lista.error ? (
        <ErrorPanel error={lista.error} onRetry={lista.reload} recurso={`el partido ${id}`} />
      ) : lista.items.length === 0 ? (
        tipo === null ? (
          <EmptyState title="Este partido todavía no tiene eventos" icon="list">
            El partido existe (la API respondió 200 con <code className="mono">items: []</code>); no es lo mismo que un
            404.
          </EmptyState>
        ) : (
          <EmptyState title={`Sin eventos de tipo “${ETIQUETA_TIPO[tipo]}”`} icon="list" />
        )
      ) : (
        <>
          <ol className="timeline">
            {lista.items.map((ev) => {
              const eq = equipoDe(ev, partido)
              return (
                <li key={ev.eventoId} className={`tl-item ${CLASE_TIPO[ev.tipo] ?? ''}`}>
                  <span className="tl-min num" aria-label={`Minuto ${ev.minuto}`}>
                    {ev.minuto}′
                  </span>
                  <span className="tl-dot" aria-hidden="true" />
                  <div className="tl-body">
                    <p className="tl-title">
                      <strong>{ETIQUETA_TIPO[ev.tipo]}</strong>
                      {eq && ev.condicionEquipo ? (
                        <span className={`chip cond-${ev.condicionEquipo.toLowerCase()}`}>
                          {eq} · {ETIQUETA_CONDICION[ev.condicionEquipo]}
                        </span>
                      ) : null}
                      {ev.origen === 'API' ? <span className="chip chip-api">alta por API</span> : null}
                    </p>
                    <p className="tl-sub muted small">
                      {ev.protagonista ? (
                        <>
                          {ev.protagonista.nombre} {ev.protagonista.apellido}
                          {ev.dorsalProtagonista ? ` (#${ev.dorsalProtagonista})` : ''}
                        </>
                      ) : ev.dorsalProtagonista ? (
                        `Dorsal #${ev.dorsalProtagonista}`
                      ) : (
                        'Sin protagonista'
                      )}
                      <span aria-hidden="true"> · </span>
                      <span className="mono">sec. {ev.secuencia}</span>
                    </p>
                  </div>
                </li>
              )
            })}
          </ol>
          <div className="list-foot">
            <span className="muted small" aria-live="polite">
              {lista.items.length} eventos · {lista.pages} {lista.pages === 1 ? 'página' : 'páginas'}
            </span>
            {lista.hasMore ? (
              <button type="button" className="btn btn-secondary" onClick={lista.loadMore} disabled={lista.loadingMore}>
                {lista.loadingMore ? <Spinner label="Cargando…" /> : 'Cargar más'}
              </button>
            ) : (
              <span className="muted small">Fin del timeline.</span>
            )}
          </div>
          {lista.moreError && <ErrorPanel error={lista.moreError} onRetry={lista.loadMore} compact />}
        </>
      )}
    </Panel>
  )
}
