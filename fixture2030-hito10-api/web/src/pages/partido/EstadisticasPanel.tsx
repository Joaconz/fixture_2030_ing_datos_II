import { useMemo, useState, type FormEvent } from 'react'
import { getEstadisticas } from '../../api/endpoints'
import { AGREGACIONES, ETIQUETA_AGREGACION } from '../../api/enums'
import type { Agregacion, EstadisticasPartido, PartidoDetalle } from '../../api/types'
import { SourceBadge } from '../../components/Badges'
import { ErrorPanel } from '../../components/ErrorPanel'
import { Icon } from '../../components/Icon'
import { LineChart } from '../../components/LineChart'
import { Panel } from '../../components/Panel'
import { EmptyState, Skeleton, Spinner } from '../../components/States'
import { useApi } from '../../hooks/useApi'
import { seriesPorEquipo, type Metrica } from '../../lib/stats'
import { addMinutes, formatFechaHoraUtc, formatHoraUtc, isoToUtcInput, utcInputToIso } from '../../lib/time'

interface Consulta {
  desde: string
  hasta: string
  agregacion: Agregacion
  equipo: string | null
}

const ACUMULADOS: Array<{ m: Metrica; label: string }> = [
  { m: 'golesAcum', label: 'Goles' },
  { m: 'pasesAcum', label: 'Pases' },
  { m: 'tirosAcum', label: 'Tiros' },
]

function fmt(v: number | null | undefined, sufijo = ''): string {
  return v === null || v === undefined ? '—' : `${Number.isInteger(v) ? v : v.toFixed(1)}${sufijo}`
}

function Resultado({ data, partido }: { data: EstadisticasPartido; partido: PartidoDetalle }) {
  const [acum, setAcum] = useState<Metrica>('golesAcum')
  const posesion = useMemo(() => seriesPorEquipo(data.puntos, 'posesionPct', partido), [data, partido])
  const acumulado = useMemo(() => seriesPorEquipo(data.puntos, acum, partido), [data, partido, acum])
  const etiquetaAcum = ACUMULADOS.find((a) => a.m === acum)?.label ?? ''

  return (
    <div className="stack">
      <p className="muted small" aria-live="polite">
        {data.cantidad} puntos · agregación {ETIQUETA_AGREGACION[data.agregacion]} · {formatFechaHoraUtc(data.desde)} →{' '}
        {formatHoraUtc(data.hasta)} UTC
      </p>
      {data.truncado && (
        <p className="note note-warn" role="status">
          <Icon name="alert" size={16} />
          <span>
            Se alcanzó el tope de puntos: hay más datos en la ventana. Achicá la ventana o usá una agregación mayor.
          </span>
        </p>
      )}

      <div className="grid-2">
        <div className="chart-card">
          {posesion.some((s) => s.points.length > 0) ? (
            <LineChart
              title="Posesión por equipo"
              yLabel="%"
              yMin={0}
              yMax={100}
              formatY={(v) => `${Math.round(v)}%`}
              series={posesion.map((s) => ({ id: s.equipoCodigo, label: s.label, variant: s.variant, points: s.points }))}
            />
          ) : (
            <EmptyState title="Sin datos de posesión en la ventana" icon="chart" />
          )}
        </div>
        <div className="chart-card">
          <fieldset className="segmented segmented-sm">
            <legend className="sr-only">Contador acumulado</legend>
            {ACUMULADOS.map((a) => (
              <label key={a.m} className={acum === a.m ? 'seg active' : 'seg'}>
                <input type="radio" name="acum" checked={acum === a.m} onChange={() => setAcum(a.m)} />
                {a.label}
              </label>
            ))}
          </fieldset>
          {acumulado.some((s) => s.points.length > 0) ? (
            <LineChart
              title={`${etiquetaAcum} acumulados por equipo`}
              yLabel={etiquetaAcum.toLowerCase()}
              formatY={(v) => String(Math.round(v))}
              integer
              series={acumulado.map((s) => ({ id: s.equipoCodigo, label: s.label, variant: s.variant, points: s.points }))}
            />
          ) : (
            <EmptyState title={`Sin datos de ${etiquetaAcum.toLowerCase()} en la ventana`} icon="chart" />
          )}
        </div>
      </div>

      <details className="disclosure">
        <summary>Ver los datos en tabla ({data.puntos.length} filas)</summary>
        <div className="table-wrap table-scroll">
          <table className="table compact">
            <caption className="sr-only">Puntos de estadísticas del partido {partido.partidoId}</caption>
            <thead>
              <tr>
                <th scope="col">Hora (UTC)</th>
                <th scope="col">Equipo</th>
                <th scope="col" className="num">
                  Posesión
                </th>
                <th scope="col" className="num">
                  Pases
                </th>
                <th scope="col" className="num">
                  Tiros
                </th>
                <th scope="col" className="num">
                  Goles
                </th>
                <th scope="col" className="num">
                  Minuto
                </th>
              </tr>
            </thead>
            <tbody>
              {data.puntos.map((p) => (
                <tr key={`${p.time}-${p.equipoCodigo}`}>
                  <td className="num">{formatHoraUtc(p.time)}</td>
                  <td>
                    <span className="mono">{p.equipoCodigo}</span>
                    {p.condicion ? <span className="muted small"> · {p.condicion.toLowerCase()}</span> : null}
                  </td>
                  <td className="num">{fmt(p.posesionPct, '%')}</td>
                  <td className="num">{fmt(p.pasesAcum)}</td>
                  <td className="num">{fmt(p.tirosAcum)}</td>
                  <td className="num">{fmt(p.golesAcum)}</td>
                  <td className="num">{fmt(p.minutoJuego)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

export function EstadisticasPanel({ partido }: { partido: PartidoDetalle }) {
  const id = partido.partidoId
  const [desde, setDesde] = useState(() => isoToUtcInput(partido.fechaHora))
  const [hasta, setHasta] = useState(() => isoToUtcInput(addMinutes(partido.fechaHora, 30)))
  const [agregacion, setAgregacion] = useState<Agregacion>('1m')
  const [equipo, setEquipo] = useState<string>('')
  const [errorForm, setErrorForm] = useState<string | null>(null)
  const [consulta, setConsulta] = useState<Consulta>(() => ({
    desde: addMinutes(partido.fechaHora, 0),
    hasta: addMinutes(partido.fechaHora, 30),
    agregacion: '1m',
    equipo: null,
  }))

  const key = `stats:${id}:${consulta.desde}:${consulta.hasta}:${consulta.agregacion}:${consulta.equipo ?? '*'}`
  const { loading, result, reload } = useApi(key, (s) =>
    getEstadisticas(id, { ...consulta, limit: 500 }, s),
  )

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const d = utcInputToIso(desde)
    const h = utcInputToIso(hasta)
    if (!d || !h) {
      setErrorForm('Completá desde y hasta con fecha y hora.')
      return
    }
    // La regla de la ventana (desde < hasta, ≤ 3 h) la valida la API: un 400 se muestra con su detalle.
    setErrorForm(null)
    const nueva: Consulta = { desde: d, hasta: h, agregacion, equipo: equipo === '' ? null : equipo }
    if (JSON.stringify(nueva) === JSON.stringify(consulta)) reload()
    else setConsulta(nueva)
  }

  return (
    <Panel
      title="Estadísticas en vivo"
      id="estadisticas"
      badges={<SourceBadge fuente="InfluxDB" rol="estadisticas_equipo" />}
      meta={result?.meta}
    >
      <form className="filters filters-wrap" onSubmit={onSubmit} noValidate>
        <div className="field">
          <label htmlFor="st-desde">Desde (UTC)</label>
          <input id="st-desde" type="datetime-local" className="mono" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="st-hasta">Hasta (UTC)</label>
          <input id="st-hasta" type="datetime-local" className="mono" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </div>
        <fieldset className="field">
          <legend>Agregación</legend>
          <div className="segmented">
            {AGREGACIONES.map((a) => (
              <label key={a} className={agregacion === a ? 'seg active' : 'seg'}>
                <input type="radio" name="agregacion" value={a} checked={agregacion === a} onChange={() => setAgregacion(a)} />
                {ETIQUETA_AGREGACION[a]}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="field">
          <label htmlFor="st-equipo">Equipo</label>
          <select id="st-equipo" value={equipo} onChange={(e) => setEquipo(e.target.value)}>
            <option value="">Ambos</option>
            <option value={partido.local.equipoCodigo}>{partido.local.equipoCodigo} (local)</option>
            <option value={partido.visitante.equipoCodigo}>{partido.visitante.equipoCodigo} (visitante)</option>
          </select>
        </div>
        <div className="field field-action">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? <Spinner /> : <Icon name="search" size={16} />}
            Consultar
          </button>
        </div>
        {errorForm && (
          <p className="field-error full" role="alert">
            {errorForm}
          </p>
        )}
        <p className="help full">
          Ventana [desde, hasta) en UTC, de hasta 3 horas. Por defecto, los primeros 30 minutos del partido.
        </p>
      </form>

      {loading || !result ? (
        <Skeleton lines={6} label="Consultando InfluxDB…" />
      ) : !result.ok ? (
        <ErrorPanel error={result.error} onRetry={reload} />
      ) : result.data.puntos.length === 0 ? (
        <EmptyState title="Sin puntos en la ventana" icon="chart">
          InfluxDB respondió bien (200) pero no hay mediciones entre {formatFechaHoraUtc(result.data.desde)} y{' '}
          {formatFechaHoraUtc(result.data.hasta)}. No es una falla de la fuente: probá otra ventana.
        </EmptyState>
      ) : (
        <Resultado data={result.data} partido={partido} />
      )}
    </Panel>
  )
}
