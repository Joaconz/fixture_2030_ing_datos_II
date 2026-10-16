import { useEffect, useId, useMemo, useRef, useState, type PointerEvent } from 'react'
import { formatHoraUtc } from '../lib/time'

export interface SeriePunto {
  t: number // epoch ms
  v: number
}

export interface Serie {
  id: string
  label: string
  /** 0 = local (línea continua, círculos), 1 = visitante (línea discontinua, cuadrados). */
  variant: 0 | 1
  points: SeriePunto[]
}

interface LineChartProps {
  series: Serie[]
  title: string
  yLabel: string
  yMin?: number
  yMax?: number
  formatY?: (v: number) => string
  /** Contadores: marcas del eje Y sólo en enteros. */
  integer?: boolean
  height?: number
}

const M = { top: 26, right: 18, bottom: 30, left: 44 }

function nice(max: number): number {
  if (max <= 0) return 1
  const exp = Math.pow(10, Math.floor(Math.log10(max)))
  const f = max / exp
  const n = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10
  return n * exp
}

/** Gráfico de líneas SVG propio (sin librería): series distinguibles por color, trazo y marcador. */
export function LineChart({ series, title, yLabel, yMin = 0, yMax, formatY = String, integer = false, height = 240 }: LineChartProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(640)
  const [hover, setHover] = useState<number | null>(null)
  const titleId = useId()

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w && w > 0) setWidth(Math.round(w))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const calc = useMemo(() => {
    const todos = series.flatMap((s) => s.points)
    const tMin = Math.min(...todos.map((p) => p.t))
    const tMax = Math.max(...todos.map((p) => p.t))
    const vMaxData = Math.max(...todos.map((p) => p.v), 0)
    let top = yMax ?? nice(vMaxData * 1.05)
    let pasoY = (top - yMin) / 4
    if (integer && yMax === undefined) {
      pasoY = Math.max(1, Math.ceil((Math.max(vMaxData, 1) - yMin) / 4))
      top = yMin + pasoY * 4
    }
    const innerW = Math.max(10, width - M.left - M.right)
    const innerH = height - M.top - M.bottom
    const span = tMax - tMin || 1
    const x = (t: number) => M.left + ((t - tMin) / span) * innerW
    const y = (v: number) => M.top + innerH - ((v - yMin) / (top - yMin || 1)) * innerH
    const tiempos = Array.from(new Set(todos.map((p) => p.t))).sort((a, b) => a - b)
    const nTicksX = Math.max(2, Math.min(6, Math.floor(innerW / 90)))
    const ticksX = Array.from({ length: nTicksX }, (_, i) => tMin + (span * i) / (nTicksX - 1))
    const ticksY = Array.from({ length: 5 }, (_, i) => yMin + pasoY * i)
    return { tMin, tMax, x, y, innerW, innerH, tiempos, ticksX, ticksY }
  }, [series, width, height, yMax, yMin, integer])

  const totalPuntos = series.reduce((n, s) => n + s.points.length, 0)
  if (totalPuntos === 0) return null
  const { x, y, tiempos, ticksX, ticksY } = calc

  function onMove(e: PointerEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = e.clientX - rect.left + M.left
    let mejor: number | null = null
    let dist = Infinity
    for (const t of tiempos) {
      const d = Math.abs(x(t) - px)
      if (d < dist) {
        dist = d
        mejor = t
      }
    }
    setHover(mejor)
  }

  const valoresHover =
    hover === null
      ? []
      : series.map((s) => {
          const p = s.points.reduce<SeriePunto | null>(
            (best, q) => (best === null || Math.abs(q.t - hover) < Math.abs(best.t - hover) ? q : best),
            null,
          )
          return { s, p }
        })

  const marcadores = totalPuntos <= 120

  return (
    <figure className="chart" ref={wrapRef}>
      <figcaption id={titleId} className="chart-title">
        {title}
      </figcaption>
      <div className="chart-legend" aria-hidden="true">
        {series.map((s) => (
          <span key={s.id} className={`legend-item serie-${s.variant}`}>
            <svg width="28" height="12" viewBox="0 0 28 12">
              <line x1="0" y1="6" x2="28" y2="6" className="serie-line" />
              {s.variant === 0 ? <circle cx="14" cy="6" r="3.5" className="serie-mark" /> : <rect x="10.5" y="2.5" width="7" height="7" className="serie-mark" />}
            </svg>
            {s.label}
          </span>
        ))}
      </div>
      <div className="chart-canvas">
        <svg
          width={width}
          height={height}
          role="img"
          aria-labelledby={titleId}
          aria-describedby={`${titleId}-desc`}
        >
          <desc id={`${titleId}-desc`}>
            {series
              .map((s) => {
                const ult = s.points[s.points.length - 1]
                return `${s.label}: ${s.points.length} puntos${ult ? `, último valor ${formatY(ult.v)}` : ''}`
              })
              .join('. ')}
            . La tabla de datos debajo tiene los valores exactos.
          </desc>
          {ticksY.map((v) => (
            <g key={`y${v}`}>
              <line className="grid" x1={M.left} x2={width - M.right} y1={y(v)} y2={y(v)} />
              <text className="axis" x={M.left - 8} y={y(v)} dy="0.32em" textAnchor="end">
                {formatY(v)}
              </text>
            </g>
          ))}
          {ticksX.map((t, i) => (
            <text
              key={`x${t}`}
              className="axis"
              x={x(t)}
              y={height - 8}
              textAnchor={i === 0 ? 'start' : i === ticksX.length - 1 ? 'end' : 'middle'}
            >
              {formatHoraUtc(new Date(t).toISOString())}
            </text>
          ))}
          <text className="axis axis-label" x={8} y={14}>
            {yLabel}
          </text>
          {series.map((s) => {
            const pts = [...s.points].sort((a, b) => a.t - b.t)
            const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')
            return (
              <g key={s.id} className={`serie-${s.variant}`}>
                <path d={d} className="serie-line" fill="none" />
                {marcadores &&
                  pts.map((p) =>
                    s.variant === 0 ? (
                      <circle key={p.t} cx={x(p.t)} cy={y(p.v)} r={3} className="serie-mark" />
                    ) : (
                      <rect key={p.t} x={x(p.t) - 3} y={y(p.v) - 3} width={6} height={6} className="serie-mark" />
                    ),
                  )}
              </g>
            )
          })}
          {hover !== null && (
            <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={M.top} y2={height - M.bottom} />
          )}
          <rect
            className="chart-hit"
            x={M.left}
            y={M.top}
            width={calc.innerW}
            height={calc.innerH}
            onPointerMove={onMove}
            onPointerDown={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>
        {hover !== null && (
          <div
            className="chart-tooltip"
            style={{ left: Math.min(Math.max(x(hover) + 10, 0), width - 170) }}
            aria-hidden="true"
          >
            <strong>{formatHoraUtc(new Date(hover).toISOString())} UTC</strong>
            {valoresHover.map(({ s, p }) => (
              <span key={s.id} className={`serie-${s.variant}`}>
                <i className="tt-swatch" /> {s.label}: {p ? formatY(p.v) : '—'}
              </span>
            ))}
          </div>
        )}
      </div>
    </figure>
  )
}
