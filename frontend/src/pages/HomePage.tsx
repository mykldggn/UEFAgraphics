import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import Select from '../components/ui/Select'
import SearchInput from '../components/ui/SearchInput'
import { leaguesApi, type League, type Team } from '../api/leagues'
import { SEASONS, UNDERSTAT_LEAGUES, CURRENT_SEASON } from '../utils/constants'

const SEASON_OPTS  = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))
const LEAGUE_TABS  = ['Player', 'Team', 'League'] as const
type Tab = typeof LEAGUE_TABS[number]

export default function HomePage() {
  const navigate = useNavigate()
  const [tab, setTab]             = useState<Tab>('Player')
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

  // Player search: try FBref first, fallback to Understat
  const searchPlayers = useCallback(async (q: string) => {
    const fbres = await leaguesApi.searchPlayers(leagueId, q, season).catch(() => ({ results: [] }))
    if (fbres.results.length) return fbres.results
    const us = await leaguesApi.understatSearch(q).catch(() => ({ results: [] }))
    return us.results
  }, [leagueId, season])

  const leagueOpts = leagues.map(l => ({ value: l.id, label: `${l.label} (${l.country})` }))
  const teamOpts   = teams.map(t => ({ value: t.id, label: t.name }))

  return (
    <div className="max-w-3xl mx-auto space-y-10">
      {/* Hero */}
      <div className="text-center space-y-2 pt-4">
        <h1 className="text-3xl font-bold">
          UEFA<span className="text-accent">graphics</span>
        </h1>
        <p className="text-sub text-sm">
          Football analytics — shot maps, radars, xG timelines, league tables and more.
          Data from Understat &amp; football-data.org. No login required.
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 bg-card border border-border rounded-lg p-1 w-fit mx-auto">
        {LEAGUE_TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t ? 'bg-accent text-white' : 'text-sub hover:text-white'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Selectors */}
      <div className="bg-card border border-border rounded-xl p-6 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
          <div className="space-y-3">
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
                className="w-full bg-accent hover:bg-blue-600 text-white font-medium rounded-md py-2 text-sm transition-colors"
              >
                View {selectedTeam.name} Infographics →
              </button>
            )}
          </div>
        )}

        {tab === 'League' && (
          <button
            onClick={() => navigate(`/league/${leagueId}?season=${season}`)}
            className="w-full bg-accent hover:bg-blue-600 text-white font-medium rounded-md py-2 text-sm transition-colors"
          >
            View League Overview →
          </button>
        )}
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-center">
        {[
          { emoji: '🎯', title: 'Shot Maps',       desc: 'xG, distance, goal/no-goal' },
          { emoji: '🍕', title: 'Radars',           desc: 'Per-90 percentile pizza charts' },
          { emoji: '📈', title: 'Career xG',        desc: 'Cumulative xG vs goals' },
          { emoji: '📋', title: 'Summary Cards',    desc: 'Season stats at a glance' },
          { emoji: '⚡', title: 'xG Timeline',      desc: 'Match-by-match xG for & against' },
          { emoji: '🏆', title: 'League Tables',    desc: 'Standings, form & leader boards' },
        ].map(({ emoji, title, desc }) => (
          <div key={title} className="bg-card border border-border rounded-lg p-4 space-y-1">
            <div className="text-2xl">{emoji}</div>
            <div className="text-sm font-semibold">{title}</div>
            <div className="text-xs text-sub">{desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
