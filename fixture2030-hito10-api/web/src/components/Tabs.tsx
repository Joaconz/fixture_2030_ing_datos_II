import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

export interface TabDef<K extends string> {
  key: K
  label: string
  icon?: IconName
}

interface TabsProps<K extends string> {
  tabs: readonly TabDef<K>[]
  value: K
  onChange: (k: K) => void
  label: string
  idPrefix: string
}

/** Pestañas ARIA (tablist) con navegación por flechas, Inicio y Fin. */
export function Tabs<K extends string>({ tabs, value, onChange, label, idPrefix }: TabsProps<K>) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, i: number) {
    let j: number | null = null
    if (e.key === 'ArrowRight') j = (i + 1) % tabs.length
    else if (e.key === 'ArrowLeft') j = (i - 1 + tabs.length) % tabs.length
    else if (e.key === 'Home') j = 0
    else if (e.key === 'End') j = tabs.length - 1
    if (j === null) return
    e.preventDefault()
    const t = tabs[j]
    if (!t) return
    onChange(t.key)
    refs.current[j]?.focus()
  }

  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((t, i) => {
        const activo = t.key === value
        return (
          <button
            key={t.key}
            ref={(el) => {
              refs.current[i] = el
            }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${t.key}`}
            aria-selected={activo}
            aria-controls={`${idPrefix}-panel-${t.key}`}
            tabIndex={activo ? 0 : -1}
            className={activo ? 'tab active' : 'tab'}
            onClick={() => onChange(t.key)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {t.icon ? <Icon name={t.icon} size={16} /> : null}
            {t.label}
          </button>
        )
      })}
    </div>
  )
}

export function TabPanel({ idPrefix, tabKey, children }: { idPrefix: string; tabKey: string; children: ReactNode }) {
  return (
    <div
      role="tabpanel"
      id={`${idPrefix}-panel-${tabKey}`}
      aria-labelledby={`${idPrefix}-tab-${tabKey}`}
      tabIndex={0}
      className="tabpanel"
    >
      {children}
    </div>
  )
}
