import { useCallback, useState } from 'react'
import { useParams } from 'react-router'
import { getEquipo, listJugadores, listPartidosDeEquipo } from '../api/endpoints'
import { POSICIONES } from '../api/enums'
import type { Equipo, Jugador, Posicion } from '../api/types'
import { Cargando, EstadoDatoInvalido, EstadoError, EstadoNoDisponible, EstadoVacio } from '../components/Estados'
import { FifaSearch } from '../components/FifaSearch'
import { CodigoEquipo, FilaPartidoDeEquipo } from '../components/Fixture'
import { Icon } from '../components/Icon'
import { Spinner } from '../components/States'
import { useApi } from '../hooks/useApi'
import { useCursorList } from '../hooks/useCursorList'
import { validarCodigoFifa } from '../lib/fifa'
import { ordenarPorFecha } from '../lib/partido'
import { lineasDelPlantel, NOMBRE_LINEA, nombreCorto } from '../lib/plantel'
import { formatFecha } from '../lib/time'

function Cabecera({ codigo }: { codigo: string }) {
  const ficha = useApi(`equipo:${codigo}`, (s) => getEquipo(codigo, s))
  const r = ficha.result

  if (!r) {
    return (
      <section className="equipo-hero equipo-hero-cargando" aria-label={`Equipo ${codigo}`}>
        <CodigoEquipo codigo={codigo} tamano="lg" />
        <div className="equipo-hero-texto">
          <h1>{codigo}</h1>
          <Cargando lineas={2} etiqueta="Cargando la ficha…" />
        </div>
      </section>
    )
  }
  if (!r.ok) {
    return (
      <section className="card card-pad" aria-labelledby="equipo-titulo">
        <h1 id="equipo-titulo" className="titulo-seccion">
          Equipo {codigo}
        </h1>
        <EstadoError error={r.error} onRetry={ficha.reload} recurso="la ficha de ese equipo" que="la ficha del equipo" buscarEquipo />
      </section>
    )
  }
  return <Hero equipo={r.data} />
}

function Hero({ equipo }: { equipo: Equipo }) {
  const colores = [equipo.colores?.principal, equipo.colores?.alternativo].filter(
    (c): c is string => typeof c === 'string' && c.trim() !== '',
  )
  return (
    <section className="equipo-hero" aria-labelledby="equipo-titulo">
      <div className="equipo-hero-id">
        <CodigoEquipo codigo={equipo.codigo} tamano="lg" />
        <div className="equipo-hero-texto">
          <ul className="equipo-hero-chips" aria-label="Datos del equipo">
            <li>{equipo.confederacion}</li>
            <li>Grupo {equipo.grupo}</li>
          </ul>
          <h1 id="equipo-titulo">{equipo.nombre}</h1>
          <p className="equipo-hero-sub">
            {equipo.entrenador ? (
              <>
                Director técnico: <strong>{equipo.entrenador}</strong>
              </>
            ) : (
              'Director técnico sin informar'
            )}
            {colores.length > 0 && (
              <>
                <span className="sep" aria-hidden="true" />
                Colores: {colores.join(' y ')}
              </>
            )}
          </p>
        </div>
      </div>
      <dl className="equipo-hero-datos">
        <div>
          <dt>Ranking FIFA</dt>
          <dd className="num">{equipo.rankingFifa}</dd>
        </div>
        <div>
          <dt>Grupo</dt>
          <dd>{equipo.grupo}</dd>
        </div>
        <div>
          <dt>Jugadores</dt>
          <dd className="num">{equipo.cantidadJugadores ?? '—'}</dd>
        </div>
        <div>
          <dt>Sede</dt>
          <dd className="dd-texto">{equipo.sede ?? '—'}</dd>
        </div>
      </dl>
    </section>
  )
}

function TarjetaJugador({ j }: { j: Jugador }) {
  return (
    <li className="jugador" title={`${j.nombre} ${j.apellido}`}>
      <span className="jugador-dorsal num">{j.dorsal}</span>
      <span className="jugador-texto">
        <span className="jugador-nombre">{nombreCorto(j)}</span>
        <span className="jugador-sub num">Nac. {formatFecha(j.fechaNacimiento)}</span>
      </span>
    </li>
  )
}

function Plantel({ codigo }: { codigo: string }) {
  const [posicion, setPosicion] = useState<Posicion | null>(null)
  const fetchPage = useCallback(
    (cursor: string | null, signal: AbortSignal) => listJugadores(codigo, { posicion, limit: 24, cursor }, signal),
    [codigo, posicion],
  )
  const lista = useCursorList<Jugador>(`plantel:${codigo}:${posicion ?? '*'}`, fetchPage, (j) => j.dni)
  const lineas = lineasDelPlantel(lista.items)

  return (
    <section className="card" aria-labelledby="plantel-titulo">
      <header className="card-head">
        <div>
          <h2 id="plantel-titulo">Plantel</h2>
          <p className="card-sub">Convocados ordenados por línea y dorsal</p>
        </div>
        {!lista.loading && !lista.error && (
          <span className="tag num" aria-live="polite">
            {lista.items.length} {lista.items.length === 1 ? 'jugador' : 'jugadores'}
            {lista.hasMore ? ' (hay más)' : ''}
          </span>
        )}
      </header>
      <div className="card-body">
        {!lista.error && (
          <fieldset className="chips-filtro">
            <legend className="sr-only">Filtrar por posición</legend>
            {[null, ...POSICIONES].map((p) => (
              <label key={p ?? 'todas'} className={posicion === p ? 'chip-filtro activo' : 'chip-filtro'}>
                <input type="radio" name="posicion" checked={posicion === p} onChange={() => setPosicion(p)} />
                {p ? NOMBRE_LINEA[p] : 'Todas'}
              </label>
            ))}
          </fieldset>
        )}

        {lista.loading ? (
          <Cargando lineas={6} etiqueta="Cargando el plantel…" />
        ) : lista.error ? (
          <EstadoError error={lista.error} onRetry={lista.reload} recurso="el plantel de ese equipo" que="el plantel" />
        ) : lineas.length === 0 ? (
          <EstadoVacio titulo={posicion ? `Sin ${NOMBRE_LINEA[posicion].toLowerCase()} en el plantel` : 'El plantel está vacío'} icono="users">
            El equipo existe, pero no tiene jugadores cargados{posicion ? ' en esa posición' : ''}.
          </EstadoVacio>
        ) : (
          <>
            {lineas.map((l) => (
              <div key={l.posicion} className="linea">
                <h3 className="label-titulo">{l.titulo}</h3>
                <ul className="jugadores">
                  {l.jugadores.map((j) => (
                    <TarjetaJugador key={j.dni} j={j} />
                  ))}
                </ul>
              </div>
            ))}
            {lista.hasMore && (
              <div className="card-acciones">
                <button type="button" className="btn btn-secondary" onClick={lista.loadMore} disabled={lista.loadingMore}>
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

function Partidos({ codigo }: { codigo: string }) {
  const { result, reload } = useApi(`partidos-eq:${codigo}`, (s) => listPartidosDeEquipo(codigo, 20, s))
  return (
    <section className="card" aria-labelledby="partidos-titulo">
      <header className="card-head">
        <h2 id="partidos-titulo" className="con-icono">
          <Icon name="calendar" size={20} />
          Partidos en el Mundial 2030
        </h2>
      </header>
      <div className="card-body">
        {!result ? (
          <Cargando lineas={4} etiqueta="Cargando los partidos…" />
        ) : !result.ok ? (
          <EstadoError error={result.error} onRetry={reload} recurso="partidos de ese equipo" que="los partidos" compacto />
        ) : result.data.items.length === 0 ? (
          <EstadoVacio titulo="Sin partidos" icono="ball" compacto>
            Este equipo todavía no tiene partidos en el fixture.
          </EstadoVacio>
        ) : (
          <ul className="lista-partidos">
            {ordenarPorFecha(result.data.items).map((p) => (
              <li key={p.partidoId}>
                <FilaPartidoDeEquipo p={p} codigo={codigo} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

export function EquipoPage() {
  const { codigo: raw = '' } = useParams()
  const valido = validarCodigoFifa(raw)

  if (!valido.ok) {
    return (
      <div className="page">
        <section className="card card-pad" aria-labelledby="equipo-titulo">
          <h1 id="equipo-titulo" className="titulo-seccion">
            Buscar equipo
          </h1>
          <EstadoDatoInvalido accion={<FifaSearch valorInicial={raw} etiqueta="Código FIFA del equipo" />}>
            <p>
              “{raw}” no es un código FIFA. {valido.mensaje}
            </p>
          </EstadoDatoInvalido>
        </section>
      </div>
    )
  }
  return <EquipoValido codigo={valido.codigo} />
}

function EquipoValido({ codigo }: { codigo: string }) {
  return (
    <div className="page">
      <Cabecera codigo={codigo} />
      <div className="grid-equipo">
        <div className="col-principal">
          <Plantel codigo={codigo} />
          <EstadoNoDisponible titulo="Formación titular y posiciones del grupo">
            Todavía no se publican el once titular, la tabla de posiciones ni los goles a favor y en contra.
          </EstadoNoDisponible>
        </div>
        <aside className="col-lateral">
          <Partidos codigo={codigo} />
        </aside>
      </div>
    </div>
  )
}
