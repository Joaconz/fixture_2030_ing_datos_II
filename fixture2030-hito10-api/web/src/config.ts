/**
 * Configuración del front. La única variable es la URL base de la API
 * (FastAPI del Hito 10, corre en la notebook). Se define en build con
 * `VITE_API_URL`; si no está, se usa la API local.
 */
const DEFAULT_API_URL = 'http://localhost:8000'

function normalizar(url: string | undefined): string {
  const limpia = (url ?? '').trim()
  return (limpia === '' ? DEFAULT_API_URL : limpia).replace(/\/+$/, '')
}

export const API_URL: string = normalizar(import.meta.env.VITE_API_URL)

/** Cada cuánto el indicador de conexión vuelve a consultar /health (ms). */
export const HEALTH_POLL_MS = 30_000
