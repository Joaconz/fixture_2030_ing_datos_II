import { useCallback, useEffect, useRef, useState } from 'react'
import type { ApiResult, ResponseMeta } from '../api/client'
import type { ApiFailure } from '../api/errors'
import { appendPage, emptyCursorState, hayMas, type CursorPage, type CursorState } from '../lib/pagination'

export type PageFetcher<T> = (cursor: string | null, signal: AbortSignal) => Promise<ApiResult<CursorPage<T>>>

interface Estado<T> {
  key: string
  list: CursorState<T>
  error: ApiFailure | null
  meta: ResponseMeta | null
}

export interface CursorList<T> {
  /** Primera página en curso (lista vacía). */
  loading: boolean
  items: T[]
  hasMore: boolean
  /** Error de la primera página (bloquea el panel). */
  error: ApiFailure | null
  /** Error al pedir una página siguiente (los ítems ya cargados se conservan). */
  moreError: ApiFailure | null
  loadingMore: boolean
  meta: ResponseMeta | null
  pages: number
  loadMore: () => void
  reload: () => void
}

/**
 * Lista paginada por `nextCursor`: pide la primera página cuando cambia `key`
 * y las siguientes con `loadMore()`, acumulando sin repetidos.
 */
export function useCursorList<T>(key: string, fetchPage: PageFetcher<T>, idOf: (item: T) => string): CursorList<T> {
  const fetchRef = useRef(fetchPage)
  const idRef = useRef(idOf)
  useEffect(() => {
    fetchRef.current = fetchPage
    idRef.current = idOf
  })

  const [nonce, setNonce] = useState(0)
  const fullKey = `${key}#${nonce}`
  const [estado, setEstado] = useState<Estado<T> | null>(null)
  const [more, setMore] = useState<{ key: string; loading: boolean; error: ApiFailure | null }>({
    key: '',
    loading: false,
    error: null,
  })
  const moreCtrl = useRef<AbortController | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchRef.current(null, ctrl.signal).then((r) => {
      if (ctrl.signal.aborted) return
      if (r.ok) {
        setEstado({ key: fullKey, list: appendPage(emptyCursorState<T>(), r.data, idRef.current), error: null, meta: r.meta })
      } else if (r.error.kind !== 'aborted') {
        setEstado({ key: fullKey, list: emptyCursorState<T>(), error: r.error, meta: r.meta })
      }
    })
    return () => {
      ctrl.abort()
      moreCtrl.current?.abort()
    }
  }, [fullKey])

  const vigente = estado !== null && estado.key === fullKey ? estado : null
  const moreVigente = more.key === fullKey ? more : { loading: false, error: null }

  const loadMore = useCallback(() => {
    if (!vigente || vigente.error || !hayMas(vigente.list) || moreVigente.loading) return
    const keyActual = vigente.key
    const ctrl = new AbortController()
    moreCtrl.current = ctrl
    setMore({ key: keyActual, loading: true, error: null })
    fetchRef.current(vigente.list.nextCursor, ctrl.signal).then((r) => {
      if (ctrl.signal.aborted) return
      if (r.ok) {
        setEstado((prev) =>
          prev && prev.key === keyActual
            ? { ...prev, list: appendPage(prev.list, r.data, idRef.current), meta: r.meta }
            : prev,
        )
        setMore({ key: keyActual, loading: false, error: null })
      } else if (r.error.kind !== 'aborted') {
        setMore({ key: keyActual, loading: false, error: r.error })
      }
    })
  }, [vigente, moreVigente.loading])

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  return {
    loading: vigente === null,
    items: vigente?.list.items ?? [],
    hasMore: vigente ? hayMas(vigente.list) : false,
    error: vigente?.error ?? null,
    moreError: moreVigente.error,
    loadingMore: moreVigente.loading,
    meta: vigente?.meta ?? null,
    pages: vigente?.list.pages ?? 0,
    loadMore,
    reload,
  }
}
