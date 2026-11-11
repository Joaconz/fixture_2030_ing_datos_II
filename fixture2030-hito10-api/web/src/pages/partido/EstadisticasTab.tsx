import { useMemo, useState } from 'react'
import { getEstadisticas } from '../../api/endpoints'
import { AGREGACIONES, ETIQUETA_AGREGACION } from '../../api/enums'
import type { Agregacion, EstadisticasPartido, PartidoDetalle } from '../../api/types'
import { Cargando, EstadoError, EstadoVacio } from '../../components/Estados'
import { Icon } from '../../components/Icon'
import { LineChart } from '../../components/LineChart'
import { useApi } from '../../hooks/useApi'
import {
  comparativa,
  minutoDeJuego,
  PERIODOS,
  promedio,
  seriesPorEquipo,
  ventanaDePeriodo,
  type Metrica,
  type Periodo,
} from '../../lib/stats'
import { formatHoraUtc } from '../../lib/time'

const EVOLUCION: Array<{ m: Metrica; label: string }> = [
  { m: 'golesAcum', label: 'Goles' },
  { m: 'tirosAcum', label: 'Tiros' },
  { m: 'pasesAcum', label: 'Pases' },
]

function fmt(v: number | null | undefined, sufijo = ''): string {
  return v === null || v === undefined ? '—' : `${Number.isInteger(v) ? v : v.toFixed(1)}${sufijo}`
}

function Segmentado<K extends string>({
  nombre,
  leyenda,
  opciones,
  valor,
  onChange,
}: {
  nombre: string
  leyenda: string
  opciones: ReadonlyArray<{ key: K; label: string }>
  valor: K
  onChange: (k: K) => void
}) {
  return (
    <fieldset className="segmento">
      <legend>{leyenda}</legend>
      <div className="segmento-opciones">
        {opciones.map((o) => (
          <label key={o.key} className={valor === o.key ? 'segmento-op activo' : 'segmento-op'}>
            <input type="radio" name={nombre} checked={valor === o.key} onChange={() => onChange(o.key)} />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function Resultado({ data, partido }: { data: EstadisticasPartido; partido: PartidoDetalle }) {
  const [evolucion, setEvolucion] = useState<Metrica>('golesAcum')
  const local = partido.local.equipoCodigo
  const visitante = partido.visitante.equipoCodigo
  const posLocal = promedio(data.puntos, local, 'posesionPct')
  const posVisit = promedio(data.puntos, visitante, 'posesionPct')
  const filas = useMemo(() => comparativa(data.puntos, partido), [data, partido])
  const seriePosesion = useMemo(() => seriesPorEquipo(data.puntos, 'posesionPct', partido), [data, partido])
  const serieEvolucion = useMemo(() => seriesPorEquipo(data.puntos, evolucion, partido), [data, partido, evolucion])
  const etiquetaEvolucion = EVOLUCION.find((e) => e.m === evolucion)?.label ?? ''
  const formatX = (t: number) => `${minutoDeJuego(t, partido.fechaHora)}′`
  const nombre = (codigo: string) => (codigo === local ? partido.local.nombre : partido.visitante.nombre)
  const aSerie = (s: ReturnType<typeof seriesPorEquipo>[number]) => ({
    id: s.equipoCodigo,
    label: nombre(s.equipoCodigo),
    variant: s.variant,
    points: s.points,
  })
  const totalPos = (posLocal ?? 0) + (posVisit ?? 0)
  const pctLocal = totalPos > 0 ? ((posLocal ?? 0) / totalPos) * 100 : 50

  return (
    <div className="stack">
      {data.truncado && (
        <p className="nota-linea" role="status">
          <Icon name="info" size={16} />
          Hay más mediciones de las que se muestran: elegí un período más corto o una agregación mayor.
        </p>
      )}

      <section className="card" aria-labelledby="posesion-titulo">
        <header className="card-head">
          <div>
            <h3 id="posesion-titulo" className="con-icono">
              <Icon name="activity" size={20} />
              Posesión
            </h3>
            <p className="card-sub">Promedio del período y evolución minuto a minuto</p>
          </div>
          <div className="posesion-resumen">
            <span>
              <span className="label-mini">{local}</span>
              <strong className="num serie-0-texto">{fmt(posLocal === null ? null : Math.round(posLocal), '%')}</strong>
            </span>
            <span className="posesion-sep" aria-hidden="true" />
            <span>
              <span className="label-mini">{visitante}</span>
              <strong className="num serie-1-texto">{fmt(posVisit === null ? null : Math.round(posVisit), '%')}</strong>
            </span>
          </div>
        </header>
        <div className="card-body">
          <div className="barra-dividida" aria-hidden="true">
            <span className="barra-local" style={{ width: `${pctLocal}%` }} />
            <span className="barra-visitante" style={{ width: `${100 - pctLocal}%` }} />
          </div>
          {seriePosesion.some((s) => s.points.length > 0) ? (
            <LineChart
              title="Posesión por equipo"
              yLabel="%"
              yMin={0}
              yMax={100}
              formatY={(v) => `${Math.round(v)}%`}
              formatX={formatX}
              series={seriePosesion.map(aSerie)}
            />
          ) : (
            <EstadoVacio titulo="Sin datos de posesión en este período" icono="chart" compacto />
          )}
        </div>
      </section>

      <section className="card" aria-labelledby="comparativa-titulo">
        <header className="card-head">
          <div>
            <h3 id="comparativa-titulo" className="con-icono">
              <Icon name="swap" size={20} />
              Comparativa
            </h3>
            <p className="card-sub">Acumulado al final del período</p>
          </div>
          <div className="leyenda">
            <span className="leyenda-item serie-0-texto">
              <i className="leyenda-color serie-0-fondo" /> {partido.local.nombre}
            </span>
            <span className="leyenda-item serie-1-texto">
              <i className="leyenda-color serie-1-fondo" /> {partido.visitante.nombre}
            </span>
          </div>
        </header>
        <div className="card-body">
          <ul className="comparativa">
            {filas.map((f) => (
              <li key={f.metrica}>
                <div className="comparativa-fila">
                  <strong className="num serie-0-texto">{fmt(f.local)}</strong>
                  <span>{f.label}</span>
                  <strong className="num serie-1-texto">{fmt(f.visitante)}</strong>
                </div>
                <div className="comparativa-barras" aria-hidden="true">
                  <span className="cb-lado cb-local">
                    <span style={{ width: `${f.pctLocal}%` }} />
                  </span>
                  <span className="cb-lado cb-visitante">
                    <span style={{ width: `${100 - f.pctLocal}%` }} />
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="card" aria-labelledby="evolucion-titulo">
        <header className="card-head">
          <div>
            <h3 id="evolucion-titulo" className="con-icono">
              <Icon name="chart" size={20} />
              Evolución
            </h3>
            <p className="card-sub">{etiquetaEvolucion} acumulados por equipo</p>
          </div>
          <Segmentado
            nombre="evolucion"
            leyenda="Métrica"
            opciones={EVOLUCION.map((e) => ({ key: e.m, label: e.label }))}
            valor={evolucion}
            onChange={setEvolucion}
          />
        </header>
        <div className="card-body">
          {serieEvolucion.some((s) => s.points.length > 0) ? (
            <LineChart
              title={`${etiquetaEvolucion} acumulados por equipo`}
              yLabel={etiquetaEvolucion.toLowerCase()}
              formatY={(v) => String(Math.round(v))}
              formatX={formatX}
              integer
              series={serieEvolucion.map(aSerie)}
            />
          ) : (
            <EstadoVacio titulo={`Sin datos de ${etiquetaEvolucion.toLowerCase()} en este período`} icono="chart" compacto />
          )}
          <details className="disclosure">
            <summary>Ver los datos en tabla ({data.puntos.length} filas)</summary>
            <div className="table-wrap table-scroll">
              <table className="table compact">
                <caption className="sr-only">Mediciones del partido por minuto y equipo</caption>
                <thead>
                  <tr>
                    <th scope="col">Minuto</th>
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
                  </tr>
                </thead>
                <tbody>
                  {data.puntos.map((p) => (
                    <tr key={`${p.time}-${p.equipoCodigo}`}>
                      <td className="num">{fmt(p.minutoJuego, '′')}</td>
                      <td className="num">{formatHoraUtc(p.time)}</td>
                      <td>{p.equipoCodigo}</td>
                      <td className="num">{fmt(p.posesionPct, '%')}</td>
                      <td className="num">{fmt(p.pasesAcum)}</td>
                      <td className="num">{fmt(p.tirosAcum)}</td>
                      <td className="num">{fmt(p.golesAcum)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </section>
    </div>
  )
}

/** Estadísticas del partido por ventana temporal (CU12): período ≤ 3 h y agregación raw, 1m o 5m. */
export function EstadisticasTab({ partido }: { partido: PartidoDetalle }) {
  const id = partido.partidoId
  const [periodo, setPeriodo] = useState<Periodo>('completo')
  const [agregacion, setAgregacion] = useState<Agregacion>('1m')
  const ventana = ventanaDePeriodo(partido.fechaHora, periodo)

  const key = `stats:${id}:${ventana.desde}:${ventana.hasta}:${agregacion}`
  const { result, reload } = useApi(key, (s) => getEstadisticas(id, { ...ventana, agregacion, limit: 2000 }, s))

  return (
    <div className="estadisticas">
      <div className="card barra-periodo">
        <Segmentado
          nombre="periodo"
          leyenda="Período"
          opciones={PERIODOS.map((p) => ({ key: p.key, label: p.label }))}
          valor={periodo}
          onChange={setPeriodo}
        />
        <Segmentado
          nombre="agregacion"
          leyenda="Detalle"
          opciones={AGREGACIONES.map((a) => ({ key: a, label: ETIQUETA_AGREGACION[a] }))}
          valor={agregacion}
          onChange={setAgregacion}
        />
      </div>

      {!result ? (
        <div className="card card-pad">
          <Cargando lineas={6} etiqueta="Cargando las estadísticas…" />
        </div>
      ) : !result.ok ? (
        <div className="card card-pad">
          <EstadoError error={result.error} onRetry={reload} recurso="ese partido" que="las estadísticas" />
        </div>
      ) : result.data.puntos.length === 0 ? (
        <div className="card card-pad">
          <EstadoVacio titulo="Sin estadísticas en este período" icono="chart">
            {partido.estado === 'PROGRAMADO'
              ? 'El partido todavía no se jugó: las estadísticas aparecen cuando empieza.'
              : 'No hay mediciones para este tramo del partido. Probá con otro período.'}
          </EstadoVacio>
        </div>
      ) : (
        <Resultado data={result.data} partido={partido} />
      )}
    </div>
  )
}
