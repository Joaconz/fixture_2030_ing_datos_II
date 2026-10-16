import { useEffect, useRef } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { API_URL } from '../config'
import { useTheme, type Tema } from '../hooks/useTheme'
import { ConnectionIndicator } from './ConnectionIndicator'
import { Icon, type IconName } from './Icon'

const TEMAS: Array<{ tema: Tema; icono: IconName; label: string }> = [
  { tema: 'sistema', icono: 'monitor', label: 'Tema del sistema' },
  { tema: 'claro', icono: 'sun', label: 'Tema claro' },
  { tema: 'oscuro', icono: 'moon', label: 'Tema oscuro' },
]

function ThemeSwitch() {
  const [tema, setTema] = useTheme()
  return (
    <div className="theme-switch" role="group" aria-label="Tema de color">
      {TEMAS.map((t) => (
        <button
          key={t.tema}
          type="button"
          className="btn-icon"
          aria-pressed={tema === t.tema}
          aria-label={t.label}
          title={t.label}
          onClick={() => setTema(t.tema)}
        >
          <Icon name={t.icono} size={16} />
        </button>
      ))}
    </div>
  )
}

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

  return (
    <div className="app">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand" aria-label="Fixture 2030 · Centro de datos — Inicio">
            <span className="brand-mark" aria-hidden="true">
              <Icon name="ball" size={20} />
            </span>
            <span className="brand-text">
              <strong>Fixture 2030</strong>
              <span>Centro de datos</span>
            </span>
          </Link>
          <nav className="mainnav" aria-label="Principal">
            <NavLink to="/" end>
              Inicio
            </NavLink>
            <NavLink to="/salud">Salud</NavLink>
          </nav>
          <div className="topbar-tools">
            <ConnectionIndicator />
            <ThemeSwitch />
          </div>
        </div>
      </header>

      <main id="contenido" ref={mainRef} tabIndex={-1} className="main">
        <Outlet />
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <span>
            Ingeniería de Datos II · Hito 10 · API REST integrada
          </span>
          <span>
            API: <code className="mono">{API_URL}</code>
          </span>
        </div>
      </footer>
    </div>
  )
}
