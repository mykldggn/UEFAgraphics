import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import Select from '../components/ui/Select'
import TabBar from '../components/ui/TabBar'
import { leaguesApi, type TableRow, type LeaderEntry } from '../api/leagues'
import { SEASONS, CURRENT_SEASON } from '../utils/constants'


const SEASON_OPTS = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))

const PAGE_TABS = [
  { id: 'table',   label: 'Table'         },
  { id: 'race',    label: 'Position Race' },
  { id: 'leaders', label: 'Leaders'       },
]

// 20-colour palette for team lines — vivid spectrum
const PALETTE = [
  '#4a9eff','#e63946','#4dc478','#c9a84c','#8B5CF6',
  '#06B6D4','#EC4899','#84CC16','#F97316','#6366F1',
  '#14B8A6','#E11D48','#0EA5E9','#A3E635','#7C3AED',
  '#FB923C','#34D399','#FBBF24','#60A5FA','#F87171',
]

const FORM_BG: Record<string, string> = {
  W: '#1fa355',
  D: '#9a6e00',
  L: '#c42b2b',
}

function FormPills({ form }: { form: string }) {
  const chars = form.replace(/[^WDLwdl]/gi, '').toUpperCase().split('')
  if (!chars.length) return <span style={{ color: '#4d5e7a' }}>—</span>
  return (
    <div style={{ display: 'flex', gap: 3, justifyContent: 'flex-end' }}>
      {chars.map((r, i) => (
        <span
          key={i}
          style={{
            backgroundColor: FORM_BG[r] ?? '#374151',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 20,
            height: 20,
            borderRadius: 3,
            fontSize: 9,
            fontWeight: 700,
            color: '#fff',
          }}
        >
          {r}
        </span>
      ))}
    </div>
  )
}

// Zone colours
const ZONE_COLOR = {
  champion:    '#c9a84c',  // gold
  promotion:   '#16a34a',  // green (automatic promotion, no European)
  playoff:     '#4ade80',  // light green (promotion playoff)
  cl:          '#1e3a8a',  // navy
  el:          '#f97316',  // orange
  ecl:         '#84cc16',  // lime
  rel_playoff: '#f97316',  // orange (relegation playoff)
  relegation:  '#e63946',  // red
} as const

type ZoneType = keyof typeof ZONE_COLOR

interface ZoneEntry { from: number; to: number; type: ZoneType }

// Per-league zone definitions — covers promotion, European, and relegation slots
const LEAGUE_ZONES: Record<string, ZoneEntry[]> = {
  // ── England ─────────────────────────────────────────────────────────────
  'ENG-1': [  // Premier League, 20 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 4, type: 'cl' },
    { from: 5, to: 5, type: 'el' },
    { from: 6, to: 6, type: 'ecl' },
    { from: 18, to: 20, type: 'relegation' },
  ],
  'ENG-2': [  // Championship, 24 teams — no European football
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 2, type: 'promotion' },
    { from: 3, to: 6,  type: 'playoff' },
    { from: 21, to: 24, type: 'relegation' },  // 4 relegated
  ],
  'ENG-3': [  // League One, 24 teams
    { from: 1, to: 1,  type: 'champion' },
    { from: 2, to: 2,  type: 'promotion' },
    { from: 3, to: 6,  type: 'playoff' },
    { from: 21, to: 24, type: 'relegation' },
  ],
  'ENG-4': [  // League Two, 24 teams — top 3 auto, 4-7 playoff
    { from: 1, to: 1,  type: 'champion' },
    { from: 2, to: 3,  type: 'promotion' },
    { from: 4, to: 7,  type: 'playoff' },
    { from: 23, to: 24, type: 'relegation' },  // 2 relegated to non-league
  ],
  // ── Spain ───────────────────────────────────────────────────────────────
  'ESP-1': [  // La Liga, 20 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 4, type: 'cl' },
    { from: 5, to: 6, type: 'el' },
    { from: 7, to: 7, type: 'ecl' },
    { from: 18, to: 20, type: 'relegation' },
  ],
  // ── Germany ─────────────────────────────────────────────────────────────
  'DEU-1': [  // Bundesliga, 18 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 4, type: 'cl' },
    { from: 5, to: 5, type: 'el' },
    { from: 6, to: 6, type: 'ecl' },
    { from: 16, to: 16, type: 'rel_playoff' },
    { from: 17, to: 18, type: 'relegation' },
  ],
  'DEU-2': [  // 2. Bundesliga, 18 teams
    { from: 1, to: 1,  type: 'champion' },
    { from: 2, to: 2,  type: 'promotion' },
    { from: 3, to: 3,  type: 'playoff' },
    { from: 16, to: 16, type: 'rel_playoff' },
    { from: 17, to: 18, type: 'relegation' },
  ],
  // ── Italy ────────────────────────────────────────────────────────────────
  'ITA-1': [  // Serie A, 20 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 4, type: 'cl' },
    { from: 5, to: 6, type: 'el' },
    { from: 7, to: 7, type: 'ecl' },
    { from: 18, to: 20, type: 'relegation' },
  ],
  // ── France ──────────────────────────────────────────────────────────────
  'FRA-1': [  // Ligue 1, 18 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 3, type: 'cl' },
    { from: 4, to: 5, type: 'el' },
    { from: 6, to: 6, type: 'ecl' },
    { from: 16, to: 16, type: 'rel_playoff' },
    { from: 17, to: 18, type: 'relegation' },
  ],
  // ── Netherlands ──────────────────────────────────────────────────────────
  'NED-1': [  // Eredivisie, 18 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 2, type: 'cl' },
    { from: 3, to: 3, type: 'el' },
    { from: 4, to: 6, type: 'ecl' },
    { from: 16, to: 16, type: 'rel_playoff' },
    { from: 17, to: 18, type: 'relegation' },
  ],
  // ── Portugal ─────────────────────────────────────────────────────────────
  'PRT-1': [  // Primeira Liga, 18 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 2, type: 'cl' },
    { from: 3, to: 4, type: 'el' },
    { from: 5, to: 5, type: 'ecl' },
    { from: 16, to: 17, type: 'rel_playoff' },
    { from: 18, to: 18, type: 'relegation' },
  ],
  // ── Belgium ──────────────────────────────────────────────────────────────
  'BEL-1': [  // Pro League, 18 teams (simplified — ignores Championship playoffs)
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 2, type: 'cl' },
    { from: 3, to: 4, type: 'el' },
    { from: 5, to: 5, type: 'ecl' },
    { from: 16, to: 18, type: 'relegation' },
  ],
  // ── Scotland ─────────────────────────────────────────────────────────────
  'SCO-1': [  // Scottish Premiership, 12 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 2, type: 'cl' },
    { from: 3, to: 4, type: 'el' },
    { from: 5, to: 6, type: 'ecl' },
    { from: 11, to: 11, type: 'rel_playoff' },
    { from: 12, to: 12, type: 'relegation' },
  ],
  // ── Turkey ───────────────────────────────────────────────────────────────
  'TUR-1': [  // Süper Lig, 19 teams
    { from: 1, to: 1, type: 'champion' },
    { from: 2, to: 2, type: 'cl' },
    { from: 3, to: 4, type: 'el' },
    { from: 5, to: 5, type: 'ecl' },
    { from: 16, to: 17, type: 'rel_playoff' },
    { from: 18, to: 19, type: 'relegation' },
  ],
}

// Build dynamic zone key for the current league
function buildZoneKey(leagueId: string | undefined): { color: string; label: string }[] {
  const zones = leagueId ? LEAGUE_ZONES[leagueId] : undefined
  if (!zones) return [
    { color: ZONE_COLOR.champion, label: 'League Winners' },
    { color: ZONE_COLOR.cl, label: 'Champions League' },
    { color: ZONE_COLOR.el, label: 'Europa League' },
    { color: ZONE_COLOR.ecl, label: 'Conference League' },
    { color: ZONE_COLOR.relegation, label: 'Relegation' },
  ]
  const seen = new Set<ZoneType>()
  const key: { color: string; label: string }[] = []
  const LABELS: Record<ZoneType, string> = {
    champion:    'League Winners',
    promotion:   'Automatic Promotion',
    playoff:     'Promotion Playoff',
    cl:          'Champions League',
    el:          'Europa League',
    ecl:         'Conference League',
    rel_playoff: 'Relegation Playoff',
    relegation:  'Relegation',
  }
  for (const z of zones) {
    if (!seen.has(z.type)) {
      seen.add(z.type)
      key.push({ color: ZONE_COLOR[z.type], label: LABELS[z.type] })
    }
  }
  return key
}

function LeaderBoard({
  title, entries, unit = '', onPlayerClick,
}: {
  title: string
  entries: LeaderEntry[]
  unit?: string
  onPlayerClick?: (player: string, team: string) => void
}) {
  return (
    <div style={{
      background: '#0c1321',
      border: '1px solid #1a2235',
      borderRadius: 8,
      padding: '14px 16px',
      boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
    }}>
      <h3 style={{
        fontFamily: '"Bebas Neue", sans-serif',
        fontSize: 15,
        letterSpacing: '0.05em',
        color: '#e6e9f4',
        margin: '0 0 10px',
        paddingBottom: 8,
        borderBottom: '1px solid #1a2235',
      }}>{title}</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {entries.slice(0, 10).map((e, i) => (
          <div
            key={i}
            onClick={() => onPlayerClick?.(e.player, e.team)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              padding: '4px 6px',
              borderRadius: 4,
              cursor: onPlayerClick ? 'pointer' : 'default',
              transition: 'background 0.1s',
            }}
            onMouseEnter={e2 => { if (onPlayerClick) (e2.currentTarget as HTMLElement).style.background = 'rgba(201,168,76,0.07)' }}
            onMouseLeave={e2 => { if (onPlayerClick) (e2.currentTarget as HTMLElement).style.background = 'transparent' }}
          >
            <span style={{
              fontFamily: '"Bebas Neue", sans-serif',
              fontSize: 13,
              color: i === 0 ? '#c9a84c' : '#1e2c44',
              width: 18,
              textAlign: 'right',
              flexShrink: 0,
            }}>{i + 1}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <span style={{ color: '#e6e9f4', fontWeight: 500, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.player}</span>
              <span style={{ color: '#4d5e7a', fontSize: 10 }}>{e.team}</span>
            </div>
            <span style={{
              fontFamily: '"Bebas Neue", sans-serif',
              fontSize: 18,
              color: '#c9a84c',
              fontWeight: 700,
              flexShrink: 0,
            }}>{e.value}{unit}</span>
          </div>
        ))}
        {entries.length === 0 && <p style={{ color: '#4d5e7a', fontSize: 12 }}>No data</p>}
      </div>
    </div>
  )
}

export default function LeaguePage() {
  const { leagueId } = useParams<{ leagueId: string }>()
  const [params]     = useSearchParams()
  const navigate     = useNavigate()

  const [activeTab, setActiveTab] = useState('table')
  const [season, setSeason]       = useState(Number(params.get('season') ?? CURRENT_SEASON))
  const [table, setTable]         = useState<TableRow[]>([])
  const [posHistory, setPosHistory] = useState<{ teams: string[]; history: Record<string, number>[] } | null>(null)
  const [leaders, setLeaders]     = useState<Record<string, LeaderEntry[]> | null>(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState<string | null>(null)
  const [focusTeam, setFocusTeam] = useState<string | null>(null)
  const [teamColors, setTeamColors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!leagueId) return
    setLoading(true); setError(null)
    setTable([]); setPosHistory(null); setLeaders(null)

    const tableP = leaguesApi.table(leagueId, season)
      .then(r => setTable(r.table))
      .catch(() => {})

    const posP = leaguesApi.positionHistory(leagueId, season)
      .then(r => setPosHistory({ teams: r.teams, history: r.history }))
      .catch(() => {})

    const leadP = leaguesApi.leaders(leagueId, season)
      .then(r => setLeaders(r as unknown as Record<string, LeaderEntry[]>))
      .catch(() => {})

    const colorP = leaguesApi.teamColors(leagueId, season)
      .then(r => setTeamColors(r))
      .catch(() => {})

    Promise.all([tableP, posP, leadP, colorP])
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [leagueId, season])

  if (!leagueId) return null

  const COLS: { key: string; label: string }[] = [
    { key: 'played',        label: 'MP' },
    { key: 'wins',          label: 'W'  },
    { key: 'draws',         label: 'D'  },
    { key: 'losses',        label: 'L'  },
    { key: 'goals_for',     label: 'GF' },
    { key: 'goals_against', label: 'GA' },
    { key: 'goal_diff',     label: 'GD' },
    { key: 'points',        label: 'Pts'},
  ].filter(c => table.length > 0 && table[0][c.key] != null)

  const teamColorMap: Record<string, string> = {}
  if (posHistory) {
    posHistory.teams.forEach((t, i) => {
      // Use real team color if available, fall back to palette
      teamColorMap[t] = teamColors[t] || PALETTE[i % PALETTE.length]
    })
  }
  const numTeams = posHistory?.teams.length ?? 20

  const leagueName = leagueId.replace('-', ' ')
  const numInLeague = table.length || 20

  function posZoneColor(pos: number): string {
    const zones = leagueId ? LEAGUE_ZONES[leagueId] : undefined
    if (!zones) {
      // Sensible defaults for unknown leagues
      if (pos === 1) return ZONE_COLOR.champion
      if (pos <= 4)  return ZONE_COLOR.cl
      if (pos > numInLeague - 3) return ZONE_COLOR.relegation
      return 'transparent'
    }
    const zone = zones.find(z => pos >= z.from && pos <= z.to)
    return zone ? ZONE_COLOR[zone.type] : 'transparent'
  }

  // Row suffix badges: champion crown, relegated R
  function rowBadge(pos: number): string | null {
    if (pos === 1 && table[0]?.played != null && Number(table[0].played) >= 34) return '👑'
    if (pos > numInLeague - 3 && table[0]?.played != null && Number(table[0].played) >= 34) return 'R'
    return null
  }

  const UNDERSTAT_LEAGUES = new Set(['ENG-1', 'ESP-1', 'DEU-1', 'ITA-1', 'FRA-1'])
  const isUnderstatLeague = UNDERSTAT_LEAGUES.has(leagueId ?? '')

  function handleTeamClick(row: TableRow) {
    // Use the numeric fdorg team_id in the URL so non-top-5 infographics can fetch match results.
    // team_name is passed as a query param for display + matching purposes.
    const teamId = row.team_id != null ? String(row.team_id) : encodeURIComponent(String(row.team))
    navigate(`/team/${encodeURIComponent(teamId)}?name=${encodeURIComponent(String(row.team))}&league=${leagueId}&season=${season}`)
  }

  function handlePlayerClick(player: string, _team: string) {
    const source = isUnderstatLeague ? 'understat' : 'fotmob'
    navigate(`/player/${encodeURIComponent(player)}?season=${season}&league=${leagueId}&source=${source}&name=${encodeURIComponent(player)}`)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(90deg, rgba(201,168,76,0.10), transparent)',
        borderLeft: '4px solid #c9a84c',
        borderRadius: '0 6px 6px 0',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <h1 style={{
          fontFamily: '"Bebas Neue", sans-serif',
          fontSize: 28,
          letterSpacing: '0.04em',
          color: '#e6e9f4',
          margin: 0,
          textTransform: 'uppercase',
        }}>
          {leagueName}
        </h1>
        <Select value={season} options={SEASON_OPTS} onChange={v => setSeason(Number(v))} />
      </div>

      <TabBar tabs={PAGE_TABS} active={activeTab} onChange={setActiveTab} />

{loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0', color: '#4d5e7a', fontSize: 13 }}>
          Loading…
        </div>
      )}
      {error && (
        <div style={{
          background: 'rgba(230,57,70,0.1)',
          border: '1px solid rgba(230,57,70,0.3)',
          color: '#e63946',
          borderRadius: 8,
          padding: '12px 16px',
          fontSize: 13,
        }}>{error}</div>
      )}

      {/* ── TABLE ── */}
      {!loading && activeTab === 'table' && (
        table.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Zone key — dynamic per league */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, paddingLeft: 4 }}>
              {buildZoneKey(leagueId).map(z => (
                <div key={z.label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#4d5e7a' }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: z.color, flexShrink: 0 }} />
                  {z.label}
                </div>
              ))}
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #1a2235' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left', width: 32, fontSize: 10, color: '#4d5e7a', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 500 }}>#</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 10, color: '#4d5e7a', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 500 }}>Team</th>
                    {COLS.map(c => (
                      <th key={c.key} style={{ padding: '8px 12px', textAlign: 'right', fontSize: 10, color: '#4d5e7a', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 500 }}>
                        {c.label}
                      </th>
                    ))}
                    <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 10, color: '#4d5e7a', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 500 }}>Form</th>
                  </tr>
                </thead>
                <tbody>
                  {table.map((row, i) => {
                    const badge = rowBadge(i + 1)
                    return (
                      <tr
                        key={i}
                        onClick={() => handleTeamClick(row)}
                        style={{
                          borderBottom: '1px solid rgba(26,34,53,0.6)',
                          borderLeft: `3px solid ${posZoneColor(i + 1)}`,
                          background: i % 2 === 1 ? 'rgba(201,168,76,0.025)' : 'transparent',
                          transition: 'background 0.1s',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(201,168,76,0.07)')}
                        onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 1 ? 'rgba(201,168,76,0.025)' : 'transparent')}
                      >
                        <td style={{ padding: '8px 12px', color: '#4d5e7a', fontFamily: '"Bebas Neue", sans-serif', fontSize: 16, letterSpacing: '0.04em' }}>{i + 1}</td>
                        <td style={{ padding: '8px 12px', color: '#e6e9f4', fontWeight: 500 }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            {badge && (
                              <span style={{
                                fontSize: badge === '👑' ? 12 : 9,
                                fontWeight: 700,
                                color: badge === '👑' ? '#c9a84c' : '#e63946',
                                letterSpacing: 0,
                              }}>{badge}</span>
                            )}
                            {row.team}
                          </span>
                        </td>
                        {COLS.map(c => (
                          <td key={c.key} style={{
                            padding: '8px 12px',
                            textAlign: 'right',
                            color: c.key === 'points' ? '#c9a84c' : '#4d5e7a',
                            fontFamily: c.key === 'points' ? '"Bebas Neue", sans-serif' : 'Inter, sans-serif',
                            fontSize: c.key === 'points' ? 16 : 13,
                            fontWeight: c.key === 'points' ? 700 : 400,
                            letterSpacing: c.key === 'points' ? '0.04em' : 0,
                          }}>
                            {row[c.key] != null ? String(row[c.key]) : '—'}
                          </td>
                        ))}
                        <td style={{ padding: '8px 12px' }}><FormPills form={String(row.form ?? '')} /></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          !error && <div style={{ textAlign: 'center', padding: '48px 0', color: '#4d5e7a', fontSize: 13 }}>No table data available.</div>
        )
      )}

      {/* ── POSITION RACE ── */}
      {!loading && activeTab === 'race' && (
        posHistory && posHistory.history.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <p style={{ fontSize: 12, color: '#4d5e7a', margin: 0 }}>
              League position after each match played.
              {posHistory.history.length < 34 ? ' Data reflects the current point in the season.' : ''}
              {' '}Click a team to highlight.
            </p>
            <div style={{
              background: '#0c1321',
              border: '1px solid #1a2235',
              borderRadius: 8,
              padding: '16px 8px',
              boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
            }}>
              <ResponsiveContainer width="100%" height={480}>
                <LineChart data={posHistory.history} layout="horizontal"
                  margin={{ top: 10, right: 30, bottom: 20, left: 10 }}>
                  <XAxis dataKey="match" type="number"
                    domain={[1, posHistory.history.length]}
                    ticks={(() => {
                      const n = posHistory.history.length
                      const step = n <= 20 ? 1 : n <= 38 ? 2 : 4
                      const t: number[] = []
                      for (let i = 1; i <= n; i += step) t.push(i)
                      if (t[t.length - 1] !== n) t.push(n)
                      return t
                    })()}
                    tick={{ fill: '#4d5e7a', fontSize: 10 }}
                    label={{ value: 'Match', position: 'insideBottom', offset: -4, fill: '#4d5e7a', fontSize: 10 }} />
                  <YAxis reversed domain={[1, numTeams]} tickCount={numTeams}
                    tick={{ fill: '#4d5e7a', fontSize: 10 }}
                    label={{ value: 'Position', angle: -90, position: 'insideLeft', fill: '#4d5e7a', fontSize: 10 }} />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload?.length) return null
                      // Sort all entries by position value ascending
                      const sorted = [...payload]
                        .filter(p => p.value != null)
                        .sort((a, b) => Number(a.value) - Number(b.value))
                      // Show: focused team always, otherwise top 5 + bottom 3
                      const focused = focusTeam
                        ? sorted.filter(p => p.dataKey === focusTeam)
                        : []
                      const top5   = sorted.slice(0, 5)
                      const bottom3 = sorted.slice(-3)
                      const shown  = focusTeam
                        ? focused
                        : [...top5, ...bottom3].filter((p, i, arr) =>
                            arr.findIndex(x => x.dataKey === p.dataKey) === i
                          )
                      return (
                        <div style={{
                          background: '#0c1321',
                          border: '1px solid #1a2235',
                          borderRadius: 6,
                          padding: '8px 12px',
                          fontSize: 11,
                          minWidth: 140,
                        }}>
                          <div style={{ color: '#4d5e7a', marginBottom: 6, fontWeight: 600 }}>
                            Match {label}
                          </div>
                          {shown.map(p => (
                            <div key={String(p.dataKey)} style={{
                              display: 'flex', alignItems: 'center', gap: 6,
                              marginBottom: 3,
                            }}>
                              <span style={{
                                width: 7, height: 7, borderRadius: '50%',
                                background: String(p.stroke), flexShrink: 0,
                              }} />
                              <span style={{ color: '#e6e9f4', flex: 1 }}>{p.dataKey}</span>
                              <span style={{
                                fontFamily: '"Bebas Neue", sans-serif',
                                fontSize: 14, color: '#c9a84c', marginLeft: 8,
                              }}>{p.value}</span>
                            </div>
                          ))}
                          {!focusTeam && sorted.length > 8 && (
                            <div style={{ color: '#1e2c44', marginTop: 4, fontSize: 10 }}>
                              — click a team to pin —
                            </div>
                          )}
                        </div>
                      )
                    }}
                  />
                  {/* Zone boundary reference lines from LEAGUE_ZONES */}
                  {leagueId && LEAGUE_ZONES[leagueId]
                    ? LEAGUE_ZONES[leagueId].map(z => (
                        <ReferenceLine key={`${z.type}-${z.to}`} y={z.to + 0.5}
                          stroke={ZONE_COLOR[z.type]} strokeDasharray="3 3"
                          strokeOpacity={0.3} />
                      ))
                    : [4, 6, numTeams - 3].map(pos => (
                        <ReferenceLine key={pos} y={pos + 0.5}
                          stroke="#1a2235" strokeDasharray="3 3" />
                      ))
                  }
                  {posHistory.teams.map(team => (
                    <Line key={team} type="linear" dataKey={team}
                      stroke={teamColorMap[team]}
                      strokeWidth={focusTeam === null ? 1.5 : focusTeam === team ? 2.5 : 0.5}
                      opacity={focusTeam === null ? 0.85 : focusTeam === team ? 1 : 0.12}
                      dot={false} connectNulls activeDot={{ r: 4 }}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* Team legend */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
              {posHistory.teams.map(team => (
                <button key={team}
                  onClick={() => setFocusTeam(f => f === team ? null : team)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 11,
                    padding: '4px 10px',
                    borderRadius: 4,
                    border: `1px solid ${teamColorMap[team]}`,
                    background: focusTeam === team ? teamColorMap[team] + '33' : 'transparent',
                    color: focusTeam === null || focusTeam === team ? '#e6e9f4' : '#4d5e7a',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: teamColorMap[team], flexShrink: 0 }} />
                  {team}
                </button>
              ))}
            </div>
          </div>
        ) : (
          !error && (
            <div style={{ textAlign: 'center', padding: '48px 0' }}>
              <p style={{ color: '#4d5e7a', fontSize: 13, marginBottom: 6 }}>Position history is only available for Understat leagues.</p>
              <p style={{ color: '#1e2c44', fontSize: 11 }}>Supported: Premier League · La Liga · Bundesliga · Serie A · Ligue 1</p>
            </div>
          )
        )
      )}

      {/* ── LEADERS ── */}
      {!loading && activeTab === 'leaders' && (
        leaders ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
            <LeaderBoard title="Top Scorers"   entries={leaders.goals ?? []}      onPlayerClick={isUnderstatLeague ? handlePlayerClick : undefined} />
            <LeaderBoard title="Top Assisters" entries={leaders.assists ?? []}    onPlayerClick={isUnderstatLeague ? handlePlayerClick : undefined} />
            {(leaders.xg ?? []).length > 0 && <LeaderBoard title="xG Leaders"    entries={leaders.xg ?? []}         onPlayerClick={isUnderstatLeague ? handlePlayerClick : undefined} />}
            {(leaders.key_passes ?? []).length > 0 && <LeaderBoard title="Key Passes" entries={leaders.key_passes ?? []} onPlayerClick={isUnderstatLeague ? handlePlayerClick : undefined} />}
            {(leaders.shots ?? []).length > 0 && <LeaderBoard title="Most Shots"  entries={leaders.shots ?? []}      onPlayerClick={isUnderstatLeague ? handlePlayerClick : undefined} />}
          </div>
        ) : (
          !error && <div style={{ textAlign: 'center', padding: '48px 0', color: '#4d5e7a', fontSize: 13 }}>Leaders not available for this league.</div>
        )
      )}
    </div>
  )
}
