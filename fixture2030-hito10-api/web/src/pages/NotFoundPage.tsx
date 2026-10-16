import { Link } from 'react-router'
import { EmptyState } from '../components/States'

export function NotFoundPage() {
  return (
    <div className="page">
      <h1>Página no encontrada</h1>
      <EmptyState title="Esta ruta no existe en el front" icon="searchX">
        <p>
          Volvé al <Link to="/">inicio</Link> para buscar un equipo, un partido o una sesión.
        </p>
      </EmptyState>
    </div>
  )
}
