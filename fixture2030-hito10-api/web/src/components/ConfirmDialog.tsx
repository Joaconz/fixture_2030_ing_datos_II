import { useEffect, useRef, type ReactNode } from 'react'

interface ConfirmDialogProps {
  open: boolean
  title: string
  children: ReactNode
  confirmLabel: string
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Confirmación modal sobre <dialog> nativo: atrapa el foco, cierra con Escape
 * y devuelve el foco al control que lo abrió. El foco inicial va a "Cancelar".
 */
export function ConfirmDialog({ open, title, children, confirmLabel, destructive, onConfirm, onCancel }: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) {
      d.showModal()
      cancelRef.current?.focus()
    } else if (!open && d.open) {
      d.close()
    }
  }, [open])

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby="confirm-title"
      onCancel={(e) => {
        e.preventDefault()
        onCancel()
      }}
    >
      <h2 id="confirm-title">{title}</h2>
      <div className="dialog-body">{children}</div>
      <div className="dialog-actions">
        <button ref={cancelRef} type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancelar
        </button>
        <button type="button" className={destructive ? 'btn btn-danger' : 'btn btn-primary'} onClick={onConfirm}>
          {confirmLabel}
        </button>
      </div>
    </dialog>
  )
}
