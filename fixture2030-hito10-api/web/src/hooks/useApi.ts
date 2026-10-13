import { useCallback, useEffect, useRef, useState } from 'react'
import type { ApiResult } from '../api/client'

export type Fetcher<T> = (signal: AbortSignal) => Promise<ApiResult<T>>

export interface ApiState<T> {
  loading: boolean
  result: ApiResult<T> | null
  /** Último resultado de la MISMA key mientras se recarga (para no desmontar la vista). */
  stale: ApiResult<T> | null
  reload: () => void
}

/**
 * Ejecuta `fetcher` cada vez que cambia `key` (o con `reload()`), cancela la
 * request anterior y descarta respuestas viejas. `key = null` no pide nada.
 */
export function useApi<T>(key: string | null, fetcher: Fetcher<T>): ApiState<T> {
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  const [nonce, setNonce] = useState(0)
  const fullKey = key === null ? null : `${key}#${nonce}`
  const [estado, setEstado] = useState<{ base: string; key: string; result: ApiResult<T> } | null>(null)

  useEffect(() => {
    if (fullKey === null) return
    const ctrl = new AbortController()
    fetcherRef.current(ctrl.signal).then((result) => {
      if (ctrl.signal.aborted) return
      if (!result.ok && result.error.kind === 'aborted') return
      setEstado({ base: fullKey.slice(0, fullKey.lastIndexOf('#')), key: fullKey, result })
    })
    return () => ctrl.abort()
  }, [fullKey])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  const vigente = estado !== null && estado.key === fullKey
  return {
    loading: fullKey !== null && !vigente,
    result: vigente ? estado.result : null,
    stale: !vigente && estado !== null && estado.base === key ? estado.result : null,
    reload,
  }
}
