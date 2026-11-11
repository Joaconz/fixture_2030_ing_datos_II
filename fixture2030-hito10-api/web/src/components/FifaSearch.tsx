import { useId, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { validarCodigoFifa } from '../lib/fifa'
import { Icon } from './Icon'

interface FifaSearchProps {
  /** `barra`: el buscador compacto de la barra superior; `bloque`: con etiqueta visible y botón. */
  variante?: 'barra' | 'bloque'
  valorInicial?: string
  etiqueta?: string
}

/** Buscador de equipo por código FIFA: valida en el navegador (3 letras) antes de navegar. */
export function FifaSearch({ variante = 'bloque', valorInicial = '', etiqueta = 'Código FIFA del equipo' }: FifaSearchProps) {
  const id = useId()
  const navigate = useNavigate()
  const [valor, setValor] = useState(valorInicial)
  const [error, setError] = useState<string | null>(null)

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const r = validarCodigoFifa(valor)
    if (!r.ok) {
      setError(r.mensaje)
      return
    }
    setError(null)
    setValor(r.codigo)
    void navigate(`/equipos/${r.codigo}`)
  }

  const errorId = `${id}-error`
  return (
    <form className={`fifa-search fifa-search-${variante}`} onSubmit={onSubmit} noValidate role="search">
      <label htmlFor={id} className={variante === 'barra' ? 'sr-only' : undefined}>
        {etiqueta}
      </label>
      <div className="fifa-search-row">
        <span className="fifa-search-field">
          <Icon name="search" size={16} />
          <input
            id={id}
            type="text"
            value={valor}
            onChange={(e) => {
              setValor(e.target.value)
              if (error) setError(null)
            }}
            placeholder={variante === 'barra' ? 'Buscar código FIFA (ej. ARG)' : 'Código FIFA (ej. ARG)'}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={8}
            aria-invalid={error !== null}
            aria-describedby={error ? errorId : undefined}
          />
        </span>
        {variante === 'bloque' && (
          <button type="submit" className="btn btn-primary">
            <Icon name="search" size={16} />
            Buscar
          </button>
        )}
      </div>
      {error && (
        <p id={errorId} className="field-error fifa-search-error" role="alert">
          <Icon name="alert" size={14} />
          {error}
        </p>
      )}
    </form>
  )
}
