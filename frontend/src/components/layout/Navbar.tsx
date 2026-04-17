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
    <header className="sticky top-0 z-50 bg-card/95 backdrop-blur border-b border-border">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="text-white font-bold text-lg tracking-tight hover:text-accent transition-colors">
          UEFA<span className="text-accent">graphics</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden sm:flex items-center gap-1">
          {LINKS.map(({ to, label }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to))
            return (
              <Link
                key={to}
                to={to}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  active
                    ? 'bg-accent/10 text-accent'
                    : 'text-sub hover:text-white hover:bg-border'
                }`}
              >
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Mobile hamburger */}
        <button
          className="sm:hidden flex flex-col gap-1.5 p-2 rounded-md hover:bg-border transition-colors"
          onClick={() => setOpen(o => !o)}
          aria-label="Toggle menu"
        >
          <span className={`block w-5 h-0.5 bg-white transition-transform duration-200 ${open ? 'rotate-45 translate-y-2' : ''}`} />
          <span className={`block w-5 h-0.5 bg-white transition-opacity duration-200 ${open ? 'opacity-0' : ''}`} />
          <span className={`block w-5 h-0.5 bg-white transition-transform duration-200 ${open ? '-rotate-45 -translate-y-2' : ''}`} />
        </button>
      </div>

      {/* Mobile dropdown */}
      {open && (
        <nav className="sm:hidden border-t border-border bg-card px-4 py-3 flex flex-col gap-1">
          {LINKS.map(({ to, label }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to))
            return (
              <Link
                key={to}
                to={to}
                onClick={() => setOpen(false)}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  active ? 'bg-accent/10 text-accent' : 'text-sub hover:text-white'
                }`}
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
