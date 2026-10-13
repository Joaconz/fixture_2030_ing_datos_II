import { useCallback, useState, type FormEvent } from 'react'
import type { ApiResult } from '../../api/client'
import { cerrarPartido, registrarEvento } from '../../api/endpoints'
import { CONDICIONES, ETIQUETA_CONDICION, ETIQUETA_TIPO, TIPOS_EVENTO } from '../../api/enums'
import type { Condicion, EventoNuevo, PartidoDetalle, TipoEvento } from '../../api/types'
import { HttpBadge, SourceBadge } from '../../components/Badges'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorPanel } from '../../components/ErrorPanel'
import { Icon } from '../../components/Icon'
import { Panel } from '../../components/Panel'
import { RequestId } from '../../components/RequestId'
import { SendLog } from '../../components/SendLog'
import { Spinner } from '../../components/States'
import { useIdempotentSender } from '../../hooks/useIdempotentSender'

export type CambioMesa = 'evento' | 'cierre'

interface Props {
  partido: PartidoDetalle
  onChange: (c: CambioMesa) => void
}

function FormEvento({ partido, onChange }: Props) {
  const id = partido.partidoId
  const [tipo, setTipo] = useState<TipoEvento>('GOL')
  const [minuto, setMinuto] = useState('88')
  const [condicion, setCondicion] = useState<Condicion | ''>('LOCAL')
  const [dorsal, setDorsal] = useState('9')
  const [reusar, setReusar] = useState(false)
  const [errorLocal, setErrorLocal] = useState<string | null>(null)

  const send = useCallback((key: string, body: EventoNuevo) => registrarEvento(id, key, body), [id])
  const sender = useIdempotentSender(send, 'evt')
  const ultimo = sender.last

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const min = Number(minuto)
    if (minuto.trim() === '' || !Number.isInteger(min)) {
      setErrorLocal('El minuto tiene que ser un número entero.')
      document.getElementById('ev-minuto')?.focus()
      return
    }
    const dor = dorsal.trim() === '' ? null : Number(dorsal)
    if (dor !== null && !Number.isInteger(dor)) {
      setErrorLocal('El dorsal tiene que ser un número entero o quedar vacío.')
      document.getElementById('ev-dorsal')?.focus()
      return
    }
    setErrorLocal(null)
    // Rango de minuto/dorsal y reglas por tipo: las valida la API (400 con detalle o 409).
    const body: EventoNuevo = {
      tipo,
      minuto: min,
      condicionEquipo: condicion === '' ? null : condicion,
      dorsalProtagonista: dor,
    }
    const r = await sender.enviar(body, { reusarClave: reusar })
    if (r.ok) onChange('evento')
  }

  async function onReenviar() {
    const r = await sender.reenviar()
    if (r?.ok) onChange('evento')
  }

  return (
    <Panel title="Registrar evento" id="registrar-evento" level={3} badges={<SourceBadge fuente="Neo4j" rol="escritura validada (N8)" />}>
      <form onSubmit={onSubmit} noValidate className="form">
        <div className="form-row">
          <div className="field">
            <label htmlFor="ev-tipo">Tipo</label>
            <select id="ev-tipo" value={tipo} onChange={(e) => setTipo(TIPOS_EVENTO.find((t) => t === e.target.value) ?? 'GOL')}>
              {TIPOS_EVENTO.map((t) => (
                <option key={t} value={t}>
                  {ETIQUETA_TIPO[t]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="ev-minuto">Minuto</label>
            <input
              id="ev-minuto"
              type="number"
              inputMode="numeric"
              min={0}
              max={130}
              step={1}
              className="mono"
              value={minuto}
              onChange={(e) => setMinuto(e.target.value)}
              aria-describedby="ev-minuto-ayuda"
            />
            <p id="ev-minuto-ayuda" className="help">
              0 a 130.
            </p>
          </div>
        </div>
        <div className="form-row">
          <div className="field">
            <label htmlFor="ev-condicion">Condición del equipo</label>
            <select
              id="ev-condicion"
              value={condicion}
              onChange={(e) => setCondicion(CONDICIONES.find((c) => c === e.target.value) ?? '')}
            >
              <option value="">Sin equipo</option>
              {CONDICIONES.map((c) => (
                <option key={c} value={c}>
                  {ETIQUETA_CONDICION[c]} ({c === 'LOCAL' ? partido.local.equipoCodigo : partido.visitante.equipoCodigo})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="ev-dorsal">Dorsal del protagonista</label>
            <input
              id="ev-dorsal"
              type="number"
              inputMode="numeric"
              min={1}
              max={99}
              step={1}
              className="mono"
              value={dorsal}
              onChange={(e) => setDorsal(e.target.value)}
              aria-describedby="ev-dorsal-ayuda"
            />
            <p id="ev-dorsal-ayuda" className="help">
              Opcional según el tipo.
            </p>
          </div>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={reusar}
            onChange={(e) => setReusar(e.target.checked)}
            disabled={!sender.ultimaRequest}
          />
          <span>
            Usar la clave del último envío con este cuerpo (demuestra <code className="mono">409 IDEMPOTENCY_KEY_REUSED</code>)
          </span>
        </label>
        {errorLocal && (
          <p className="field-error" role="alert">
            {errorLocal}
          </p>
        )}
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={sender.sending}>
            {sender.sending ? <Spinner /> : <Icon name="send" size={16} />}
            Registrar evento
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
        {sender.ultimaRequest && (
          <p className="help">
            Última <code className="mono">Idempotency-Key</code>: <code className="mono">{sender.ultimaRequest.key}</code>
          </p>
        )}
      </form>

      {ultimo && (
        <div className="result" aria-live="polite">
          {ultimo.result.ok ? (
            <div className={`result-ok ${ultimo.result.meta.replayed ? 'replayed' : ''}`}>
              <p className="result-title">
                <HttpBadge status={ultimo.result.meta.status} />
                {ultimo.result.meta.status === 201 ? 'Evento registrado' : 'Reintento reconocido: no se duplicó'}
                {ultimo.result.meta.replayed ? <code className="mono chip">Idempotent-Replayed: true</code> : null}
              </p>
              <p className="small">
                <span className="muted">eventoId</span> <code className="mono">{ultimo.result.data.eventoId}</code>
                <span className="muted"> · secuencia</span> <strong className="num">{ultimo.result.data.secuencia}</strong>
              </p>
              <RequestId id={ultimo.result.meta.requestId} />
            </div>
          ) : (
            <ErrorPanel error={ultimo.result.error} compact />
          )}
        </div>
      )}
      <SendLog envios={sender.envios} caption="Envíos de la mesa (más reciente primero)" />
    </Panel>
  )
}

function CierrePartido({ partido, onChange }: Props) {
  const [confirmar, setConfirmar] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<ApiResult<PartidoDetalle> | null>(null)

  async function cerrar() {
    setConfirmar(false)
    setEnviando(true)
    try {
      const r = await cerrarPartido(partido.partidoId)
      setResultado(r)
      if (r.ok) onChange('cierre')
    } finally {
      setEnviando(false)
    }
  }

  const finalizado = partido.estado === 'FINALIZADO'

  return (
    <Panel title="Cerrar partido" id="cerrar" level={3} badges={<SourceBadge fuente="Neo4j" rol="transacción de escritura" />}>
      <p>
        Pasa el partido de <strong>PROGRAMADO</strong> a <strong>FINALIZADO</strong>. Exige un evento{' '}
        <code className="mono">FIN_PARTIDO</code>; el marcador lo calcula la API contando los <code className="mono">GOL</code>.
        No es idempotente a propósito: repetirlo responde <code className="mono">409</code>.
      </p>
      {finalizado && (
        <p className="note note-ok" role="status">
          <Icon name="check" size={16} />
          <span>El partido ya está FINALIZADO. Un nuevo intento debería responder 409 INVALID_TRANSITION.</span>
        </p>
      )}
      <div className="form-actions">
        <button type="button" className="btn btn-danger" onClick={() => setConfirmar(true)} disabled={enviando}>
          {enviando ? <Spinner /> : <Icon name="flag" size={16} />}
          {finalizado ? 'Intentar cerrar otra vez' : 'Cerrar partido'}
        </button>
      </div>

      {resultado && (
        <div className="result" aria-live="polite">
          {resultado.ok ? (
            <div className="result-ok">
              <p className="result-title">
                <HttpBadge status={resultado.meta.status} />
                Partido cerrado: {resultado.data.local.equipoCodigo}{' '}
                {resultado.data.marcador ? `${resultado.data.marcador.golesLocal} – ${resultado.data.marcador.golesVisitante}` : ''}{' '}
                {resultado.data.visitante.equipoCodigo}
              </p>
              <p className="small muted">Se invalidó la caché del detalle: el próximo pedido debería ser X-Cache: MISS.</p>
              <RequestId id={resultado.meta.requestId} />
            </div>
          ) : (
            <ErrorPanel error={resultado.error} compact />
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirmar}
        title={`¿Cerrar ${partido.partidoId}?`}
        confirmLabel="Sí, cerrar partido"
        destructive
        onConfirm={() => void cerrar()}
        onCancel={() => setConfirmar(false)}
      >
        <p>
          {partido.local.nombre} vs {partido.visitante.nombre} pasará a FINALIZADO y ya no aceptará eventos. Esta
          transición no se puede deshacer desde la API.
        </p>
      </ConfirmDialog>
    </Panel>
  )
}

export function MesaControlPanel({ partido, onChange }: Props) {
  return (
    <section className="stack" aria-labelledby="mesa-titulo">
      <div className="section-head">
        <h2 id="mesa-titulo" className="section-title">
          Mesa de control
        </h2>
        <p className="muted small">Operador del partido: registra eventos y cierra el partido. Cada respuesta de error muestra su code.</p>
      </div>
      <div className="grid-2 grid-form">
        <FormEvento partido={partido} onChange={onChange} />
        <CierrePartido partido={partido} onChange={onChange} />
      </div>
    </section>
  )
}
