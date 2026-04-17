import { useState } from 'react'

interface Props {
  src: string
  alt: string
  className?: string
}

export default function InfographicViewer({ src, alt, className = '' }: Props) {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading')

  return (
    <div className={`relative ${className}`}>
      {status === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center bg-card rounded-lg">
          <div className="flex flex-col items-center gap-3 text-sub">
            <svg className="w-8 h-8 animate-spin text-accent" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm">Generating infographic…</span>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div className="flex items-center justify-center bg-card rounded-lg p-12 text-sub text-sm">
          Failed to load infographic. The data may not be available for this selection.
        </div>
      )}

      <img
        src={src}
        alt={alt}
        className={`w-full rounded-lg transition-opacity duration-300 ${
          status === 'loaded' ? 'opacity-100' : 'opacity-0'
        }`}
        onLoad={() => setStatus('loaded')}
        onError={() => setStatus('error')}
      />
    </div>
  )
}
