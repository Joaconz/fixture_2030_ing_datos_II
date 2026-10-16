import { useCallback, useState, type FormEvent } from 'react'
import { listComentarios, publicarComentario } from '../../api/endpoints'
import type { Comentario, ComentarioNuevo, PartidoDetalle } from '../../api/types'
import { HttpBadge, SourceBadge } from '../../components/Badges'
import { ErrorPanel } from '../../components/ErrorPanel'
import { Icon } from '../../components/Icon'
import { Panel } from '../../components/Panel'
import { RequestId } from '../../components/RequestId'
import { SendLog } from '../../components/SendLog'
import { EmptyState, Skeleton, Spinner } from '../../components/States'
import { useCursorList } from '../../hooks/useCursorList'
import { useIdempotentSender } from '../../hooks/useIdempotentSender'
import { addMinutes, formatFechaHoraUtc, isoToUtcInput, utcInputToIso } from '../../lib/time'

function Lista({ partidoId, version }: { partidoId: string; version: number }) {
  const fetchPage = useCallback(
    (cursor: string | null, signal: AbortSignal) => listComentarios(partidoId, { limit: 10, cursor }, signal),
    [partidoId],
  )
  const lista = useCursorList<Comentario>(`comentarios:${partidoId}:${version}`, fetchPage, (c) => c.comentarioId)

  return (
    <Panel
      title="Comentarios"
      id="comentarios"
      badges={<SourceBadge fuente="Cassandra" rol="del más reciente al más antiguo" />}
      meta={lista.meta}
      actions={
        <button type="button" className="btn btn-ghost btn-sm" onClick={lista.reload} aria-label="Recargar comentarios">
          <Icon name="refresh" size={16} />
        </button>
      }
    >
      {lista.loading ? (
        <Skeleton lines={5} label="Cargando comentarios…" />
      ) : lista.error ? (
        <ErrorPanel error={lista.error} onRetry={lista.reload} recurso={`el partido ${partidoId} en el módulo de comentarios`} />
      ) : lista.items.length === 0 ? (
        <EmptyState title="Todavía no hay comentarios" icon="message">
          Sé el primero en comentar con el formulario.
        </EmptyState>
      ) : (
        <>
          <ul className="comments">
            {lista.items.map((c) => (
              <li key={c.comentarioId} className="comment">
                <div className="comment-head">
                  <strong>{c.alias ?? c.usuarioId}</strong>
                  <span className="muted small mono">{c.usuarioId}</span>
                  {c.hinchada ? <span className="chip">{c.hinchada.toLowerCase()}</span> : null}
                  {c.estadoModeracion !== 'PUBLICADO' ? <span className="chip chip-warn">{c.estadoModeracion}</span> : null}
                </div>
                <p className="comment-body">{c.contenido}</p>
                <p className="muted small">
                  <time dateTime={c.creadoEn}>{formatFechaHoraUtc(c.creadoEn)}</time>
                  {c.minutoPartido !== null && c.minutoPartido !== undefined ? ` · min ${c.minutoPartido}′` : ''}
                  <span aria-hidden="true"> · </span>
                  <span className="mono">{c.comentarioId}</span>
                </p>
              </li>
            ))}
          </ul>
          <div className="list-foot">
            <span className="muted small" aria-live="polite">
              {lista.items.length} comentarios cargados
            </span>
            {lista.hasMore ? (
              <button type="button" className="btn btn-secondary" onClick={lista.loadMore} disabled={lista.loadingMore}>
                {lista.loadingMore ? <Spinner label="Cargando…" /> : 'Cargar anteriores'}
              </button>
            ) : (
              <span className="muted small">No hay comentarios anteriores.</span>
            )}
          </div>
          {lista.moreError && <ErrorPanel error={lista.moreError} onRetry={lista.loadMore} compact />}
        </>
      )}
    </Panel>
  )
}

export function ComentariosPanel({ partido }: { partido: PartidoDetalle }) {
  const id = partido.partidoId
  const [version, setVersion] = useState(0)
  const [usuarioId, setUsuarioId] = useState('USR-0000042')
  const [alias, setAlias] = useState('hincha42')
  const [contenido, setContenido] = useState('')
  const [creadoEn, setCreadoEn] = useState(() => isoToUtcInput(addMinutes(partido.fechaHora, 47)))
  const [faltantes, setFaltantes] = useState<string[]>([])

  const send = useCallback((key: string, body: ComentarioNuevo) => publicarComentario(id, key, body), [id])
  const sender = useIdempotentSender(send, 'com')
  const ultimo = sender.last

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const iso = utcInputToIso(creadoEn)
    const f: string[] = []
    if (usuarioId.trim() === '') f.push('usuarioId')
    if (alias.trim() === '') f.push('alias')
    if (contenido.trim() === '') f.push('contenido')
    if (!iso) f.push('creadoEn')
    setFaltantes(f)
    if (f.length > 0 || !iso) {
      document.getElementById(`com-${f[0]}`)?.focus()
      return
    }
    const r = await sender.enviar({ usuarioId: usuarioId.trim(), alias: alias.trim(), contenido: contenido.trim(), creadoEn: iso })
    if (r.ok) setVersion((v) => v + 1)
  }

  async function onReenviar() {
    const r = await sender.reenviar()
    if (r?.ok) setVersion((v) => v + 1)
  }

  const err = (campo: string) => faltantes.includes(campo)

  return (
    <div className="grid-2 grid-form">
      <Lista partidoId={id} version={version} />

      <Panel title="Publicar comentario" id="publicar" badges={<SourceBadge fuente="Cassandra" rol="LOGGED BATCH" />}>
        <form onSubmit={onSubmit} noValidate className="form">
          <div className="form-row">
            <div className="field">
              <label htmlFor="com-usuarioId">
                usuarioId <span aria-hidden="true">*</span>
              </label>
              <input
                id="com-usuarioId"
                className="mono"
                value={usuarioId}
                onChange={(e) => setUsuarioId(e.target.value)}
                required
                aria-invalid={err('usuarioId')}
                aria-describedby="com-usuarioId-ayuda"
                autoComplete="off"
              />
              <p id="com-usuarioId-ayuda" className="help">
                Formato USR-XXXX.
              </p>
            </div>
            <div className="field">
              <label htmlFor="com-alias">
                Alias <span aria-hidden="true">*</span>
              </label>
              <input
                id="com-alias"
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
                maxLength={40}
                required
                aria-invalid={err('alias')}
                autoComplete="nickname"
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="com-contenido">
              Comentario <span aria-hidden="true">*</span>
            </label>
            <textarea
              id="com-contenido"
              value={contenido}
              onChange={(e) => setContenido(e.target.value)}
              maxLength={500}
              rows={3}
              required
              aria-invalid={err('contenido')}
              aria-describedby="com-contenido-ayuda"
            />
            <p id="com-contenido-ayuda" className="help">
              {contenido.length}/500 caracteres.
            </p>
          </div>
          <div className="field">
            <label htmlFor="com-creadoEn">
              creadoEn (UTC) <span aria-hidden="true">*</span>
            </label>
            <input
              id="com-creadoEn"
              type="datetime-local"
              className="mono"
              value={creadoEn}
              onChange={(e) => setCreadoEn(e.target.value)}
              required
              aria-invalid={err('creadoEn')}
              aria-describedby="com-creadoEn-ayuda"
            />
            <p id="com-creadoEn-ayuda" className="help">
              Reloj del torneo simulado, en UTC. Tiene que caer entre −15′ y +125′ del inicio (
              {formatFechaHoraUtc(partido.fechaHora)}). Precargado en el minuto 47.
            </p>
          </div>
          {faltantes.length > 0 && (
            <p className="field-error" role="alert">
              Completá: {faltantes.join(', ')}.
            </p>
          )}
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={sender.sending}>
              {sender.sending ? <Spinner /> : <Icon name="send" size={16} />}
              Publicar
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void onReenviar()}
              disabled={sender.sending || !sender.ultimaRequest}
              title="Repite exactamente la última request: misma Idempotency-Key y mismo cuerpo"
            >
              <Icon name="repeat" size={16} />
              Reenviar la misma request
            </button>
          </div>
          <p className="help">
            Cada “Publicar” genera una <code className="mono">Idempotency-Key</code> nueva. “Reenviar” repite la última:
            la API responde <strong>200</strong> con <code className="mono">Idempotent-Replayed: true</code> en vez de 201
            y no duplica el comentario.
          </p>
        </form>

        {ultimo && (
          <div className="result" aria-live="polite">
            {ultimo.result.ok ? (
              <div className={`result-ok ${ultimo.result.meta.replayed ? 'replayed' : ''}`}>
                <p className="result-title">
                  <HttpBadge status={ultimo.result.meta.status} />
                  {ultimo.result.meta.status === 201
                    ? 'Comentario creado'
                    : ultimo.result.meta.replayed
                      ? 'Reintento reconocido: no se duplicó'
                      : 'OK'}
                  {ultimo.result.meta.replayed ? <code className="mono chip">Idempotent-Replayed: true</code> : null}
                </p>
                <p className="small">
                  <span className="muted">comentarioId</span> <code className="mono">{ultimo.result.data.comentarioId}</code>
                </p>
                <RequestId id={ultimo.result.meta.requestId} />
              </div>
            ) : (
              <ErrorPanel error={ultimo.result.error} compact />
            )}
          </div>
        )}
        <SendLog envios={sender.envios} caption="Envíos de esta sesión (más reciente primero)" />
      </Panel>
    </div>
  )
}
