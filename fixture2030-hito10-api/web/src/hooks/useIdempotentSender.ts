import { useCallback, useRef, useState } from 'react'
import type { ApiResult } from '../api/client'
import { nuevaIdempotencyKey } from '../lib/idempotency'

export type ModoEnvio = 'nuevo' | 'reenvio' | 'reuso'

export interface Envio<R> {
  n: number
  hora: string
  modo: ModoEnvio
  key: string
  result: ApiResult<R>
}

export interface IdempotentSender<B, R> {
  sending: boolean
  envios: Envio<R>[]
  last: Envio<R> | null
  /** Clave y cuerpo del último envío (lo que "reenviar" repite tal cual). */
  ultimaRequest: { key: string; body: B } | null
  /** Envía con una clave nueva; con `reusarClave` usa la del último envío (para mostrar 409). */
  enviar: (body: B, opciones?: { reusarClave?: boolean }) => Promise<ApiResult<R>>
  /** Repite exactamente la última request (misma clave y mismo cuerpo). */
  reenviar: () => Promise<ApiResult<R> | null>
  limpiar: () => void
}

/**
 * Envíos con `Idempotency-Key`: una clave nueva por envío y la posibilidad de
 * repetir la misma request para demostrar 201 → 200 + Idempotent-Replayed.
 */
export function useIdempotentSender<B, R>(
  send: (key: string, body: B) => Promise<ApiResult<R>>,
  prefijo: string,
): IdempotentSender<B, R> {
  const [envios, setEnvios] = useState<Envio<R>[]>([])
  const [sending, setSending] = useState(false)
  const [ultimaRequest, setUltima] = useState<{ key: string; body: B } | null>(null)
  const contador = useRef(0)

  const ejecutar = useCallback(
    async (key: string, body: B, modo: ModoEnvio) => {
      setSending(true)
      setUltima({ key, body })
      try {
        const result = await send(key, body)
        contador.current += 1
        const envio: Envio<R> = {
          n: contador.current,
          hora: new Date().toLocaleTimeString('es-AR', { hour12: false }),
          modo,
          key,
          result,
        }
        setEnvios((prev) => [envio, ...prev].slice(0, 12))
        return result
      } finally {
        setSending(false)
      }
    },
    [send],
  )

  const enviar = useCallback(
    (body: B, opciones?: { reusarClave?: boolean }) => {
      const reusar = opciones?.reusarClave === true && ultimaRequest !== null
      const key = reusar && ultimaRequest ? ultimaRequest.key : nuevaIdempotencyKey(prefijo)
      return ejecutar(key, body, reusar ? 'reuso' : 'nuevo')
    },
    [ejecutar, prefijo, ultimaRequest],
  )

  const reenviar = useCallback(async () => {
    if (!ultimaRequest) return null
    return ejecutar(ultimaRequest.key, ultimaRequest.body, 'reenvio')
  }, [ejecutar, ultimaRequest])

  const limpiar = useCallback(() => {
    setEnvios([])
    setUltima(null)
  }, [])

  return { sending, envios, last: envios[0] ?? null, ultimaRequest, enviar, reenviar, limpiar }
}
