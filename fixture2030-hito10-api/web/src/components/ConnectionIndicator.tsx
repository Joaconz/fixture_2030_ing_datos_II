import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { getHealth, getSaludDependencias } from '../api/endpoints'
import { enArquitectura } from '../api/types'
import { HEALTH_POLL_MS } from '../config'
import { Icon } from './Icon'

type Estado =
  | { tipo: 'conectando' }
  | { tipo: 'offline' }
  | { tipo: 'online'; up: number; total: number; caidas: string[] }

/**
 * Indicador de conexión del encabezado: /health (¿la API vive?) y
 * /health/dependencias (¿cuántas fuentes responden?). Se refresca solo.
 */
export function ConnectionIndicator() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'conectando' })

  useEffect(() => {
    let vivo = true
    let ctrl = new AbortController()
    async function sondear() {
      ctrl.abort()
      ctrl = new AbortController()
      const vida = await getHealth(ctrl.signal)
      if (!vivo) return
      if (!vida.ok) {
        if (vida.error.kind !== 'aborted') setEstado({ tipo: 'offline' })
        return
      }
      const deps = await getSaludDependencias(ctrl.signal)
      if (!vivo) return
      if (deps.ok) {
        const lista = deps.data.dependencias.filter(enArquitectura)
        const caidas = lista.filter((d) => d.estado !== 'UP').map((d) => d.nombre)
        setEstado({ tipo: 'online', up: lista.length - caidas.length, total: lista.length, caidas })
      } else if (deps.error.kind !== 'aborted') {
        setEstado({ tipo: 'online', up: 0, total: 5, caidas: ['desconocido'] })
      }
    }
    void sondear()
    const t = setInterval(() => void sondear(), HEALTH_POLL_MS)
    const alVolver = () => {
      if (document.visibilityState === 'visible') void sondear()
    }
    document.addEventListener('visibilitychange', alVolver)
    return () => {
      vivo = false
      ctrl.abort()
      clearInterval(t)
      document.removeEventListener('visibilitychange', alVolver)
    }
  }, [])

  let clase = 'conn-pending'
  let texto = 'Conectando con la API…'
  let corto = 'Conectando'
  if (estado.tipo === 'offline') {
    clase = 'conn-down'
    texto = 'API sin conexión'
    corto = 'Sin conexión'
  } else if (estado.tipo === 'online') {
    const todo = estado.up === estado.total
    clase = todo ? 'conn-up' : 'conn-degraded'
    texto = todo
      ? `API en línea · ${estado.up}/${estado.total} fuentes`
      : `API en línea · ${estado.up}/${estado.total} fuentes (caídas: ${estado.caidas.join(', ')})`
    corto = `${estado.up}/${estado.total} fuentes`
  }

  return (
    <Link to="/salud" className={`conn ${clase}`} aria-live="polite" title={`${texto}. Ver salud de las fuentes`}>
      <span className="conn-dot" aria-hidden="true" />
      <Icon name={estado.tipo === 'offline' ? 'plugOff' : 'activity'} size={16} />
      <span className="conn-long">{texto}</span>
      <span className="conn-short" aria-hidden="true">
        {corto}
      </span>
    </Link>
  )
}
