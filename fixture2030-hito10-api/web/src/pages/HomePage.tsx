import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { SourceBadge, type Fuente } from '../components/Badges'
import { Icon, type IconName } from '../components/Icon'

interface Demo {
  to: string
  id: string
  titulo: string
  texto: string
  icono: IconName
  fuentes: Fuente[]
}

const DEMOS: Demo[] = [
  {
    to: '/equipos/ARG',
    id: 'ARG',
    titulo: 'Ficha, plantel y partidos',
    texto: 'Ficha y plantel paginado desde MongoDB; partidos del equipo desde el grafo.',
    icono: 'users',
    fuentes: ['MongoDB', 'Neo4j'],
  },
  {
    to: '/partidos/PAR-A-1',
    id: 'PAR-A-1',
    titulo: 'Partido con eventos',
    texto: 'Detalle con caché (X-Cache), timeline, comentarios y estadísticas.',
    icono: 'ball',
    fuentes: ['Neo4j', 'Redis', 'Cassandra', 'InfluxDB'],
  },
  {
    to: '/partidos/PAR-D16-01',
    id: 'PAR-D16-01',
    titulo: 'Partido sin eventos',
    texto: 'Existe pero no se jugó: 200 con lista vacía, distinto de un 404.',
    icono: 'list',
    fuentes: ['Neo4j'],
  },
  {
    to: '/partidos/PAR-DEMO-API?tab=mesa',
    id: 'PAR-DEMO-API',
    titulo: 'Flujo de cierre',
    texto: 'Mesa de control: registrar eventos con Idempotency-Key y cerrar el partido.',
    icono: 'flag',
    fuentes: ['Neo4j', 'Redis'],
  },
  {
    to: '/sesiones/demo-ses-0000001-1',
    id: 'demo-ses-0000001-1',
    titulo: 'Sesión de demo',
    texto: 'Consulta con TTL restante e invalidación (404/403 documentados).',
    icono: 'shield',
    fuentes: ['Redis'],
  },
]

const MODULOS: Array<{ fuente: Fuente; que: string }> = [
  { fuente: 'MongoDB', que: 'Equipos y jugadores' },
  { fuente: 'Neo4j', que: 'Partidos, eventos y tipos de evento' },
  { fuente: 'Redis', que: 'Sesiones y caché del detalle de partido' },
  { fuente: 'Cassandra', que: 'Comentarios' },
  { fuente: 'InfluxDB', que: 'Estadísticas en vivo' },
]

function Buscador({
  id,
  label,
  ayuda,
  placeholder,
  boton,
  transformar,
  destino,
  maxLength,
}: {
  id: string
  label: string
  ayuda: string
  placeholder: string
  boton: string
  transformar: (v: string) => string
  destino: (v: string) => string
  maxLength?: number
}) {
  const [valor, setValor] = useState('')
  const [vacio, setVacio] = useState(false)
  const navigate = useNavigate()

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const v = transformar(valor)
    if (v === '') {
      setVacio(true)
      return
    }
    void navigate(destino(v))
  }

  return (
    <form className="search" onSubmit={onSubmit} noValidate>
      <label htmlFor={id}>{label}</label>
      <div className="search-row">
        <input
          id={id}
          type="text"
          value={valor}
          onChange={(e) => {
            setValor(e.target.value)
            setVacio(false)
          }}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          maxLength={maxLength}
          aria-describedby={`${id}-ayuda${vacio ? ` ${id}-error` : ''}`}
          aria-invalid={vacio}
          className="mono"
        />
        <button type="submit" className="btn btn-primary">
          <Icon name="search" size={16} />
          {boton}
        </button>
      </div>
      <p id={`${id}-ayuda`} className="help">
        {ayuda}
      </p>
      {vacio && (
        <p id={`${id}-error`} className="field-error" role="alert">
          Escribí un valor para buscar.
        </p>
      )}
    </form>
  )
}

export function HomePage() {
  return (
    <div className="page">
      <section className="hero" aria-labelledby="home-titulo">
        <p className="eyebrow">Mundial 2030 · API REST integrada</p>
        <h1 id="home-titulo">Centro de datos del torneo</h1>
        <p className="lead">
          Consultá equipos, partidos, eventos, comentarios y estadísticas. Cada panel indica de qué base sale el dato y
          muestra el <code className="mono">X-Request-Id</code> de la respuesta.
        </p>
      </section>

      <section className="panel" aria-labelledby="buscar-titulo">
        <header className="panel-head">
          <div className="panel-title">
            <h2 id="buscar-titulo">Buscar</h2>
          </div>
        </header>
        <div className="panel-body search-grid">
          <Buscador
            id="buscar-equipo"
            label="Equipo"
            ayuda="Código FIFA de 3 letras, por ejemplo ARG."
            placeholder="ARG"
            boton="Ver equipo"
            maxLength={3}
            transformar={(v) => v.trim().toUpperCase()}
            destino={(v) => `/equipos/${encodeURIComponent(v)}`}
          />
          <Buscador
            id="buscar-partido"
            label="Partido"
            ayuda="Identificador del partido, por ejemplo PAR-A-1."
            placeholder="PAR-A-1"
            boton="Ver partido"
            maxLength={40}
            transformar={(v) => v.trim().toUpperCase()}
            destino={(v) => `/partidos/${encodeURIComponent(v)}`}
          />
          <Buscador
            id="buscar-sesion"
            label="Sesión"
            ayuda="Id de sesión, por ejemplo demo-ses-0000001-1."
            placeholder="demo-ses-0000001-1"
            boton="Consultar"
            maxLength={64}
            transformar={(v) => v.trim()}
            destino={(v) => `/sesiones/${encodeURIComponent(v)}`}
          />
        </div>
      </section>

      <section aria-labelledby="demo-titulo" className="stack">
        <h2 id="demo-titulo" className="section-title">
          Accesos de demo
        </h2>
        <ul className="demo-grid">
          {DEMOS.map((d) => (
            <li key={d.id}>
              <Link to={d.to} className="demo-card">
                <span className="demo-icon" aria-hidden="true">
                  <Icon name={d.icono} size={20} />
                </span>
                <span className="demo-main">
                  <code className="mono demo-id">{d.id}</code>
                  <strong>{d.titulo}</strong>
                  <span className="muted">{d.texto}</span>
                  <span className="badge-row">
                    {d.fuentes.map((f) => (
                      <SourceBadge key={f} fuente={f} />
                    ))}
                  </span>
                </span>
                <Icon name="chevronRight" size={18} className="demo-chevron" />
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" aria-labelledby="fuentes-titulo">
        <header className="panel-head">
          <div className="panel-title">
            <h2 id="fuentes-titulo">De dónde sale cada dato</h2>
          </div>
          <div className="panel-actions">
            <Link to="/salud" className="btn btn-secondary btn-sm">
              <Icon name="activity" size={16} /> Ver salud de las fuentes
            </Link>
          </div>
        </header>
        <div className="panel-body">
          <ul className="source-map">
            {MODULOS.map((m) => (
              <li key={m.fuente}>
                <SourceBadge fuente={m.fuente} />
                <span>{m.que}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  )
}
