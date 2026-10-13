/**
 * Íconos SVG de trazo uniforme (2px, 24×24), trazados al estilo de Lucide
 * (licencia ISC). Decorativos por defecto: el texto al lado da el significado.
 */
const PATHS = {
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3',
  refresh: 'M3 12a9 9 0 0 1 15.5-6.2L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.2L3 16M3 21v-5h5',
  copy: 'M9 9h11v11H9zM5 15H4V4h11v1',
  check: 'M20 6 9 17l-5-5',
  alert: 'M12 3 2 20h20L12 3zM12 10v4M12 17h.01',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 16v-4M12 8h.01',
  lock: 'M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4',
  ban: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM5.6 5.6l12.8 12.8',
  plugOff: 'M2 2l20 20M7 7v3a5 5 0 0 0 7.7 4.2M17 12V8h-3M9 2v4M15 2v4M12 17v5',
  serverOff: 'M7 3h12a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-5M3 7v2a2 2 0 0 0 2 2h4M3 15v2a2 2 0 0 0 2 2h12M21 17v-2a2 2 0 0 0-2-2h-2M2 2l20 20',
  searchX: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3M8.5 8.5l5 5M13.5 8.5l-5 5',
  gitMerge: 'M6 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM18 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM6 9v12M6 9a9 9 0 0 0 9 9',
  database: 'M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  activity: 'M22 12h-4l-3 9L9 3l-3 9H2',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
  monitor: 'M3 4h18v12H3zM8 20h8M12 16v4',
  chevronRight: 'M9 18l6-6-6-6',
  chevronDown: 'M6 9l6 6 6-6',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  message: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
  chart: 'M3 3v18h18M7 15l4-4 3 3 5-6',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  flag: 'M4 22V4M4 4h12l-2 4 2 4H4',
  send: 'M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z',
  repeat: 'M17 1l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4M21 13v2a4 4 0 0 1-4 4H3',
  trash: 'M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6',
  x: 'M18 6 6 18M6 6l12 12',
  mapPin: 'M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12zM12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  ball: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7.5l4 2.9-1.5 4.6h-5L8 10.4zM12 3v4.5M21 10.4l-5 0M18 19.3l-3.5-4.3M6 19.3l3.5-4.3M3 10.4h5',
  key: 'M15.5 7.5a4.5 4.5 0 1 1-6.4 6.4 4.5 4.5 0 0 1 6.4-6.4zM15.5 7.5 21 2M18 5l3 3M12.3 10.7 3 20v2h2l9.3-9.3',
  external: 'M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6',
} as const

export type IconName = keyof typeof PATHS

interface IconProps {
  name: IconName
  size?: number
  /** Si se pasa, el ícono deja de ser decorativo y se anuncia con este texto. */
  label?: string
  className?: string
}

export function Icon({ name, size = 18, label, className }: IconProps) {
  return (
    <svg
      className={className ? `icon ${className}` : 'icon'}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
