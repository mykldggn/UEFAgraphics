import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { to: '/',       label: 'Home' },
  { to: '/player', label: 'Players' },
  { to: '/team',   label: 'Teams' },
  { to: '/league', label: 'Leagues' },
]

export default function Navbar() {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        height: 52,
        background: '#06080f',
        borderBottom: '1px solid #1a2235',
      }}
    >
      {/* Decorative gold gradient line at bottom of navbar */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: 1,
        background: 'linear-gradient(90deg, transparent, rgba(201,168,76,0.4), transparent)',
        pointerEvents: 'none',
      }} />

      <div style={{ maxWidth: 1152, margin: '0 auto', padding: '0 16px', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {/* Wordmark */}
        <Link
          to="/"
          style={{
            fontFamily: '"Bebas Neue", sans-serif',
            fontSize: 22,
            letterSpacing: '0.04em',
            textDecoration: 'none',
            lineHeight: 1,
          }}
        >
          <span style={{ color: '#e6e9f4' }}>UEFA</span>
          <span style={{ color: '#c9a84c' }}>graphics</span>
        </Link>

        {/* Desktop nav */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: 4 }} className="hidden sm:flex">
          {LINKS.map(({ to, label }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to))
            return (
              <Link
                key={to}
                to={to}
                style={{
                  padding: '9px 14px',
                  marginBottom: -1,
                  fontSize: 13.5,
                  fontWeight: active ? 600 : 400,
                  color: active ? '#c9a84c' : '#4d5e7a',
                  background: active ? 'rgba(201,168,76,0.10)' : 'transparent',
                  borderBottom: active ? '2px solid #c9a84c' : '2px solid transparent',
                  boxShadow: active ? 'none' : 'none',
                  textDecoration: 'none',
                  borderRadius: '4px 4px 0 0',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => {
                  if (!active) {
                    (e.currentTarget as HTMLElement).style.color = '#e6e9f4'
                  }
                }}
                onMouseLeave={e => {
                  if (!active) {
                    (e.currentTarget as HTMLElement).style.color = '#4d5e7a'
                  }
                }}
              >
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Mobile hamburger */}
        <button
          className="sm:hidden"
          style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 8, background: 'none', border: 'none', cursor: 'pointer' }}
          onClick={() => setOpen(o => !o)}
          aria-label="Toggle menu"
        >
          <span style={{ display: 'block', width: 20, height: 2, background: '#e6e9f4', transition: 'transform 0.2s', transform: open ? 'rotate(45deg) translate(0, 8px)' : 'none' }} />
          <span style={{ display: 'block', width: 20, height: 2, background: '#e6e9f4', transition: 'opacity 0.2s', opacity: open ? 0 : 1 }} />
          <span style={{ display: 'block', width: 20, height: 2, background: '#e6e9f4', transition: 'transform 0.2s', transform: open ? 'rotate(-45deg) translate(0, -8px)' : 'none' }} />
        </button>
      </div>

      {/* Mobile dropdown */}
      {open && (
        <nav style={{ background: '#0c1321', borderTop: '1px solid #1a2235', padding: '8px 16px 12px' }}>
          {LINKS.map(({ to, label }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to))
            return (
              <Link
                key={to}
                to={to}
                onClick={() => setOpen(false)}
                style={{
                  display: 'block',
                  padding: '10px 12px',
                  fontSize: 14,
                  fontWeight: 500,
                  borderBottom: '1px solid #1a2235',
                  color: active ? '#c9a84c' : '#4d5e7a',
                  background: active ? 'rgba(201,168,76,0.10)' : 'transparent',
                  textDecoration: 'none',
                }}
              >
                {label}
              </Link>
            )
          })}
        </nav>
      )}
    </header>
  )
}
