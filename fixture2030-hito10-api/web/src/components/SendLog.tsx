import type { Envio, ModoEnvio } from '../hooks/useIdempotentSender'
import { HttpBadge } from './Badges'
import { CopyButton } from './RequestId'

const ETIQUETA_MODO: Record<ModoEnvio, string> = {
  nuevo: 'Clave nueva',
  reenvio: 'Reenvío idéntico',
  reuso: 'Misma clave, otro cuerpo',
}

function resultado<R>(e: Envio<R>): string {
  const r = e.result
  if (r.ok) {
    if (r.meta.status === 201) return 'Creado'
    if (r.meta.replayed) return 'Reintento reconocido (no duplicó)'
    return 'OK'
  }
  return r.error.code
}

/** Historial de envíos idempotentes: muestra clave, status e Idempotent-Replayed lado a lado. */
export function SendLog<R>({ envios, caption }: { envios: Envio<R>[]; caption: string }) {
  if (envios.length === 0) return null
  return (
    <div className="table-wrap">
      <table className="table compact">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Hora</th>
            <th scope="col">Modo</th>
            <th scope="col">Idempotency-Key</th>
            <th scope="col">Status</th>
            <th scope="col">Idempotent-Replayed</th>
            <th scope="col">Resultado</th>
            <th scope="col">X-Request-Id</th>
          </tr>
        </thead>
        <tbody>
          {envios.map((e) => {
            const status = e.result.ok ? e.result.meta.status : e.result.error.status
            const requestId = e.result.ok ? e.result.meta.requestId : e.result.error.requestId
            const replayed = e.result.ok ? e.result.meta.replayed : false
            return (
              <tr key={e.n}>
                <td className="num">{e.n}</td>
                <td className="num">{e.hora}</td>
                <td>{ETIQUETA_MODO[e.modo]}</td>
                <td>
                  <code className="mono truncate" title={e.key}>
                    {e.key}
                  </code>
                </td>
                <td>
                  <HttpBadge status={status} />
                </td>
                <td>{replayed ? <strong className="text-ok">true</strong> : <span className="muted">—</span>}</td>
                <td>{resultado(e)}</td>
                <td>
                  {requestId ? (
                    <span className="reqid inline">
                      <code className="mono truncate" title={requestId}>
                        {requestId}
                      </code>
                      <CopyButton value={requestId} label="el request id" />
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
