/**
 * Paginación por cursor opaco (`nextCursor`). El front nunca interpreta el
 * cursor: lo devuelve tal cual en la siguiente request. `null` = no hay más.
 */
export interface CursorPage<T> {
  items: T[]
  nextCursor?: string | null
}

export interface CursorState<T> {
  items: T[]
  nextCursor: string | null
  pages: number
}

export function emptyCursorState<T>(): CursorState<T> {
  return { items: [], nextCursor: null, pages: 0 }
}

/**
 * Agrega una página a la lista acumulada, sin repetir ítems (por `idOf`),
 * y conserva el `nextCursor` de la última página.
 */
export function appendPage<T>(prev: CursorState<T>, page: CursorPage<T>, idOf: (item: T) => string): CursorState<T> {
  const vistos = new Set(prev.items.map(idOf))
  const nuevos = page.items.filter((it) => {
    const id = idOf(it)
    if (vistos.has(id)) return false
    vistos.add(id)
    return true
  })
  return {
    items: [...prev.items, ...nuevos],
    nextCursor: normalizarCursor(page.nextCursor),
    pages: prev.pages + 1,
  }
}

export function normalizarCursor(c: string | null | undefined): string | null {
  return typeof c === 'string' && c.length > 0 ? c : null
}

export function hayMas<T>(s: CursorState<T>): boolean {
  return s.nextCursor !== null
}
