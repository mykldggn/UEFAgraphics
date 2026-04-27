import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import Select from '../components/ui/Select'
import SearchInput from '../components/ui/SearchInput'
import { leaguesApi, type League, type Team } from '../api/leagues'
import { SEASONS, CURRENT_SEASON } from '../utils/constants'

const SEASON_OPTS  = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))
const SEARCH_TABS  = ['Player', 'Team', 'League'] as const
type SearchTab = typeof SEARCH_TABS[number]

const FEATURES = [
  { icon: '◎', title: 'Shot Maps',    desc: 'xG-weighted shots, distance & goal distribution' },
  { icon: '◈', title: 'Radars',       desc: 'Per-90 percentile pizza charts vs peers' },
  { icon: '↗', title: 'Career xG',   desc: 'Cumulative xG vs goals across seasons' },
  { icon: '▦', title: 'Summary Cards', desc: 'Season stats at a glance with progress bars' },
  { icon: '⚡', title: 'xG Timeline', desc: 'Match-by-match xG for & against' },
  { icon: '🏆', title: 'League Tables', desc: 'Standings, form, position race & leaderboards' },
]

export default function HomePage() {
  const navigate = useNavigate()
  const [tab, setTab]             = useState<SearchTab>('Player')
  const [leagues, setLeagues]     = useState<League[]>([])
  const [leagueId, setLeagueId]   = useState('ENG-1')
  const [season, setSeason]       = useState(CURRENT_SEASON)
  const [teams, setTeams]         = useState<Team[]>([])
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null)

  useEffect(() => {
    leaguesApi.list().then(setLeagues).catch(() => {})
  }, [])

  useEffect(() => {
    if (tab === 'Team') {
      leaguesApi.teams(leagueId, season).then(r => setTeams(r.teams)).catch(() => setTeams([]))
    }
  }, [tab, leagueId, season])

  const searchPlayers = useCallback(async (q: string) => {
    const fbres = await leaguesApi.searchPlayers(leagueId, q, season).catch(() => ({ results: [] }))
    if (fbres.results.length) return fbres.results
    const us = await leaguesApi.understatSearch(q).catch(() => ({ results: [] }))
    return us.results
  }, [leagueId, season])

  const leagueOpts = leagues.map(l => ({ value: l.id, label: `${l.label} (${l.country})` }))
  const teamOpts   = teams.map(t => ({ value: t.id, label: t.name }))

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>

      {/* Hero */}
      <div style={{
        textAlign: 'center',
        padding: '48px 16px 40px',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Radial gold glow */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -60%)',
          width: 600,
          height: 300,
          background: 'radial-gradient(ellipse, rgba(201,168,76,0.18) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <h1 style={{
          fontFamily: '"Bebas Neue", sans-serif',
          fontSize: 72,
          letterSpacing: '0.06em',
          lineHeight: 1,
          margin: '0 0 12px',
          position: 'relative',
        }}>
          <span style={{ color: '#e6e9f4' }}>UEFA</span>
          <span style={{ color: '#c9a84c' }}>graphics</span>
        </h1>

        <p style={{ color: '#4d5e7a', fontSize: 14, maxWidth: 400, margin: '0 auto 28px', lineHeight: 1.6 }}>
          Football analytics — shot maps, radars, xG timelines, league tables and more.
          Data from Understat &amp; football-data.org.
        </p>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={() => navigate('/player')}
            style={{
              background: '#c9a84c',
              color: '#06080f',
              border: 'none',
              borderRadius: 5,
              padding: '9px 20px',
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 0 20px rgba(201,168,76,0.22)',
              transition: 'all 0.15s',
            }}
          >
            Explore Players
          </button>
          <button
            onClick={() => navigate('/team')}
            style={{
              background: 'transparent',
              color: '#4d5e7a',
              border: '1px solid #1a2235',
              borderRadius: 5,
              padding: '9px 20px',
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            Browse Teams
          </button>
        </div>

        {/* Separator */}
        <div style={{
          height: 1,
          background: 'linear-gradient(90deg, transparent, rgba(201,168,76,0.35), transparent)',
          marginTop: 40,
        }} />
      </div>

      {/* Search panel */}
      <div style={{ marginBottom: 40 }}>
        {/* Segment tabs */}
        <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid #1a2235', marginBottom: 0 }}>
          {SEARCH_TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '9px 18px',
                marginBottom: -1,
                fontSize: 13,
                fontWeight: tab === t ? 600 : 400,
                color: tab === t ? '#c9a84c' : '#4d5e7a',
                borderBottom: `2px solid ${tab === t ? '#c9a84c' : 'transparent'}`,
                background: 'none',
                border: 'none',
                borderBottomWidth: 2,
                borderBottomStyle: 'solid',
                borderBottomColor: tab === t ? '#c9a84c' : 'transparent',
                cursor: 'pointer',
                transition: 'all 0.15s',
                outline: 'none',
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Panel */}
        <div style={{
          background: '#0c1321',
          border: '1px solid #1a2235',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
          padding: 20,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
            <Select
              label="League"
              value={leagueId}
              options={leagueOpts.length ? leagueOpts : [{ value: leagueId, label: leagueId }]}
              onChange={setLeagueId}
            />
            <Select
              label="Season"
              value={season}
              options={SEASON_OPTS}
              onChange={v => setSeason(Number(v))}
            />
          </div>

          {tab === 'Player' && (
            <SearchInput
              label="Player"
              placeholder="Search player name…"
              onSearch={searchPlayers}
              onSelect={player => {
                const id   = (player as { id?: string }).id
                const name = player.name ?? player.player ?? ''
                if (id) {
                  navigate(`/player/${id}?season=${season}&league=${leagueId}&name=${encodeURIComponent(name)}`)
                } else {
                  navigate(`/player/${encodeURIComponent(name)}?season=${season}&league=${leagueId}&source=fbref`)
                }
              }}
            />
          )}

          {tab === 'Team' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <Select
                label="Team"
                value={selectedTeam?.id ?? ''}
                options={teamOpts.length ? teamOpts : [{ value: '', label: 'Loading…' }]}
                onChange={id => {
                  const team = teams.find(t => t.id === id) ?? null
                  setSelectedTeam(team)
                }}
              />
              {selectedTeam && (
                <button
                  onClick={() => navigate(`/team/${selectedTeam.id}?name=${encodeURIComponent(selectedTeam.name)}&season=${season}&league=${leagueId}`)}
                  style={{
                    width: '100%',
                    background: '#c9a84c',
                    color: '#06080f',
                    border: 'none',
                    borderRadius: 5,
                    padding: '8px 0',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  View {selectedTeam.name} Infographics →
                </button>
              )}
            </div>
          )}

          {tab === 'League' && (
            <button
              onClick={() => navigate(`/league/${leagueId}?season=${season}`)}
              style={{
                width: '100%',
                background: '#c9a84c',
                color: '#06080f',
                border: 'none',
                borderRadius: 5,
                padding: '8px 0',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              View League Overview →
            </button>
          )}
        </div>
      </div>

      {/* Feature grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {FEATURES.map(({ icon, title, desc }) => (
          <div
            key={title}
            style={{
              background: '#0c1321',
              border: '1px solid #1a2235',
              borderRadius: 8,
              padding: 18,
              boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
              transition: 'all 0.15s',
              cursor: 'default',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.borderColor = 'rgba(201,168,76,0.3)'
              ;(e.currentTarget as HTMLElement).style.boxShadow = '0 2px 12px rgba(0,0,0,0.4), 0 0 16px rgba(201,168,76,0.08)'
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.borderColor = '#1a2235'
              ;(e.currentTarget as HTMLElement).style.boxShadow = '0 2px 12px rgba(0,0,0,0.4)'
            }}
          >
            <div style={{ fontSize: 20, marginBottom: 6, color: '#c9a84c' }}>{icon}</div>
            <div style={{
              fontFamily: '"Bebas Neue", sans-serif',
              fontSize: 16,
              letterSpacing: '0.05em',
              color: '#e6e9f4',
              marginBottom: 4,
            }}>{title}</div>
            <div style={{ fontSize: 11, color: '#4d5e7a', lineHeight: 1.5 }}>{desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
