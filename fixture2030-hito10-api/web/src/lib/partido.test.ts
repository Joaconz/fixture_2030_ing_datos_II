import { describe, expect, it } from 'vitest'
import type { Evento, PartidoDeEquipo, PartidoDetalle } from '../api/types'
import {
  descripcionFase,
  equipoDeEvento,
  familiaEvento,
  marcadorDeDetalle,
  marcadorDePartidoDeEquipo,
  ordenarPorFecha,
  protagonistaCorto,
  tituloEvento,
} from './partido'

const partido: PartidoDetalle = {
  partidoId: 'PAR-A-1',
  fase: 'Fase de grupos',
  grupo: 'A',
  jornada: 1,
  fechaHora: '2030-06-09T13:00:00Z',
  estado: 'FINALIZADO',
  local: { equipoCodigo: 'URU', nombre: 'Uruguay' },
  visitante: { equipoCodigo: 'POR', nombre: 'Portugal' },
  marcador: { golesLocal: 2, golesVisitante: 1 },
  cantidadEventos: 10,
}

const evento = (over: Partial<Evento>): Evento => ({
  eventoId: 'e1',
  partidoId: 'PAR-A-1',
  secuencia: 1,
  tipo: 'GOL',
  minuto: 12,
  ...over,
})

describe('marcadores', () => {
  it('el detalle sin marcador (partido sin cerrar) no inventa un 0-0', () => {
    expect(marcadorDeDetalle(partido)).toEqual({ local: 2, visitante: 1 })
    expect(marcadorDeDetalle({ ...partido, marcador: null })).toBeNull()
  })

  it('el partido del equipo necesita los dos goles', () => {
    const base: PartidoDeEquipo = {
      partidoId: 'PAR-A-1',
      fase: 'Fase de grupos',
      fechaHora: '2030-06-09T13:00:00Z',
      estado: 'PROGRAMADO',
      condicion: 'LOCAL',
      rivalCodigo: 'POR',
    }
    expect(marcadorDePartidoDeEquipo(base)).toBeNull()
    expect(marcadorDePartidoDeEquipo({ ...base, golesLocal: 0, golesVisitante: 3 })).toEqual({ local: 0, visitante: 3 })
  })
})

describe('eventos', () => {
  it('asigna el equipo por condición y deja los eventos del partido sin equipo', () => {
    expect(equipoDeEvento(evento({ condicionEquipo: 'VISITANTE' }), partido)).toEqual({ codigo: 'POR', nombre: 'Portugal' })
    expect(equipoDeEvento(evento({ tipo: 'INICIO_PARTIDO', condicionEquipo: null }), partido)).toBeNull()
  })

  it('arma el protagonista con inicial, apellido y dorsal', () => {
    const conNombre = evento({ dorsalProtagonista: 10, protagonista: { dni: '1', nombre: 'Lionel', apellido: 'Messi' } })
    expect(protagonistaCorto(conNombre)).toBe('L. Messi #10')
    expect(protagonistaCorto(evento({ dorsalProtagonista: 9 }))).toBe('Dorsal #9')
    expect(protagonistaCorto(evento({}))).toBeNull()
    expect(tituloEvento(conNombre)).toBe('L. Messi #10 · Gol')
    expect(tituloEvento(evento({ tipo: 'FIN_PARTIDO' }))).toBe('Fin del partido')
  })

  it('agrupa los 12 tipos en familias visuales', () => {
    expect(familiaEvento('PENAL')).toBe('gol')
    expect(familiaEvento('TARJETA_ROJA')).toBe('roja')
    expect(familiaEvento('SUSTITUCION')).toBe('cambio')
    expect(familiaEvento('CORNER')).toBe('juego')
    expect(familiaEvento('FIN_PARTIDO')).toBe('marco')
  })
})

describe('textos', () => {
  it('describe la fase con lo que haya', () => {
    expect(descripcionFase({ ...partido, fase: 'GRUPOS' })).toBe('Fase de grupos · Grupo A · Jornada 1')
    expect(descripcionFase({ fase: 'DIECISEISAVOS' })).toBe('Dieciseisavos de final')
    expect(descripcionFase({ fase: 'REPECHAJE_INTER' })).toBe('Repechaje inter')
  })

  it('ordena partidos por fecha sin mutar la lista', () => {
    const lista = [{ fechaHora: '2030-06-20T10:00:00Z' }, { fechaHora: '2030-06-10T10:00:00Z' }]
    expect(ordenarPorFecha(lista).map((p) => p.fechaHora)).toEqual(['2030-06-10T10:00:00Z', '2030-06-20T10:00:00Z'])
    expect(lista[0]?.fechaHora).toBe('2030-06-20T10:00:00Z')
  })
})
