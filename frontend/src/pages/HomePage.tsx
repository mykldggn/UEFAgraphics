import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Select from '../components/ui/Select'
import SearchInput from '../components/ui/SearchInput'
import { leaguesApi, type League, type Team } from '../api/leagues'
import { SEASONS, CURRENT_SEASON } from '../utils/constants'

const SEASON_OPTS  = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))
const SEARCH_TABS  = ['Player', 'Team', 'League'] as const
type SearchTab = typeof SEARCH_TABS[number]

const _s = { width: 22, height: 22, display: 'block' as const }

const FEATURES: { icon: React.ReactNode; title: string; desc: string }[] = [
  {
    icon: (
      <svg style={_s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="9"/>
        <circle cx="12" cy="12" r="5"/>
        <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>
        <line x1="12" y1="2" x2="12" y2="4"/>
        <line x1="12" y1="20" x2="12" y2="22"/>
        <line x1="2" y1="12" x2="4" y2="12"/>
        <line x1="20" y1="12" x2="22" y2="12"/>
      </svg>
    ),
    title: 'Shot Maps',
    desc: 'xG-weighted shots, distance & goal distribution',
  },
  {
    icon: (
      <svg style={_s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <polygon points="12,2 20.5,7 20.5,17 12,22 3.5,17 3.5,7"/>
        <line x1="12" y1="2" x2="12" y2="12" strokeWidth="0.8"/>
        <line x1="20.5" y1="7" x2="12" y2="12" strokeWidth="0.8"/>
        <line x1="20.5" y1="17" x2="12" y2="12" strokeWidth="0.8"/>
        <line x1="12" y1="22" x2="12" y2="12" strokeWidth="0.8"/>
        <line x1="3.5" y1="17" x2="12" y2="12" strokeWidth="0.8"/>
        <line x1="3.5" y1="7" x2="12" y2="12" strokeWidth="0.8"/>
        <polygon points="12,6 16.5,8.5 16.5,15.5 12,18 7.5,15.5 7.5,8.5" strokeWidth="0.8"/>
      </svg>
    ),
    title: 'Radars',
    desc: 'Per-90 percentile pizza charts vs peers',
  },
  {
    icon: (
      <svg style={_s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <line x1="2" y1="20" x2="2" y2="4" strokeWidth="1"/>
        <line x1="2" y1="20" x2="22" y2="20" strokeWidth="1"/>
        <polyline points="2,20 5,17 9,14 13,9 17,7 22,4" strokeWidth="1.5"/>
        <circle cx="5" cy="17" r="1.5" fill="currentColor" stroke="none"/>
        <circle cx="9" cy="14" r="1.5" fill="currentColor" stroke="none"/>
        <circle cx="13" cy="9" r="1.5" fill="currentColor" stroke="none"/>
        <circle cx="17" cy="7" r="1.5" fill="currentColor" stroke="none"/>
      </svg>
    ),
    title: 'Career xG',
    desc: 'Cumulative xG vs goals across seasons',
  },
  {
    icon: (
      <svg style={_s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="3" y="5" width="13" height="2.5" rx="1.2" fill="currentColor" stroke="none"/>
        <rect x="3" y="11" width="9" height="2.5" rx="1.2" fill="currentColor" stroke="none" opacity="0.75"/>
        <rect x="3" y="17" width="16" height="2.5" rx="1.2" fill="currentColor" stroke="none" opacity="0.5"/>
      </svg>
    ),
    title: 'Summary Cards',
    desc: 'Season stats at a glance with progress bars',
  },
  {
    icon: (
      <svg style={_s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <line x1="2" y1="19" x2="22" y2="19" strokeWidth="1"/>
        <circle cx="4" cy="19" r="1.5" fill="currentColor" stroke="none"/>
        <circle cx="9" cy="19" r="1.5" fill="currentColor" stroke="none"/>
        <circle cx="14" cy="19" r="1.5" fill="currentColor" stroke="none"/>
        <circle cx="19" cy="19" r="1.5" fill="currentColor" stroke="none"/>
        <polyline points="4,19 4,13 9,15 9,10 14,13 14,7 19,19" strokeWidth="1.5"/>
      </svg>
    ),
    title: 'xG Timeline',
    desc: 'Match-by-match xG for & against',
  },
  {
    icon: (
      <svg style={_s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="1.5" y="13" width="5" height="8" rx="1"/>
        <rect x="9.5" y="8" width="5" height="13" rx="1"/>
        <rect x="17.5" y="10.5" width="5" height="10.5" rx="1"/>
        <circle cx="4" cy="9.5" r="2.2"/>
        <circle cx="12" cy="4.5" r="2.2"/>
        <circle cx="20" cy="7" r="2.2"/>
      </svg>
    ),
    title: 'League Tables',
    desc: 'Standings, form, position race & leaderboards',
  },
]

export default function HomePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialTab = (searchParams.get('tab') as SearchTab | null) ?? 'Player'
  const [tab, setTab]             = useState<SearchTab>(SEARCH_TABS.includes(initialTab as SearchTab) ? initialTab : 'Player')
  const [leagues, setLeagues]     = useState<League[]>([])
  const [leagueId, setLeagueId]   = useState('ENG-1')
  const [season, setSeason]       = useState(CURRENT_SEASON)
  const [teams, setTeams]         = useState<Team[]>([])
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null)

  useEffect(() => {
    const t = searchParams.get('tab') as SearchTab | null
    if (t && SEARCH_TABS.includes(t)) setTab(t)
  }, [searchParams])

  useEffect(() => {
    leaguesApi.list().then(setLeagues).catch(() => {})
  }, [])

  useEffect(() => {
    if (tab === 'Team') {
      leaguesApi.teams(leagueId, season)
        .then(r => {
          setTeams(r.teams)
          if (r.teams.length > 0) setSelectedTeam(r.teams[0])
        })
        .catch(() => setTeams([]))
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
    <div>

      {/* Hero — full AppLayout width, overflow hidden so UCL logo stays inside */}
      <div style={{
        textAlign: 'center',
        padding: '48px 16px 40px',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* UCL logo watermark — sits behind the title text, clipped by overflow:hidden */}
        <img
          src="/ucl-logo.png"
          alt=""
          aria-hidden
          style={{
            position: 'absolute',
            top: '30%',
            left: '50%',
            transform: 'translate(-50%, -30%)',
            width: 400,
            opacity: 0.14,
            filter: 'invert(1) grayscale(1)',
            mixBlendMode: 'screen',
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        />

        {/* Radial gold glow */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -60%)',
          width: 600,
          height: 320,
          background: 'radial-gradient(ellipse, rgba(201,168,76,0.22) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* Trophy — left (mirrored) */}
        <img
          src="/ucl-trophy.png"
          alt=""
          aria-hidden
          style={{
            position: 'absolute',
            left: 'calc(50% - 400px)',
            top: '50%',
            transform: 'translateY(-52%) scaleX(-1)',
            width: 180,
            opacity: 0.65,
            filter: 'grayscale(0.1)',
            maskImage: 'radial-gradient(ellipse 90% 95% at 15% 50%, black 30%, transparent 100%)',
            WebkitMaskImage: 'radial-gradient(ellipse 90% 95% at 15% 50%, black 30%, transparent 100%)',
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        />

        {/* Trophy — right */}
        <img
          src="/ucl-trophy.png"
          alt=""
          aria-hidden
          style={{
            position: 'absolute',
            right: 'calc(50% - 400px)',
            top: '50%',
            transform: 'translateY(-52%)',
            width: 180,
            opacity: 0.65,
            filter: 'grayscale(0.1)',
            maskImage: 'radial-gradient(ellipse 90% 95% at 85% 50%, black 30%, transparent 100%)',
            WebkitMaskImage: 'radial-gradient(ellipse 90% 95% at 85% 50%, black 30%, transparent 100%)',
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        />

        <h1 style={{
          fontFamily: '"Bebas Neue", sans-serif',
          fontSize: 82,
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


        {/* Separator */}
        <div style={{
          height: 1,
          background: 'linear-gradient(90deg, transparent, rgba(201,168,76,0.35), transparent)',
          marginTop: 40,
        }} />
      </div>

      {/* Search panel + features — constrained to 720px */}
      <div style={{ maxWidth: 720, margin: '0 auto' }}>

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
                const id     = (player as { id?: string }).id
                const name   = player.name ?? (player as { player?: string }).player ?? ''
                const rawSrc = (player as { source?: string }).source ?? 'understat'
                // TSDB players have no FotMob/Understat ID — treat as fotmob name-based lookup
                const source = rawSrc === 'tsdb' ? 'fotmob' : rawSrc
                if (id && rawSrc !== 'tsdb') {
                  navigate(`/player/${id}?season=${season}&league=${leagueId}&name=${encodeURIComponent(name)}&source=${source}`)
                } else {
                  navigate(`/player/${encodeURIComponent(name)}?season=${season}&league=${leagueId}&source=fotmob&name=${encodeURIComponent(name)}`)
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
            <div style={{ marginBottom: 8, color: '#c9a84c' }}>{icon}</div>
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

      </div> {/* end narrow wrapper */}
    </div>
  )
}
