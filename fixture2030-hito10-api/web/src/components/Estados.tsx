/**
 * Estados de las pantallas del hincha ("Hoja de Estados" del proyecto de Stitch):
 * vacío, no encontrado, dato inválido y fuente no disponible son cuatro
 * composiciones distintas, cada una con título y acción (PRODUCT.md, principio 2).
 * No nombran bases de datos: dicen qué parte de la app no se pudo cargar.
 */
import type { ReactNode } from 'react'
import { areaDeFuente, type ApiFailure } from '../api/errors'
import { FifaSearch } from './FifaSearch'
import { Icon, type IconName } from './Icon'
import { RequestId } from './RequestId'

interface EstadoBaseProps {
  tono: 'neutro' | 'aviso' | 'error'
  icono: IconName
  titulo: string
  children?: ReactNode
  accion?: ReactNode
  pie?: ReactNode
  rol?: 'status' | 'alert'
  compacto?: boolean
}

function EstadoBase({ tono, icono, titulo, children, accion, pie, rol = 'status', compacto = false }: EstadoBaseProps) {
  return (
    <div className={`estado estado-${tono}${compacto ? ' estado-compacto' : ''}`} role={rol}>
      <span className="estado-icono" aria-hidden="true">
        <Icon name={icono} size={compacto ? 18 : 22} />
      </span>
      <div className="estado-cuerpo">
        <p className="estado-titulo">{titulo}</p>
        {children ? <div className="estado-texto">{children}</div> : null}
        {accion ? <div className="estado-accion">{accion}</div> : null}
        {pie ? <div className="estado-pie">{pie}</div> : null}
      </div>
    </div>
  )
}

/** 01 · Vacío: el recurso existe pero no tiene datos (200 con lista vacía). */
export function EstadoVacio({
  titulo,
  children,
  accion,
  icono = 'info',
  compacto,
}: {
  titulo: string
  children?: ReactNode
  accion?: ReactNode
  icono?: IconName
  compacto?: boolean
}) {
  return (
    <EstadoBase tono="neutro" icono={icono} titulo={titulo} accion={accion} compacto={compacto}>
      {children}
    </EstadoBase>
  )
}

/** 03 · Dato inválido detectado antes de llamar a la API (con el campo para corregirlo). */
export function EstadoDatoInvalido({ children, accion }: { children: ReactNode; accion?: ReactNode }) {
  return (
    <EstadoBase tono="aviso" icono="alert" titulo="Dato inválido" rol="alert" accion={accion}>
      {children}
    </EstadoBase>
  )
}

/** Dato que la API no ofrece: se dice, no se inventa (PRODUCT.md, principio 3). */
export function EstadoNoDisponible({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <EstadoBase tono="neutro" icono="ban" titulo={titulo} compacto>
      {children}
    </EstadoBase>
  )
}

/** Cargando: altura reservada para que la página no salte al llegar los datos. */
export function Cargando({ lineas = 3, etiqueta = 'Cargando…' }: { lineas?: number; etiqueta?: string }) {
  return (
    <div className="cargando" role="status" aria-live="polite">
      <span className="sr-only">{etiqueta}</span>
      {Array.from({ length: lineas }, (_, i) => (
        <span key={i} className="cargando-linea" style={{ width: `${94 - ((i * 19) % 42)}%` }} aria-hidden="true" />
      ))}
    </div>
  )
}

interface EstadoErrorProps {
  error: ApiFailure
  /** Reintentar la misma solicitud (fuente no disponible, sin conexión, error interno). */
  onRetry?: () => void
  /** Qué se buscó, para el 404: "ese equipo", "ese partido". */
  recurso?: string
  /** Qué parte de la pantalla falló si la API no indica la fuente: "los comentarios". */
  que?: string
  /** En un 404 de equipo, ofrecer el buscador por código FIFA. */
  buscarEquipo?: boolean
  /** Acción extra (por ejemplo, volver al inicio). */
  accion?: ReactNode
  compacto?: boolean
}

/** 02 · No encontrado (404) · 03 · Dato inválido (400) · 04 · Fuente no disponible (503/504) y demás errores. */
export function EstadoError({ error, onRetry, recurso, que, buscarEquipo = false, accion, compacto }: EstadoErrorProps) {
  if (error.kind === 'aborted') return null
  const pie = <RequestId id={error.requestId} prefix="ID de solicitud" />
  const reintentar = onRetry ? (
    <button type="button" className="btn btn-primary btn-sm" onClick={onRetry}>
      <Icon name="refresh" size={16} />
      Reintentar
    </button>
  ) : null

  switch (error.kind) {
    case 'not_found':
      return (
        <EstadoBase
          tono="neutro"
          icono="searchX"
          titulo={recurso ? `No encontramos ${recurso}` : 'No encontramos lo que buscabas'}
          accion={
            buscarEquipo || accion ? (
              <>
                {buscarEquipo ? <FifaSearch etiqueta="Probá con otro código FIFA" /> : null}
                {accion}
              </>
            ) : null
          }
          compacto={compacto}
        >
          <p>{error.message}</p>
        </EstadoBase>
      )
    case 'validation':
      return (
        <EstadoBase tono="aviso" icono="alert" titulo="Dato inválido" rol="alert" accion={accion} pie={pie} compacto={compacto}>
          <p>Revisá el dato ingresado: no tiene el formato que se espera.</p>
          {error.details.length > 0 && (
            <details className="estado-detalle">
              <summary>Ver detalle</summary>
              <ul>
                {error.details.map((d, i) => (
                  <li key={`${d.campo}-${i}`}>
                    <code>{d.campo}</code> {d.problema}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </EstadoBase>
      )
    case 'unavailable': {
      const area = areaDeFuente(error.dependency)
      const objeto = area ? `los datos de ${area}` : (que ?? 'estos datos')
      return (
        <EstadoBase
          tono="error"
          icono="serverOff"
          titulo={`No pudimos cargar ${objeto} ahora`}
          rol="alert"
          accion={reintentar}
          pie={pie}
          compacto={compacto}
        >
          <p>
            {error.status === 504 ? 'El servicio tardó demasiado en responder.' : 'El servicio que los entrega no está disponible.'}{' '}
            No es que no existan: probá de nuevo
            {error.retryAfter !== null ? ` en ${error.retryAfter} s` : ' en unos segundos'}.
          </p>
        </EstadoBase>
      )
    }
    case 'network':
      return (
        <EstadoBase tono="error" icono="plugOff" titulo="Sin conexión" rol="alert" accion={reintentar} compacto={compacto}>
          <p>No pudimos comunicarnos con el servidor de Fixture 2030. Revisá tu conexión y reintentá.</p>
        </EstadoBase>
      )
    case 'server':
      return (
        <EstadoBase tono="error" icono="alert" titulo="Algo salió mal" rol="alert" accion={reintentar} pie={pie} compacto={compacto}>
          <p>Hubo un error inesperado al cargar {que ?? 'estos datos'}.</p>
        </EstadoBase>
      )
    case 'conflict':
      return (
        <EstadoBase tono="aviso" icono="gitMerge" titulo="No se pudo completar" rol="alert" accion={accion} pie={pie} compacto={compacto}>
          <p>{error.message}</p>
        </EstadoBase>
      )
    case 'forbidden':
      return (
        <EstadoBase tono="aviso" icono="lock" titulo="Acceso denegado" rol="alert" accion={accion} pie={pie} compacto={compacto}>
          <p>{error.message}</p>
        </EstadoBase>
      )
    default:
      return (
        <EstadoBase tono="aviso" icono="info" titulo="Respuesta inesperada" rol="alert" accion={reintentar} pie={pie} compacto={compacto}>
          <p>{error.message}</p>
        </EstadoBase>
      )
  }
}
