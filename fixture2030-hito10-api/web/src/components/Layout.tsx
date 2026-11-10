import { useEffect, useRef } from 'react'
import { Link, Outlet, useLocation } from 'react-router'
import { FifaSearch } from './FifaSearch'
import { Icon } from './Icon'

/**
 * Barra superior fina (stitch/DESIGN.md §5): marca y buscador de equipo por
 * código FIFA. Sin pestañas de navegación, sin pie de página y sin selector de
 * tema: el diseño es sólo claro (§6).
 */
export function Layout() {
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  const primera = useRef(true)

  // Al cambiar de ruta, el foco va al contenido principal (lectores de pantalla).
  useEffect(() => {
    if (primera.current) {
      primera.current = false
      return
    }
    const h1 = mainRef.current?.querySelector('h1')
    if (h1 instanceof HTMLElement) {
      h1.setAttribute('tabindex', '-1')
      h1.focus({ preventScroll: false })
    } else {
      mainRef.current?.focus()
    }
  }, [location.pathname])

  const enInicio = location.pathname === '/'

  return (
    <div className="app">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          {!enInicio && (
            <Link to="/" className="btn-icon topbar-volver" aria-label="Volver al inicio">
              <Icon name="arrowLeft" size={20} />
            </Link>
          )}
          <Link to="/" className="brand" aria-label="Fixture 2030 — Inicio">
            Fixture 2030
          </Link>
          <div className="topbar-tools">
            <FifaSearch variante="barra" key={location.pathname} />
          </div>
        </div>
      </header>

      <main id="contenido" ref={mainRef} tabIndex={-1} className="main">
        <Outlet />
      </main>
    </div>
  )
}
