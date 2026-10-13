/**
 * Claves de idempotencia para POST de eventos y comentarios.
 * El contrato exige `^[A-Za-z0-9_-]{8,64}$` en la cabecera `Idempotency-Key`.
 *
 * Se usa `crypto.getRandomValues` (no `randomUUID`) porque también existe
 * fuera de contextos seguros (p. ej. el front servido por IP de la LAN).
 */
export const IDEMPOTENCY_KEY_PATTERN = /^[A-Za-z0-9_-]{8,64}$/

export function nuevaIdempotencyKey(prefijo = 'web'): string {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  const clave = `${prefijo}-${hex}`
  if (!IDEMPOTENCY_KEY_PATTERN.test(clave)) {
    throw new Error(`Prefijo inválido para Idempotency-Key: ${prefijo}`)
  }
  return clave
}

export function esIdempotencyKeyValida(clave: string): boolean {
  return IDEMPOTENCY_KEY_PATTERN.test(clave)
}
