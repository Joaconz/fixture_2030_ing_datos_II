/**
 * Código FIFA de 3 letras (el mismo patrón que valida la API: ^[A-Z]{3}$).
 * El buscador normaliza mayúsculas y espacios antes de validar, para que
 * "arg " lleve a ARG y "12" no llegue a la API como un 400.
 */
export type CodigoFifa =
  | { ok: true; codigo: string }
  | { ok: false; motivo: 'vacio' | 'formato'; mensaje: string }

export function validarCodigoFifa(entrada: string): CodigoFifa {
  const codigo = entrada.trim().toUpperCase()
  if (codigo === '') return { ok: false, motivo: 'vacio', mensaje: 'Escribí un código FIFA, por ejemplo ARG.' }
  if (!/^[A-Z]{3}$/.test(codigo)) {
    return {
      ok: false,
      motivo: 'formato',
      mensaje: 'El código tiene que ser de 3 letras, por ejemplo ARG.',
    }
  }
  return { ok: true, codigo }
}
