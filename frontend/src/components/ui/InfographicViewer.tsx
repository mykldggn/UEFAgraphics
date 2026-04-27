import { useState, useEffect } from 'react'

interface Props {
  src: string
  alt: string
  className?: string
}

export default function InfographicViewer({ src, alt, className = '' }: Props) {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading')

  useEffect(() => {
    setStatus('loading')
  }, [src])

  return (
    <div className={`relative ${className}`}>
      {status === 'loading' && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#0c1321', borderRadius: 8, minHeight: 300,
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, color: '#4d5e7a' }}>
            <svg style={{ width: 32, height: 32, color: '#c9a84c' }} className="animate-spin" viewBox="0 0 24 24" fill="none">
              <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path style={{ opacity: 0.75 }} fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span style={{ fontSize: 13 }}>Generating infographic…</span>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#0c1321', borderRadius: 8, padding: 48, minHeight: 200,
          color: '#4d5e7a', fontSize: 13, border: '1px solid #1a2235',
        }}>
          Failed to load infographic. The data may not be available for this selection.
        </div>
      )}

      <img
        src={src}
        alt={alt}
        style={{
          width: '100%',
          borderRadius: 8,
          transition: 'opacity 0.3s',
          opacity: status === 'loaded' ? 1 : 0,
        }}
        onLoad={() => setStatus('loaded')}
        onError={() => setStatus('error')}
      />
    </div>
  )
}
