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
    <div ref={containerRef} className="relative flex flex-col gap-1">
      {label && <label className="text-xs text-sub font-medium uppercase tracking-wide">{label}</label>}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-card border border-border text-white text-sm rounded-md px-3 py-2 pr-8
                     focus:outline-none focus:ring-1 focus:ring-accent placeholder-sub"
        />
        {loading && (
          <svg className="absolute right-2 top-2.5 w-4 h-4 animate-spin text-accent" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
      </div>

      {open && (
        <ul className="absolute z-50 top-full mt-1 w-full bg-card border border-border rounded-md
                       shadow-xl max-h-60 overflow-y-auto">
          {results.map((opt, i) => (
            <li key={opt.id ?? i}>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-border transition-colors"
                onClick={() => handleSelect(opt)}
              >
                <span className="text-white font-medium">{displayName(opt)}</span>
                {opt.team && <span className="text-sub ml-2 text-xs">{opt.team}</span>}
                {opt.pos  && <span className="text-sub ml-1 text-xs">· {opt.pos}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
