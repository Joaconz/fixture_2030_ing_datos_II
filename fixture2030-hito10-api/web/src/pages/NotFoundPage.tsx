import { Link } from 'react-router'
import { EstadoVacio } from '../components/Estados'
import { Icon } from '../components/Icon'

export function NotFoundPage() {
  return (
    <div className="page">
      <section className="card card-pad" aria-labelledby="nf-titulo">
        <h1 id="nf-titulo" className="titulo-seccion">
          Página no encontrada
        </h1>
        <EstadoVacio
          titulo="Esta dirección no existe"
          icono="searchX"
          accion={
            <Link to="/" className="btn btn-secondary btn-sm">
              <Icon name="arrowLeft" size={16} />
              Volver al inicio
            </Link>
          }
        >
          Desde el inicio podés buscar un equipo por su código FIFA o entrar a un partido destacado.
        </EstadoVacio>
      </section>
    </div>
  )
}
