import { Link } from 'react-router'
import { getPartido } from '../api/endpoints'
import { Cargando, EstadoError, EstadoNoDisponible } from '../components/Estados'
import { FifaSearch } from '../components/FifaSearch'
import { TarjetaPartido } from '../components/Fixture'
import { useApi } from '../hooks/useApi'

/**
 * La API no tiene un listado del fixture: los destacados son partidos conocidos
 * de la carga de muestra, pedidos uno por uno al detalle (CU4).
 */
const DESTACADOS = ['PAR-A-1', 'PAR-A-3', 'PAR-A-5', 'PAR-D16-01'] as const

/** Equipos con ficha en la carga de muestra (CU1). */
const ACCESOS = ['ARG', 'BRA', 'ESP', 'POR', 'MAR', 'FRA', 'GER', 'ENG', 'NED', 'BEL'] as const

function Destacado({ id }: { id: string }) {
  const { result, reload } = useApi(`destacado:${id}`, (s) => getPartido(id, s))
  if (!result) {
    return (
      <div className="tarjeta-partido tarjeta-cargando">
        <Cargando lineas={3} etiqueta={`Cargando el partido ${id}…`} />
      </div>
    )
  }
  if (!result.ok) {
    return (
      <div className="tarjeta-partido tarjeta-estado">
        <EstadoError error={result.error} onRetry={reload} recurso="este partido" que="este partido" compacto />
      </div>
    )
  }
  return <TarjetaPartido p={result.data} />
}

export function HomePage() {
  return (
    <div className="page inicio">
      <section className="inicio-buscar" aria-labelledby="inicio-titulo">
        <p className="eyebrow-text">Mundial 2030</p>
        <h1 id="inicio-titulo">Seguí a tu selección</h1>
        <p className="lead">
          Buscá un equipo por su código FIFA para ver su ficha, su plantel y sus partidos. Cada partido trae eventos,
          comentarios de otros hinchas y estadísticas.
        </p>
        <div className="card card-pad">
          <FifaSearch />
        </div>

        <div className="accesos" aria-labelledby="accesos-titulo">
          <h2 id="accesos-titulo" className="label-titulo">
            Accesos por código
          </h2>
          <ul className="chips">
            {ACCESOS.map((c) => (
              <li key={c}>
                <Link to={`/equipos/${c}`} className="chip-link num">
                  {c}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <EstadoNoDisponible titulo="Calendario completo y tablas de grupos">
          Todavía no están disponibles: por ahora los partidos se recorren desde la ficha de cada equipo.
        </EstadoNoDisponible>
      </section>

      <section className="inicio-destacados" aria-labelledby="destacados-titulo">
        <div className="seccion-cabecera">
          <h2 id="destacados-titulo">Partidos destacados</h2>
        </div>
        <ul className="lista-destacados">
          {DESTACADOS.map((id) => (
            <li key={id}>
              <Destacado id={id} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
