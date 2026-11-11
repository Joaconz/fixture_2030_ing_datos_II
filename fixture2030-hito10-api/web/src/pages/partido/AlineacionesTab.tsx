import { useCallback } from 'react'
import { Link } from 'react-router'
import { getEquipo, listJugadores } from '../../api/endpoints'
import type { EquipoEnPartido, Jugador, PartidoDetalle } from '../../api/types'
import { Cargando, EstadoError, EstadoNoDisponible, EstadoVacio } from '../../components/Estados'
import { CodigoEquipo } from '../../components/Fixture'
import { Spinner } from '../../components/States'
import { useApi } from '../../hooks/useApi'
import { useCursorList } from '../../hooks/useCursorList'
import { lineasDelPlantel, SIGLA_POSICION } from '../../lib/plantel'

/**
 * La API no informa alineaciones (titulares, suplentes ni reservas). Por equipo
 * se muestra el plantel (CU2) y el director técnico de la ficha (CU1). Los
 * códigos del partido y de las fichas no siempre coinciden (Hallazgo H1): si
 * la ficha no existe, se dice en esa columna sin romper la otra.
 */
function ColumnaEquipo({ equipo, rol }: { equipo: EquipoEnPartido; rol: 'Local' | 'Visitante' }) {
  const codigo = equipo.equipoCodigo
  const ficha = useApi(`equipo:${codigo}`, (s) => getEquipo(codigo, s))
  const fetchPage = useCallback(
    (cursor: string | null, signal: AbortSignal) => listJugadores(codigo, { limit: 50, cursor }, signal),
    [codigo],
  )
  const lista = useCursorList<Jugador>(`alineacion:${codigo}`, fetchPage, (j) => j.dni)
  const entrenador = ficha.result?.ok ? ficha.result.data.entrenador : null
  const titulo = `alineacion-${rol.toLowerCase()}`

  return (
    <section className="card" aria-labelledby={titulo}>
      <header className="card-head alineacion-cabecera">
        <div className="alineacion-equipo">
          <CodigoEquipo codigo={codigo} />
          <div>
            <h3 id={titulo}>
              <Link to={`/equipos/${encodeURIComponent(codigo)}`}>{equipo.nombre}</Link>
            </h3>
            <p className="card-sub">{entrenador ? `DT: ${entrenador}` : rol}</p>
          </div>
        </div>
        <span className="tag">{rol}</span>
      </header>
      <div className="card-body">
        {lista.loading ? (
          <Cargando lineas={8} etiqueta={`Cargando el plantel de ${equipo.nombre}…`} />
        ) : lista.error ? (
          <EstadoError
            error={lista.error}
            onRetry={lista.reload}
            recurso={`el plantel de ${equipo.nombre}`}
            que="el plantel"
            compacto
          />
        ) : lista.items.length === 0 ? (
          <EstadoVacio titulo="Plantel sin jugadores cargados" icono="users" compacto />
        ) : (
          <>
            <h4 className="label-titulo alineacion-subtitulo">
              Plantel <span className="num">({lista.items.length}{lista.hasMore ? '+' : ''})</span>
            </h4>
            <ol className="alineacion-lista">
              {lineasDelPlantel(lista.items).flatMap((l) =>
                l.jugadores.map((j) => (
                  <li key={j.dni}>
                    <span className="al-dorsal num">{j.dorsal}</span>
                    <span className="al-nombre">
                      {j.nombre} {j.apellido}
                    </span>
                    <abbr className="al-pos" title={j.posicion}>
                      {SIGLA_POSICION[j.posicion]}
                    </abbr>
                  </li>
                )),
              )}
            </ol>
            {lista.hasMore && (
              <div className="card-acciones">
                <button type="button" className="btn btn-secondary btn-sm" onClick={lista.loadMore} disabled={lista.loadingMore}>
                  {lista.loadingMore ? <Spinner label="Cargando…" /> : 'Ver más jugadores'}
                </button>
              </div>
            )}
            {lista.moreError && <EstadoError error={lista.moreError} onRetry={lista.loadMore} que="más jugadores" compacto />}
          </>
        )}
      </div>
    </section>
  )
}

export function AlineacionesTab({ partido }: { partido: PartidoDetalle }) {
  return (
    <div className="stack">
      <EstadoNoDisponible titulo="Titulares, suplentes y reservas">
        Todavía no se informan las alineaciones del partido: abajo está el plantel completo de cada selección.
      </EstadoNoDisponible>
      <div className="grid-dos">
        <ColumnaEquipo equipo={partido.local} rol="Local" />
        <ColumnaEquipo equipo={partido.visitante} rol="Visitante" />
      </div>
    </div>
  )
}
