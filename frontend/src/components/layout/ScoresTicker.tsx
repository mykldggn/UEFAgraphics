import { useState, useEffect, useCallback } from 'react'
import { matchesApi, type FootballMatch } from '../../api/matches'

// FotMob integer league IDs → short label
const LEAGUE_SHORT: Record<number, string> = {
  47:    'PL',   87:    'LL',   54:    'BL',
  55:    'SA',   53:    'L1',   48:    'CH',
  57:    'ERE',  61:    'PPL',  58:    'SP',
  42:    'UCL',  73:    'UEL',  10478: 'UECL',
}

// leagueShort string from fdorg fallback → label
const LEAGUE_SHORT_STR: Record<string, string> = {
  'UEFA-CL': 'UCL', 'UEFA-EL': 'UEL', 'UEFA-ECL': 'UECL',
  'ENG-1': 'PL', 'ESP-1': 'LL', 'ITA-1': 'SA', 'DEU-1': 'BL', 'FRA-1': 'L1',
}

function leagueLabel(m: FootballMatch): string {
  if (m.leagueId) {
    const s = LEAGUE_SHORT[m.leagueId]
    if (s) return s
  }
  if ((m as any).leagueShort) return LEAGUE_SHORT_STR[(m as any).leagueShort] ?? ''
  return m.leagueName?.slice(0, 4).toUpperCase() ?? ''
}

function shortName(full: string): string {
  if (!full) return ''
  const parts = full.trim().split(/\s+/)
  return parts[parts.length - 1].slice(0, 3).toUpperCase()
}

function addDays(isoDate: string, n: number): string {
  const d = new Date(isoDate + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

function formatDateLabel(isoDate: string): string {
  const today = new Date().toLocaleDateString('en-CA')
  if (isoDate === today) return 'Today'
  const d = new Date(isoDate + 'T12:00:00Z')
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

// ── Competition filter buttons ──────────────────────────────────────────────
const COMP_FILTERS = ['All', 'UCL', 'UEL', 'PL', 'LL', 'BL', 'SA', 'L1']

function NavBtn({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: 'none',
        border: 'none',
        color: disabled ? '#1e2c44' : '#4d5e7a',
        cursor: disabled ? 'default' : 'pointer',
        fontSize: 13,
        padding: '0 6px',
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      {label}
    </button>
  )
}

function MatchCard({ m }: { m: FootballMatch }) {
  const hasScore = m.homeScore !== null && m.awayScore !== null
  const lbl      = leagueLabel(m)
  const scoreColor = m.isLive ? '#22C55E' : m.isFinished ? '#c9a84c' : '#4d5e7a'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '0 12px', height: '100%', flexShrink: 0,
      borderRight: '1px solid rgba(26,34,53,0.8)',
      userSelect: 'none',
    }}>
      {lbl && (
        <span style={{ fontSize: 9, fontWeight: 700, color: '#4d5e7a', letterSpacing: '0.05em', minWidth: 20 }}>
          {lbl}
        </span>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {m.homeTeamCrest && (
          <img src={m.homeTeamCrest} alt="" style={{ width: 14, height: 14, objectFit: 'contain', flexShrink: 0 }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
        )}
        <span style={{ fontSize: 11, color: '#e6e9f4', fontWeight: m.isLive ? 600 : 400 }}>
          {shortName(m.homeTeam)}
        </span>
      </div>
      <div style={{
        fontSize: 12, fontFamily: '"Bebas Neue", monospace', letterSpacing: '0.04em',
        color: scoreColor, minWidth: 32, textAlign: 'center',
      }}>
        {hasScore ? `${m.homeScore}-${m.awayScore}` : m.status}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ fontSize: 11, color: '#e6e9f4', fontWeight: m.isLive ? 600 : 400 }}>
          {shortName(m.awayTeam)}
        </span>
        {m.awayTeamCrest && (
          <img src={m.awayTeamCrest} alt="" style={{ width: 14, height: 14, objectFit: 'contain', flexShrink: 0 }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
        )}
      </div>
      {m.isLive && m.minute && (
        <span style={{ fontSize: 9, color: '#22C55E', fontWeight: 700, letterSpacing: '0.05em' }}>
          {m.minute}
        </span>
      )}
    </div>
  )
}

export default function ScoresTicker() {
  const todayIso = new Date().toLocaleDateString('en-CA')
  const [selectedDate, setSelectedDate] = useState(todayIso)
  const [compFilter, setCompFilter]     = useState('All')
  const [matches, setMatches]           = useState<FootballMatch[]>([])
  const [loading, setLoading]           = useState(true)

  const fetchMatches = useCallback(() => {
    const dateFm = selectedDate.replace(/-/g, '')
    matchesApi.today(dateFm)
      .then(r => { setMatches(Array.isArray(r?.matches) ? r.matches : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [selectedDate])

  useEffect(() => {
    setLoading(true)
    fetchMatches()
    const iv = setInterval(fetchMatches, 60_000)
    return () => clearInterval(iv)
  }, [fetchMatches])

  const visible = compFilter === 'All'
    ? matches
    : matches.filter(m => leagueLabel(m) === compFilter)

  const canGoForward = selectedDate < addDays(todayIso, 1)
  const isToday     = selectedDate === todayIso

  // Always render — controls should be visible even when no matches load
  return (
    <div style={{
      background: '#07090f',
      borderBottom: '1px solid #1a2235',
      flexShrink: 0,
      userSelect: 'none',
    }}>
      {/* ── Controls row ──────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderBottom: '1px solid rgba(26,34,53,0.5)',
        overflowX: 'auto',
        scrollbarWidth: 'none',
      }}>
        {/* Date nav */}
        <NavBtn label="‹" onClick={() => setSelectedDate(d => addDays(d, -1))} />
        <button
          onClick={() => setSelectedDate(todayIso)}
          style={{
            background: isToday ? 'rgba(201,168,76,0.12)' : 'none',
            border: isToday ? '1px solid rgba(201,168,76,0.3)' : '1px solid transparent',
            borderRadius: 4,
            color: isToday ? '#c9a84c' : '#4d5e7a',
            fontSize: 10,
            padding: '2px 8px',
            cursor: 'pointer',
            fontWeight: 600,
            letterSpacing: '0.04em',
            flexShrink: 0,
          }}
        >
          {formatDateLabel(selectedDate).toUpperCase()}
        </button>
        <NavBtn label="›" onClick={() => setSelectedDate(d => addDays(d, 1))} disabled={!canGoForward} />

        {/* Divider */}
        <span style={{ width: 1, height: 14, background: '#1a2235', flexShrink: 0, margin: '0 4px' }} />

        {/* Competition filter pills */}
        {COMP_FILTERS.map(c => (
          <button
            key={c}
            onClick={() => setCompFilter(c)}
            style={{
              background: compFilter === c ? 'rgba(201,168,76,0.12)' : 'none',
              border: compFilter === c ? '1px solid rgba(201,168,76,0.3)' : '1px solid transparent',
              borderRadius: 4,
              color: compFilter === c ? '#c9a84c' : '#4d5e7a',
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: '0.05em',
              padding: '2px 7px',
              cursor: 'pointer',
              flexShrink: 0,
              transition: 'all 0.12s',
            }}
          >
            {c}
          </button>
        ))}
      </div>

      {/* ── Scrollable matches ─────────────────────────────────────────────── */}
      <div style={{
        height: 40,
        display: 'flex',
        alignItems: 'center',
        overflowX: 'auto',
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
      } as React.CSSProperties}>
        {loading ? (
          <span style={{ padding: '0 16px', fontSize: 11, color: '#1e2c44' }}>Loading…</span>
        ) : visible.length === 0 ? (
          <span style={{ padding: '0 16px', fontSize: 11, color: '#1e2c44' }}>
            No matches · {selectedDate}
          </span>
        ) : (
          visible.map((m, i) => <MatchCard key={m.id ?? i} m={m} />)
        )}
      </div>
    </div>
  )
}
