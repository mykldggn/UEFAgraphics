import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  src: string
  alt: string
  className?: string
}

export default function InfographicViewer({ src, alt, className = '' }: Props) {
  const [status, setStatus]   = useState<'loading' | 'loaded' | 'error'>('loading')
  const [lightbox, setLightbox] = useState(false)
  const [hovered, setHovered]  = useState(false)

  useEffect(() => {
    setStatus('loading')
  }, [src])

  useEffect(() => {
    if (!lightbox) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLightbox(false)
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [lightbox])

  const lightboxOverlay = lightbox ? (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${alt} zoomed preview`}
      onMouseDown={e => {
        if (e.target === e.currentTarget) setLightbox(false)
      }}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.92)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
        cursor: 'zoom-out',
      }}
    >
      <img
        src={src}
        alt={alt}
        draggable={false}
        style={{
          maxWidth: '96vw',
          maxHeight: '94vh',
          objectFit: 'contain',
          borderRadius: 10,
          boxShadow: '0 12px 60px rgba(0,0,0,0.8)',
          cursor: 'default',
          userSelect: 'none',
        }}
      />
      <button
        type="button"
        aria-label="Close zoomed infographic"
        onMouseDown={e => e.stopPropagation()}
        onClick={() => setLightbox(false)}
        style={{
          position: 'fixed', top: 16, right: 16, zIndex: 10000,
          background: 'rgba(12,19,33,0.95)',
          border: '1px solid #2c3854',
          borderRadius: '50%',
          width: 42, height: 42,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer',
          color: '#e6e9f4',
          fontSize: 18,
          lineHeight: 1,
          fontWeight: 700,
          boxShadow: '0 8px 28px rgba(0,0,0,0.45)',
        }}
      >
        X
      </button>
    </div>
  ) : null

  return (
    <>
      <div
        className={`relative ${className}`}
        style={{ cursor: status === 'loaded' ? 'zoom-in' : 'default' }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {/* Shimmer skeleton — shown while loading */}
        {status === 'loading' && (
          <div
            className="skeleton-shimmer"
            style={{
              borderRadius: 8,
              width: '100%',
              paddingBottom: '85%',  /* ~10:8.5 matches most chart aspect ratios */
            }}
          />
        )}

        {/* Error state */}
        {status === 'error' && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: 12,
            background: '#0c1321', borderRadius: 8, padding: 48, minHeight: 200,
            border: '1px solid #1a2235',
          }}>
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.35 }}>
              <circle cx="12" cy="12" r="10" stroke="#4d5e7a" strokeWidth="1.5"/>
              <path d="M12 8v4M12 16h.01" stroke="#4d5e7a" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <span style={{ color: '#4d5e7a', fontSize: 13, textAlign: 'center', maxWidth: 320 }}>
              Failed to load infographic. The data may not be available for this selection.
            </span>
          </div>
        )}

        {/* The actual image */}
        <img
          src={src}
          alt={alt}
          onClick={() => status === 'loaded' && setLightbox(true)}
          style={{
            width: '100%',
            borderRadius: 8,
            transition: 'opacity 0.3s, transform 0.2s',
            opacity: status === 'loaded' ? 1 : 0,
            display: status === 'error' ? 'none' : 'block',
            transform: hovered && status === 'loaded' ? 'scale(1.003)' : 'scale(1)',
          }}
          onLoad={() => setStatus('loaded')}
          onError={() => setStatus('error')}
        />

        {/* Zoom hint — appears on hover */}
        {status === 'loaded' && hovered && (
          <div style={{
            position: 'absolute', bottom: 12, right: 12,
            background: 'rgba(6,8,15,0.75)',
            border: '1px solid #1a2235',
            borderRadius: 5,
            padding: '4px 9px',
            fontSize: 11,
            color: '#c9a84c',
            display: 'flex', alignItems: 'center', gap: 5,
            pointerEvents: 'none',
            backdropFilter: 'blur(4px)',
          }}>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="11" cy="11" r="7"/>
              <line x1="16.5" y1="16.5" x2="21" y2="21"/>
              <line x1="11" y1="8" x2="11" y2="14"/>
              <line x1="8" y1="11" x2="14" y2="11"/>
            </svg>
            Click to zoom
          </div>
        )}
      </div>

      {lightboxOverlay ? createPortal(lightboxOverlay, document.body) : null}
    </>
  )
}
