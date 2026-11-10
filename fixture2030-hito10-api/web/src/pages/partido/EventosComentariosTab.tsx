import { useCallback, useState, type FormEvent } from 'react'
import { listComentarios, listEventos, publicarComentario } from '../../api/endpoints'
import { ETIQUETA_TIPO, TIPOS_EVENTO } from '../../api/enums'
import type { Comentario, ComentarioNuevo, Evento, PartidoDetalle, TipoEvento } from '../../api/types'
import { Cargando, EstadoError, EstadoVacio } from '../../components/Estados'
import { Icon, type IconName } from '../../components/Icon'
import { Spinner } from '../../components/States'
import { useCursorList } from '../../hooks/useCursorList'
import { useIdempotentSender } from '../../hooks/useIdempotentSender'
import { equipoDeEvento, familiaEvento, TIPOS_DESTACADOS, tituloEvento, type FamiliaEvento } from '../../lib/partido'
import { addMinutes, formatHoraUtc } from '../../lib/time'

const ICONO_FAMILIA: Record<FamiliaEvento, IconName> = {
  gol: 'ball',
  amarilla: 'card',
  roja: 'card',
  cambio: 'swap',
  marco: 'flag',
  juego: 'activity',
}

const CHIP_TIPO: Partial<Record<TipoEvento, string>> = {
  GOL: 'Goles',
  TARJETA_AMARILLA: 'Amarillas',
  TARJETA_ROJA: 'Rojas',
  SUSTITUCION: 'Cambios',
}

const OTROS_TIPOS = TIPOS_EVENTO.filter((t) => !TIPOS_DESTACADOS.includes(t))

function ItemEvento({ ev, partido }: { ev: Evento; partido: PartidoDetalle }) {
  const fam = familiaEvento(ev.tipo)
  const equipo = equipoDeEvento(ev, partido)
  const esMarco = fam === 'marco'
  return (
    <li className={`ev ev-${fam}`}>
      <span className="ev-minuto num">
        {ev.minuto}′<span className="sr-only">, </span>
      </span>
      <span className="ev-icono" aria-hidden="true">
        <Icon name={ICONO_FAMILIA[fam]} size={16} />
      </span>
      <div className="ev-tarjeta">
        <p className="ev-titulo">{esMarco ? ETIQUETA_TIPO[ev.tipo] : tituloEvento(ev)}</p>
        {equipo && !esMarco ? (
          <span className={`ev-equipo ${ev.condicionEquipo === 'LOCAL' ? 'ev-equipo-local' : 'ev-equipo-visitante'}`}>
            <span className="sr-only">Equipo: </span>
            {equipo.codigo}
          </span>
        ) : null}
      </div>
    </li>
  )
}

function Eventos({ partido }: { partido: PartidoDetalle }) {
  const [tipo, setTipo] = useState<TipoEvento | null>(null)
  const id = partido.partidoId
  const fetchPage = useCallback(
    (cursor: string | null, signal: AbortSignal) => listEventos(id, { tipo, limit: 30, cursor }, signal),
    [id, tipo],
  )
  const lista = useCursorList<Evento>(`eventos:${id}:${tipo ?? '*'}`, fetchPage, (e) => e.eventoId)
  const otroSeleccionado = tipo !== null && !TIPOS_DESTACADOS.includes(tipo)

  return (
    <section className="col-eventos" aria-labelledby="eventos-titulo">
      <h2 id="eventos-titulo" className="sr-only">
        Eventos del partido
      </h2>
      <div className="barra-filtros">
        <fieldset className="chips-filtro">
          <legend className="sr-only">Filtrar eventos por tipo</legend>
          <label className={tipo === null ? 'chip-filtro activo' : 'chip-filtro'}>
            <input type="radio" name="tipo-evento" checked={tipo === null} onChange={() => setTipo(null)} />
            Todos
          </label>
          {TIPOS_DESTACADOS.map((t) => (
            <label key={t} className={tipo === t ? 'chip-filtro activo' : 'chip-filtro'}>
              <input type="radio" name="tipo-evento" checked={tipo === t} onChange={() => setTipo(t)} />
              {CHIP_TIPO[t] ?? ETIQUETA_TIPO[t]}
            </label>
          ))}
        </fieldset>
        <label className="select-compacto">
          <span className="sr-only">Otros tipos de evento</span>
          <select
            value={otroSeleccionado ? tipo : ''}
            onChange={(e) => setTipo(OTROS_TIPOS.find((t) => t === e.target.value) ?? null)}
            className={otroSeleccionado ? 'activo' : undefined}
          >
            <option value="">Otros tipos…</option>
            {OTROS_TIPOS.map((t) => (
              <option key={t} value={t}>
                {ETIQUETA_TIPO[t]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="card card-timeline">
        {lista.loading ? (
          <Cargando lineas={6} etiqueta="Cargando los eventos…" />
        ) : lista.error ? (
          <EstadoError error={lista.error} onRetry={lista.reload} recurso="ese partido" que="los eventos" />
        ) : lista.items.length === 0 ? (
          tipo === null ? (
            <EstadoVacio titulo="Este partido todavía no tiene eventos" icono="list">
              {partido.estado === 'PROGRAMADO'
                ? 'Todavía no se jugó: los eventos aparecen a medida que se registran.'
                : 'No hay eventos registrados para este partido.'}
            </EstadoVacio>
          ) : (
            <EstadoVacio
              titulo={`Sin eventos de tipo “${ETIQUETA_TIPO[tipo]}”`}
              icono="list"
              accion={
                <button type="button" className="btn-link" onClick={() => setTipo(null)}>
                  Ver todos los eventos
                </button>
              }
            />
          )
        ) : (
          <>
            <p className="orden-nota">Orden cronológico</p>
            <ol className="timeline-ev">
              {lista.items.map((ev) => (
                <ItemEvento key={ev.eventoId} ev={ev} partido={partido} />
              ))}
            </ol>
            {lista.hasMore && (
              <div className="card-acciones">
                <button type="button" className="btn btn-secondary" onClick={lista.loadMore} disabled={lista.loadingMore}>
                  {lista.loadingMore ? <Spinner label="Cargando…" /> : 'Ver más eventos'}
                </button>
              </div>
            )}
            {lista.moreError && <EstadoError error={lista.moreError} onRetry={lista.loadMore} que="más eventos" compacto />}
          </>
        )}
      </div>
    </section>
  )
}

function iniciales(texto: string): string {
  const limpio = texto.replace(/[^\p{L}\p{N}]+/gu, ' ').trim()
  const partes = limpio.split(' ').filter(Boolean)
  const a = partes[0]?.charAt(0) ?? '?'
  const b = partes[1]?.charAt(0) ?? partes[0]?.charAt(1) ?? ''
  return `${a}${b}`.toUpperCase()
}

function hinchadaDe(c: Comentario, p: PartidoDetalle): string | null {
  if (c.hinchada === 'LOCAL') return p.local.equipoCodigo
  if (c.hinchada === 'VISITANTE') return p.visitante.equipoCodigo
  if (c.hinchada === 'NEUTRAL') return 'Neutral'
  return null
}

function ItemComentario({ c, partido }: { c: Comentario; partido: PartidoDetalle }) {
  const nombre = c.alias ?? c.usuarioId
  const hinchada = hinchadaDe(c, partido)
  return (
    <li className="comentario">
      <span className="comentario-avatar" aria-hidden="true">
        {iniciales(nombre)}
      </span>
      <div className="comentario-cuerpo">
        <p className="comentario-cabecera">
          <strong>{nombre}</strong>
          {hinchada ? <span className="tag tag-sm">{hinchada}</span> : null}
          {typeof c.minutoPartido === 'number' ? (
            <span className="comentario-minuto num">
              <span className="sr-only">Minuto </span>
              {c.minutoPartido}′
            </span>
          ) : (
            <time className="comentario-minuto num" dateTime={c.creadoEn}>
              {formatHoraUtc(c.creadoEn)}
            </time>
          )}
        </p>
        <p className="comentario-texto">{c.contenido}</p>
      </div>
    </li>
  )
}

/** Comentarios del partido (CU8) y alta idempotente (CU9). */
function Comentarios({ partido }: { partido: PartidoDetalle }) {
  const id = partido.partidoId
  const [version, setVersion] = useState(0)
  const fetchPage = useCallback(
    (cursor: string | null, signal: AbortSignal) => listComentarios(id, { limit: 15, cursor }, signal),
    [id],
  )
  const lista = useCursorList<Comentario>(`comentarios:${id}:${version}`, fetchPage, (c) => c.comentarioId)

  const [alias, setAlias] = useState('hincha42')
  const [usuarioId, setUsuarioId] = useState('USR-0000042')
  const [contenido, setContenido] = useState('')
  const [minuto, setMinuto] = useState('47')
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [aviso, setAviso] = useState<string | null>(null)

  const send = useCallback((key: string, body: ComentarioNuevo) => publicarComentario(id, key, body), [id])
  const sender = useIdempotentSender(send, 'com')
  const ultimo = sender.last

  function validar(): Record<string, string> {
    const e: Record<string, string> = {}
    if (alias.trim() === '') e.alias = 'Escribí cómo querés aparecer.'
    if (!/^USR-[0-9A-Za-z]{1,16}$/.test(usuarioId.trim())) e.usuarioId = 'Formato USR- seguido de números, por ejemplo USR-0000042.'
    if (contenido.trim() === '') e.contenido = 'El comentario no puede estar vacío.'
    const m = Number(minuto)
    if (minuto.trim() === '' || !Number.isInteger(m) || m < 0 || m > 125) e.minuto = 'Un minuto entre 0 y 125.'
    return e
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault()
    setAviso(null)
    const e = validar()
    setErrores(e)
    const primero = Object.keys(e)[0]
    if (primero) {
      document.getElementById(`com-${primero}`)?.focus()
      return
    }
    const m = Number(minuto)
    // Reloj del torneo simulado: el comentario se fecha en el minuto elegido del partido.
    const r = await sender.enviar({
      usuarioId: usuarioId.trim(),
      alias: alias.trim(),
      contenido: contenido.trim(),
      creadoEn: addMinutes(partido.fechaHora, m),
      minutoPartido: m,
    })
    if (r.ok) {
      setContenido('')
      setAviso(r.meta.replayed ? 'Ese comentario ya estaba publicado: no se duplicó.' : 'Comentario publicado.')
      setVersion((v) => v + 1)
    }
  }

  async function reintentar() {
    // Misma Idempotency-Key y mismo cuerpo: si el primer envío llegó, no se duplica.
    const r = await sender.reenviar()
    if (r?.ok) {
      setContenido('')
      setAviso(r.meta.replayed ? 'Ese comentario ya estaba publicado: no se duplicó.' : 'Comentario publicado.')
      setVersion((v) => v + 1)
    }
  }

  return (
    <section className="col-comentarios" aria-labelledby="comentarios-titulo">
      <div className="card card-comentarios">
        <header className="card-head card-head-gris">
          <h2 id="comentarios-titulo" className="con-icono">
            <Icon name="message" size={20} />
            Comentarios
          </h2>
          {!lista.loading && !lista.error && (
            <span className="tag num">
              {lista.items.length}
              {lista.hasMore ? '+' : ''} {lista.items.length === 1 ? 'aporte' : 'aportes'}
            </span>
          )}
        </header>

        <div className="comentarios-lista">
          {lista.loading ? (
            <Cargando lineas={5} etiqueta="Cargando los comentarios…" />
          ) : lista.error ? (
            <EstadoError error={lista.error} onRetry={lista.reload} recurso="los comentarios de ese partido" que="los comentarios" />
          ) : lista.items.length === 0 ? (
            <EstadoVacio titulo="Todavía no hay comentarios" icono="message">
              Sé el primero en comentar este partido.
            </EstadoVacio>
          ) : (
            <>
              <ul className="comentarios">
                {lista.items.map((c) => (
                  <ItemComentario key={c.comentarioId} c={c} partido={partido} />
                ))}
              </ul>
              {lista.hasMore && (
                <div className="card-acciones">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={lista.loadMore} disabled={lista.loadingMore}>
                    {lista.loadingMore ? <Spinner label="Cargando…" /> : 'Ver comentarios anteriores'}
                  </button>
                </div>
              )}
              {lista.moreError && (
                <EstadoError error={lista.moreError} onRetry={lista.loadMore} que="más comentarios" compacto />
              )}
            </>
          )}
        </div>

        <form className="comentar" onSubmit={onSubmit} noValidate aria-labelledby="comentar-titulo">
          <h3 id="comentar-titulo" className="sr-only">
            Publicar un comentario
          </h3>
          <div className="comentar-fila">
            <div className="campo">
              <label htmlFor="com-alias">Alias</label>
              <input
                id="com-alias"
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
                maxLength={40}
                autoComplete="nickname"
                aria-invalid={Boolean(errores.alias)}
                aria-describedby={errores.alias ? 'com-alias-error' : undefined}
              />
              {errores.alias && (
                <p id="com-alias-error" className="field-error">
                  {errores.alias}
                </p>
              )}
            </div>
            <div className="campo">
              <label htmlFor="com-usuarioId">Usuario</label>
              <input
                id="com-usuarioId"
                value={usuarioId}
                onChange={(e) => setUsuarioId(e.target.value)}
                autoComplete="off"
                spellCheck={false}
                aria-invalid={Boolean(errores.usuarioId)}
                aria-describedby={errores.usuarioId ? 'com-usuarioId-error' : undefined}
              />
              {errores.usuarioId && (
                <p id="com-usuarioId-error" className="field-error">
                  {errores.usuarioId}
                </p>
              )}
            </div>
          </div>
          <div className="campo">
            <label htmlFor="com-contenido">Tu comentario</label>
            <textarea
              id="com-contenido"
              value={contenido}
              onChange={(e) => setContenido(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="Escribí tu comentario…"
              aria-invalid={Boolean(errores.contenido)}
              aria-describedby={`com-contenido-ayuda${errores.contenido ? ' com-contenido-error' : ''}`}
            />
            <p id="com-contenido-ayuda" className="help num">
              {contenido.length}/500
            </p>
            {errores.contenido && (
              <p id="com-contenido-error" className="field-error">
                {errores.contenido}
              </p>
            )}
          </div>
          <div className="comentar-pie">
            <div className="campo campo-minuto">
              <label htmlFor="com-minuto">Minuto</label>
              <input
                id="com-minuto"
                type="number"
                inputMode="numeric"
                min={0}
                max={125}
                value={minuto}
                onChange={(e) => setMinuto(e.target.value)}
                className="num"
                aria-invalid={Boolean(errores.minuto)}
                aria-describedby={errores.minuto ? 'com-minuto-error' : undefined}
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={sender.sending}>
              {sender.sending ? <Spinner /> : <Icon name="send" size={16} />}
              Publicar
            </button>
          </div>
          {errores.minuto && (
            <p id="com-minuto-error" className="field-error">
              {errores.minuto}
            </p>
          )}
          <div aria-live="polite">
            {aviso && (
              <p className="aviso-ok">
                <Icon name="check" size={16} />
                {aviso}
              </p>
            )}
            {ultimo && !ultimo.result.ok && (
              <EstadoError
                error={ultimo.result.error}
                onRetry={() => void reintentar()}
                que="el comentario"
                compacto
              />
            )}
          </div>
        </form>
      </div>
    </section>
  )
}

export function EventosComentariosTab({ partido }: { partido: PartidoDetalle }) {
  return (
    <div className="grid-eventos">
      <Eventos partido={partido} />
      <Comentarios partido={partido} />
    </div>
  )
}
