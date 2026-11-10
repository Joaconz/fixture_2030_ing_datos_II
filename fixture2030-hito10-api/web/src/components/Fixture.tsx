/** Piezas visuales compartidas del fixture: insignia de estado, código de equipo y tarjetas de partido. */
import { Link } from 'react-router'
import type { PartidoDeEquipo, PartidoDetalle } from '../api/types'
import {
  descripcionFase,
  ETIQUETA_ESTADO,
  marcadorDeDetalle,
  marcadorDePartidoDeEquipo,
  type EstadoPartido,
} from '../lib/partido'
import { formatFechaHoraUtc } from '../lib/time'
import { Icon } from './Icon'

/** Insignia de estado en píldora. La API no informa "en vivo", así que el acento no se usa. */
export function EstadoPill({ estado }: { estado: EstadoPartido }) {
  return <span className={`pill pill-${estado.toLowerCase()}`}>{ETIQUETA_ESTADO[estado]}</span>
}

/** Recuadro con el código FIFA (cifras y letras tabulares). */
export function CodigoEquipo({ codigo, tamano = 'md' }: { codigo: string; tamano?: 'sm' | 'md' | 'lg' }) {
  return (
    <span className={`codigo-equipo codigo-${tamano}`} aria-hidden="true">
      {codigo}
    </span>
  )
}

/** Tarjeta de partido destacado (inicio) a partir del detalle del partido. */
export function TarjetaPartido({ p }: { p: PartidoDetalle }) {
  const m = marcadorDeDetalle(p)
  return (
    <Link to={`/partidos/${encodeURIComponent(p.partidoId)}`} className="tarjeta-partido">
      <span className="tarjeta-partido-meta">
        <span className="eyebrow-text">{descripcionFase(p)}</span>
        <EstadoPill estado={p.estado} />
      </span>
      <span className="tarjeta-partido-equipos">
        <span className="tp-equipo">
          <span className="tp-codigo">{p.local.equipoCodigo}</span>
          <span className="tp-nombre">{p.local.nombre}</span>
        </span>
        <span className="tp-centro">
          {m ? (
            <span className="tp-marcador num" aria-label={`${m.local} a ${m.visitante}`}>
              {m.local} – {m.visitante}
            </span>
          ) : (
            <span className="tp-vs">vs</span>
          )}
        </span>
        <span className="tp-equipo tp-equipo-visitante">
          <span className="tp-codigo">{p.visitante.equipoCodigo}</span>
          <span className="tp-nombre">{p.visitante.nombre}</span>
        </span>
      </span>
      <span className="tarjeta-partido-pie">
        <span className="tp-dato">
          <Icon name="calendar" size={14} />
          <span className="num">{formatFechaHoraUtc(p.fechaHora)}</span>
        </span>
        {p.sede ? (
          <span className="tp-dato">
            <Icon name="mapPin" size={14} />
            {p.sede.nombre}, {p.sede.ciudad}
          </span>
        ) : null}
        <span className="tp-ir">
          Ver partido <Icon name="arrowRight" size={14} />
        </span>
      </span>
    </Link>
  )
}

/** Fila de partido en la ficha de un equipo: sólo se conoce el código del rival. */
export function FilaPartidoDeEquipo({ p, codigo }: { p: PartidoDeEquipo; codigo: string }) {
  const m = marcadorDePartidoDeEquipo(p)
  const esLocal = p.condicion === 'LOCAL'
  const [izq, der] = esLocal ? [codigo, p.rivalCodigo] : [p.rivalCodigo, codigo]
  return (
    <Link to={`/partidos/${encodeURIComponent(p.partidoId)}`} className="fila-partido">
      <span className="fila-partido-meta">
        <span className="num">{formatFechaHoraUtc(p.fechaHora)}</span>
        <EstadoPill estado={p.estado} />
      </span>
      <span className="fila-partido-cruce">
        <span className="fp-equipos">
          <span className={izq === codigo ? 'fp-propio' : undefined}>{izq}</span>
          <span className={der === codigo ? 'fp-propio' : undefined}>{der}</span>
        </span>
        <span className="fp-marcador num">
          {m ? (
            <>
              <span>{m.local}</span>
              <span>{m.visitante}</span>
            </>
          ) : (
            <span className="fp-vs">vs</span>
          )}
        </span>
      </span>
      <span className="fila-partido-pie">
        {descripcionFase(p)} · {esLocal ? 'Local' : 'Visitante'}
      </span>
    </Link>
  )
}
