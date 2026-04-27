import { useState, useEffect, useRef } from 'react'

interface Option {
  id?: string
  name?: string
  player?: string
  team?: string
  pos?: string
}

interface Props {
  label?: string
  placeholder?: string
  onSearch: (query: string) => Promise<Option[]>
  onSelect: (option: Option) => void
  minChars?: number
}

export default function SearchInput({ label, placeholder = 'Search…', onSearch, onSelect, minChars = 2 }: Props) {
  const [query, setQuery]       = useState('')
  const [results, setResults]   = useState<Option[]>([])
  const [loading, setLoading]   = useState(false)
  const [open, setOpen]         = useState(false)
  const debounceRef              = useRef<ReturnType<typeof setTimeout>>()
  const containerRef             = useRef<HTMLDivElement>(null)

  useEffect(() => {
    clearTimeout(debounceRef.current)
    if (query.length < minChars) {
      setResults([])
      setOpen(false)
      return
    }
    setLoading(true)
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await onSearch(query)
        setResults(res)
        setOpen(res.length > 0)
      } finally {
        setLoading(false)
      }
    }, 320)
  }, [query, minChars, onSearch])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function handleSelect(opt: Option) {
    setQuery(opt.name ?? opt.player ?? '')
    setOpen(false)
    onSelect(opt)
  }

  const displayName = (o: Option) => o.name ?? o.player ?? ''

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 4 }}>
      {label && (
        <label style={{ fontSize: 10, color: '#4d5e7a', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          {label}
        </label>
      )}
      <div style={{ position: 'relative' }}>
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder={placeholder}
          style={{
            width: '100%',
            background: '#111b2f',
            border: '1px solid #1a2235',
            color: '#e6e9f4',
            fontSize: 13,
            borderRadius: 5,
            padding: '7px 32px 7px 10px',
            outline: 'none',
          }}
          onFocus={e => (e.currentTarget.style.borderColor = '#c9a84c44')}
          onBlur={e => (e.currentTarget.style.borderColor = '#1a2235')}
        />
        {loading && (
          <svg
            style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', width: 14, height: 14, color: '#c9a84c' }}
            className="animate-spin"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
      </div>

      {open && (
        <ul style={{
          position: 'absolute',
          zIndex: 50,
          top: '100%',
          marginTop: 4,
          width: '100%',
          background: '#0c1321',
          border: '1px solid #1a2235',
          borderRadius: 6,
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          maxHeight: 240,
          overflowY: 'auto',
          listStyle: 'none',
          padding: 0,
          margin: 0,
        }}>
          {results.map((opt, i) => (
            <li key={opt.id ?? i}>
              <button
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '9px 12px',
                  fontSize: 13,
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'background 0.1s',
                  borderBottom: '1px solid #1a2235',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = '#111b2f')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                onClick={() => handleSelect(opt)}
              >
                <span style={{ color: '#e6e9f4', fontWeight: 500 }}>{displayName(opt)}</span>
                {opt.team && <span style={{ color: '#4d5e7a', marginLeft: 8, fontSize: 11 }}>{opt.team}</span>}
                {opt.pos  && <span style={{ color: '#4d5e7a', marginLeft: 4, fontSize: 11 }}>· {opt.pos}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
