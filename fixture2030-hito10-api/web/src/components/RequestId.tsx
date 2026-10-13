import { useEffect, useState } from 'react'
import { Icon } from './Icon'

async function copiar(texto: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(texto)
    return true
  } catch {
    // Fallback para contextos sin Clipboard API (http en LAN, permisos).
    const ta = document.createElement('textarea')
    ta.value = texto
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    ta.remove()
    return ok
  }
}

export function CopyButton({ value, label }: { value: string; label: string }) {
  const [copiado, setCopiado] = useState(false)
  useEffect(() => {
    if (!copiado) return
    const t = setTimeout(() => setCopiado(false), 1800)
    return () => clearTimeout(t)
  }, [copiado])
  return (
    <button
      type="button"
      className="btn-icon"
      onClick={() => {
        void copiar(value).then(setCopiado)
      }}
      aria-label={copiado ? `${label}: copiado` : `Copiar ${label}`}
      title={copiado ? 'Copiado' : `Copiar ${label}`}
    >
      <Icon name={copiado ? 'check' : 'copy'} size={16} />
      <span className="sr-only" aria-live="polite">
        {copiado ? 'Copiado' : ''}
      </span>
    </button>
  )
}

/** Muestra el X-Request-Id de una respuesta con botón de copiado. */
export function RequestId({ id, prefix = 'X-Request-Id' }: { id: string | null | undefined; prefix?: string }) {
  if (!id) return null
  return (
    <span className="reqid">
      <span className="reqid-label">{prefix}</span>
      <code className="mono">{id}</code>
      <CopyButton value={id} label="el request id" />
    </span>
  )
}
