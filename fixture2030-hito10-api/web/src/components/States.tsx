import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="spinner-wrap">
      <span className="spinner" aria-hidden="true" />
      {label ? <span>{label}</span> : null}
    </span>
  )
}

/** Placeholder de carga con altura reservada (evita saltos de layout). */
export function Skeleton({ lines = 3, label = 'Cargando…' }: { lines?: number; label?: string }) {
  return (
    <div className="skeleton" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton-line" style={{ width: `${92 - ((i * 17) % 40)}%` }} aria-hidden="true" />
      ))}
    </div>
  )
}

export function EmptyState({
  icon = 'info',
  title,
  children,
}: {
  icon?: IconName
  title: string
  children?: ReactNode
}) {
  return (
    <div className="empty" role="status">
      <Icon name={icon} size={22} />
      <div>
        <p className="empty-title">{title}</p>
        {children ? <div className="empty-body">{children}</div> : null}
      </div>
    </div>
  )
}
