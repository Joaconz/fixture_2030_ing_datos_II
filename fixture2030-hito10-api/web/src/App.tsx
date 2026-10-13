import { BrowserRouter, Route, Routes, useParams } from 'react-router'
import { Layout } from './components/Layout'
import { EquipoPage } from './pages/EquipoPage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PartidoPage } from './pages/partido/PartidoPage'
import { SaludPage } from './pages/SaludPage'
import { SesionPage } from './pages/SesionPage'

// `key` por id: al navegar de un recurso a otro el estado local (formularios, historial) arranca limpio.
function EquipoRoute() {
  const { codigo = '' } = useParams()
  return <EquipoPage key={codigo} />
}
function PartidoRoute() {
  const { id = '' } = useParams()
  return <PartidoPage key={id} />
}
function SesionRoute() {
  const { id = '' } = useParams()
  return <SesionPage key={id} />
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="equipos/:codigo" element={<EquipoRoute />} />
          <Route path="partidos/:id" element={<PartidoRoute />} />
          <Route path="sesiones/:id" element={<SesionRoute />} />
          <Route path="salud" element={<SaludPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
