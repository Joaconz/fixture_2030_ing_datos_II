import { getHealth, getSaludDependencias } from '../api/endpoints'
import { DEPENDENCIAS } from '../api/enums'
import type { EstadoDependencia, NombreDependencia } from '../api/types'
import { HttpBadge, SourceBadge, type Fuente } from '../components/Badges'
import { ErrorPanel } from '../components/ErrorPanel'
import { Icon } from '../components/Icon'
import { Panel } from '../components/Panel'
import { Skeleton, Spinner } from '../components/States'
import { useApi } from '../hooks/useApi'

const FUENTE: Record<NombreDependencia, Fuente> = {
  mongodb: 'MongoDB',
  neo4j: 'Neo4j',
  cassandra: 'Cassandra',
  redis: 'Redis',
  influxdb: 'InfluxDB',
}

const MODULO: Record<NombreDependencia, string> = {
  mongodb: 'Equipos y jugadores',
  neo4j: 'Partidos, eventos y tipos',
  cassandra: 'Comentarios',
  redis: 'Sesiones y caché',
  influxdb: 'Estadísticas en vivo',
}

function ordenar(deps: EstadoDependencia[]): EstadoDependencia[] {
  return [...deps].sort((a, b) => DEPENDENCIAS.indexOf(a.nombre) - DEPENDENCIAS.indexOf(b.nombre))
}

export function SaludPage() {
  const vida = useApi('health', (s) => getHealth(s))
  const deps = useApi('health-deps', (s) => getSaludDependencias(s))
  const res = deps.result ?? deps.stale
  const recargar = () => {
    vida.reload()
    deps.reload()
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Operación</p>
          <h1>Salud de las fuentes</h1>
        </div>
        <button type="button" className="btn btn-secondary" onClick={recargar} disabled={deps.loading}>
          {deps.loading ? <Spinner /> : <Icon name="refresh" size={16} />}
          Volver a medir
        </button>
      </header>

      <div className="grid-2 grid-health">
        <Panel title="API" id="api-vida" meta={vida.result?.meta}>
          {vida.loading || !vida.result ? (
            <Skeleton lines={1} label="Consultando /health…" />
          ) : vida.result.ok ? (
            <p className="health-big ok">
              <Icon name="check" size={22} />
              En línea
            </p>
          ) : (
            <ErrorPanel error={vida.result.error} onRetry={vida.reload} compact />
          )}
          <p className="help">
            <code className="mono">GET /health</code>: la API responde; no consulta ninguna fuente.
          </p>
        </Panel>
        <Panel title="Estado general" id="estado-general">
          {!res ? (
            <Skeleton lines={1} label="Midiendo dependencias…" />
          ) : res.ok ? (
            <>
              <p className={`health-big ${res.data.estado === 'OK' ? 'ok' : 'down'}`}>
                <Icon name={res.data.estado === 'OK' ? 'check' : 'alert'} size={22} />
                {res.data.estado === 'OK' ? 'Todas las fuentes responden' : 'Degradado'}
                <HttpBadge status={res.meta.status} />
              </p>
              <p className="help">
                <code className="mono">GET /health/dependencias</code> responde 200 si las cinco están UP y 503 (con este
                mismo detalle) si alguna está DOWN.
              </p>
            </>
          ) : (
            <ErrorPanel error={res.error} onRetry={deps.reload} compact />
          )}
        </Panel>
      </div>

      <Panel title="Dependencias" id="dependencias" meta={res?.meta}>
        {!res ? (
          <Skeleton lines={5} label="Midiendo dependencias…" />
        ) : !res.ok ? (
          <ErrorPanel error={res.error} onRetry={deps.reload} />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Estado y latencia de cada fuente de datos</caption>
              <thead>
                <tr>
                  <th scope="col">Fuente</th>
                  <th scope="col">Módulo</th>
                  <th scope="col">Estado</th>
                  <th scope="col" className="num">
                    Latencia
                  </th>
                  <th scope="col">Detalle</th>
                </tr>
              </thead>
              <tbody>
                {ordenar(res.data.dependencias).map((d) => (
                  <tr key={d.nombre} className={d.estado === 'UP' ? '' : 'row-down'}>
                    <th scope="row">
                      <SourceBadge fuente={FUENTE[d.nombre]} />
                    </th>
                    <td>{MODULO[d.nombre]}</td>
                    <td>
                      <span className={`status ${d.estado === 'UP' ? 'status-up' : 'status-down'}`}>
                        <Icon name={d.estado === 'UP' ? 'check' : 'x'} size={14} />
                        {d.estado}
                      </span>
                    </td>
                    <td className="num">
                      {d.latenciaMs === null || d.latenciaMs === undefined ? '—' : `${d.latenciaMs.toFixed(1)} ms`}
                    </td>
                    <td className="muted small">{d.detalle ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}
