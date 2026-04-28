import { useState, useEffect } from 'react'
import { matchesApi, type FootballMatch } from '../../api/matches'

const COMP_SHORT: Record<string, string> = {
  'UEFA-CL': 'UCL', 'UEFA-EL': 'UEL', 'UEFA-ECL': 'UECL',
  'ENG-1': 'PL', 'ESP-1': 'LL', 'ITA-1': 'SA', 'DEU-1': 'BL', 'FRA-1': 'L1',
}

function MatchCard({ m }: { m: FootballMatch }) {
  const hasScore = m.homeScore !== null && m.awayScore !== null

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '0 16px',
      height: 48,
      flexShrink: 0,
      borderRight: '1px solid rgba(26,34,53,0.8)',
      userSelect: 'none',
    }}>
      {/* Competition badge */}
      <span style={{
        fontSize: 9,
        fontWeight: 700,
        color: '#4d5e7a',
        letterSpacing: '0.05em',
        minWidth: 24,
      }}>
        {COMP_SHORT[m.competitionId] ?? m.competition.slice(0, 3).toUpperCase()}
      </span>

      {/* Home */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        {m.homeCrest && (
          <img src={m.homeCrest} alt="" style={{ width: 16, height: 16, objectFit: 'contain' }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
        )}
        <span style={{ fontSize: 12, color: '#e6e9f4', fontWeight: m.isLive ? 600 : 400 }}>
          {m.homeShort || m.homeTeam.slice(0, 3).toUpperCase()}
        </span>
      </div>

      {/* Score or time */}
      <div style={{
        fontSize: 13,
        fontFamily: '"Bebas Neue", sans-serif',
        letterSpacing: '0.04em',
        color: m.isLive ? '#22C55E' : m.isFinished ? '#c9a84c' : '#4d5e7a',
        minWidth: 36,
        textAlign: 'center',
      }}>
        {hasScore ? `${m.homeScore} - ${m.awayScore}` : m.statusLabel}
      </div>

      {/* Away */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <span style={{ fontSize: 12, color: '#e6e9f4', fontWeight: m.isLive ? 600 : 400 }}>
          {m.awayShort || m.awayTeam.slice(0, 3).toUpperCase()}
        </span>
        {m.awayCrest && (
          <img src={m.awayCrest} alt="" style={{ width: 16, height: 16, objectFit: 'contain' }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
        )}
      </div>

      {/* Live indicator */}
      {m.isLive && (
        <span style={{
          fontSize: 9,
          color: '#22C55E',
          fontWeight: 700,
          letterSpacing: '0.05em',
        }}>
          {m.statusLabel}
        </span>
      )}
    </div>
  )
}

export default function ScoresTicker() {
  const [matches, setMatches] = useState<FootballMatch[]>([])
  const [loading, setLoading] = useState(true)
  const today = new Date().toLocaleDateString('en-CA') // YYYY-MM-DD in local tz

  const fetchMatches = () => {
    matchesApi.today(today)
      .then(r => { setMatches(r.matches); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    fetchMatches()
    const iv = setInterval(fetchMatches, 60_000) // refresh every 60s
    return () => clearInterval(iv)
  }, [today])

  if (loading || matches.length === 0) return null

  return (
    <div style={{
      height: 48,
      background: '#07090f',
      borderBottom: '1px solid #1a2235',
      display: 'flex',
      alignItems: 'center',
      overflow: 'hidden',
      flexShrink: 0,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        overflowX: 'auto',
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
        height: '100%',
      }}>
        {matches.map((m, i) => <MatchCard key={i} m={m} />)}
      </div>
    </div>
  )
}
