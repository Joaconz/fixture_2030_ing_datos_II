import { useCallback, useEffect, useState } from 'react'

export type Tema = 'sistema' | 'claro' | 'oscuro'
const CLAVE = 'f30-tema'

function leer(): Tema {
  try {
    const v = localStorage.getItem(CLAVE)
    return v === 'claro' || v === 'oscuro' ? v : 'sistema'
  } catch {
    return 'sistema'
  }
}

/** Tema claro/oscuro: por defecto sigue al sistema; la elección se recuerda en este navegador. */
export function useTheme(): [Tema, (t: Tema) => void] {
  const [tema, setTemaState] = useState<Tema>(leer)

  useEffect(() => {
    const root = document.documentElement
    if (tema === 'sistema') delete root.dataset.theme
    else root.dataset.theme = tema === 'claro' ? 'light' : 'dark'
  }, [tema])

  const setTema = useCallback((t: Tema) => {
    setTemaState(t)
    try {
      if (t === 'sistema') localStorage.removeItem(CLAVE)
      else localStorage.setItem(CLAVE, t)
    } catch {
      /* almacenamiento bloqueado: el tema vale sólo para esta pestaña */
    }
  }, [])

  return [tema, setTema]
}
