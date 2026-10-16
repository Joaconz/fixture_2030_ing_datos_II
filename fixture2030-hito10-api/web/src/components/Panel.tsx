import type { ReactNode } from 'react'
import type { ResponseMeta } from '../api/client'
import { HttpBadge } from './Badges'
import { Icon } from './Icon'
import { RequestId } from './RequestId'

interface PanelProps {
  title: string
  /** Nivel del encabezado (h2 por defecto). */
  level?: 2 | 3
  id?: string
  badges?: ReactNode
  actions?: ReactNode
  meta?: ResponseMeta | null
  children: ReactNode
  className?: string
}

/** Tarjeta de datos: título + badges de fuente + acciones + pie con status y X-Request-Id. */
export function Panel({ title, level = 2, id, badges, actions, meta, children, className }: PanelProps) {
  const H = level === 2 ? 'h2' : 'h3'
  const headingId = id ? `${id}-titulo` : undefined
  return (
    <section className={className ? `panel ${className}` : 'panel'} aria-labelledby={headingId} id={id}>
      <header className="panel-head">
        <div className="panel-title">
          <H id={headingId}>{title}</H>
          {badges ? <div className="badge-row">{badges}</div> : null}
        </div>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </header>
      <div className="panel-body">{children}</div>
      {meta ? <MetaFooter meta={meta} /> : null}
    </section>
  )
}

export function MetaFooter({ meta }: { meta: ResponseMeta }) {
  return (
    <footer className="panel-foot">
      <HttpBadge status={meta.status} />
      <span className="muted small">
        <Icon name="clock" size={14} /> {meta.durationMs} ms
      </span>
      <RequestId id={meta.requestId} />
    </footer>
  )
}
