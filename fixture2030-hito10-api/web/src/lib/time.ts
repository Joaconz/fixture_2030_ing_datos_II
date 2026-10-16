/**
 * Fechas: la API trabaja en UTC (reloj del torneo simulado). La UI muestra y
 * edita SIEMPRE en UTC para que lo que se ve sea lo que se envía.
 */

const pad = (n: number) => String(n).padStart(2, '0')

/** ISO → valor de <input type="datetime-local"> interpretado como UTC ("YYYY-MM-DDTHH:mm"). */
export function isoToUtcInput(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(
    d.getUTCMinutes(),
  )}`
}

/** Valor de datetime-local (leído como UTC) → ISO con zona "Z", o null si es inválido. */
export function utcInputToIso(valor: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(valor)
  if (!m) return null
  const [, y, mo, d, h, mi, s] = m
  const ms = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(s ?? '0'))
  if (Number.isNaN(ms)) return null
  return new Date(ms).toISOString().replace('.000Z', 'Z')
}

export function addMinutes(iso: string, minutos: number): string {
  return new Date(new Date(iso).getTime() + minutos * 60_000).toISOString().replace('.000Z', 'Z')
}

const fmtFechaHora = new Intl.DateTimeFormat('es-AR', {
  timeZone: 'UTC',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const fmtHora = new Intl.DateTimeFormat('es-AR', {
  timeZone: 'UTC',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const fmtFecha = new Intl.DateTimeFormat('es-AR', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric' })

export function formatFechaHoraUtc(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : `${fmtFechaHora.format(d)} UTC`
}

export function formatHoraUtc(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : fmtHora.format(d)
}

export function formatFecha(isoDate: string): string {
  // Fechas sin hora ("1987-06-24"): se leen como UTC para no correr el día.
  const d = new Date(isoDate.length === 10 ? `${isoDate}T00:00:00Z` : isoDate)
  return Number.isNaN(d.getTime()) ? isoDate : fmtFecha.format(d)
}

/** 3725 → "1 h 02 min 05 s" */
export function formatDuracion(segundos: number): string {
  if (segundos < 0) return '—'
  const h = Math.floor(segundos / 3600)
  const m = Math.floor((segundos % 3600) / 60)
  const s = Math.floor(segundos % 60)
  if (h > 0) return `${h} h ${pad(m)} min ${pad(s)} s`
  if (m > 0) return `${m} min ${pad(s)} s`
  return `${s} s`
}
