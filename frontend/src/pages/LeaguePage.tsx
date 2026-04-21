import { useState, useEffect } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
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

// 20-colour palette for team lines
const PALETTE = [
  '#3B82F6','#EF4444','#22C55E','#F59E0B','#8B5CF6',
  '#06B6D4','#EC4899','#84CC16','#F97316','#6366F1',
  '#14B8A6','#E11D48','#0EA5E9','#A3E635','#7C3AED',
  '#FB923C','#34D399','#FBBF24','#60A5FA','#F87171',
]

const FORM_BG: Record<string, string> = { W: '#22C55E', D: '#F59E0B', L: '#EF4444' }

function FormPills({ form }: { form: string }) {
  const chars = form.replace(/[^WDLwdl]/gi, '').toUpperCase().split('')
  if (!chars.length) return <span className="text-sub">—</span>
  return (
    <div className="flex gap-1 justify-end">
      {chars.map((r, i) => (
        <span key={i} style={{ backgroundColor: FORM_BG[r] ?? '#6B7280' }}
          className="inline-flex items-center justify-center w-4 h-4 rounded-sm text-[9px] font-bold text-white">
          {r}
        </span>
      ))}
    </div>
  )
}

function LeaderBoard({ title, entries, unit = '' }: { title: string; entries: LeaderEntry[]; unit?: string }) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 space-y-2">
      <h3 className="text-sm font-semibold text-sub uppercase tracking-wide">{title}</h3>
      {entries.slice(0, 10).map((e, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <span className="text-sub w-5 text-right">{i + 1}</span>
          <div className="flex-1 min-w-0">
            <span className="font-medium">{e.player}</span>
            <span className="text-sub text-xs ml-1">({e.team})</span>
          </div>
          <span className="font-semibold text-accent tabular-nums">{e.value}{unit}</span>
        </div>
      ))}
      {entries.length === 0 && <p className="text-sub text-xs">No data</p>}
    </div>
  )
}

export default function LeaguePage() {
  const { leagueId } = useParams<{ leagueId: string }>()
  const [params]     = useSearchParams()

  const [activeTab, setActiveTab] = useState('table')
  const [season, setSeason]       = useState(Number(params.get('season') ?? CURRENT_SEASON))
  const [table, setTable]         = useState<TableRow[]>([])
  const [posHistory, setPosHistory] = useState<{ teams: string[]; history: Record<string, number>[] } | null>(null)
  const [leaders, setLeaders]     = useState<Record<string, LeaderEntry[]> | null>(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState<string | null>(null)
  const [focusTeam, setFocusTeam] = useState<string | null>(null)

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

    Promise.all([tableP, posP, leadP])
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [leagueId, season])

  if (!leagueId) return null

  // Table columns
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

  // Position race chart
  const teamColorMap: Record<string, string> = {}
  if (posHistory) {
    posHistory.teams.forEach((t, i) => { teamColorMap[t] = PALETTE[i % PALETTE.length] })
  }
  const numTeams = posHistory?.teams.length ?? 20

  const leagueName = leagueId.replace('-', ' ')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-xl font-bold">{leagueName}</h1>
        <Select value={season} options={SEASON_OPTS}
          onChange={v => setSeason(Number(v))} className="w-36" />
      </div>

      <TabBar tabs={PAGE_TABS} active={activeTab} onChange={setActiveTab} />

      {loading && (
        <div className="flex justify-center py-16 text-sub text-sm">Loading…</div>
      )}
      {error && (
        <div className="bg-red-900/20 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      {/* ── TABLE ── */}
      {!loading && activeTab === 'table' && (
        table.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-border text-sub text-xs uppercase tracking-wide">
                  <th className="py-2 px-3 text-left w-6">#</th>
                  <th className="py-2 px-3 text-left">Team</th>
                  {COLS.map(c => <th key={c.key} className="py-2 px-3 text-right">{c.label}</th>)}
                  <th className="py-2 px-3 text-right">Form</th>
                </tr>
              </thead>
              <tbody>
                {table.map((row, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-card transition-colors">
                    <td className="py-2 px-3 text-sub">{i + 1}</td>
                    <td className="py-2 px-3 font-medium">{row.team}</td>
                    {COLS.map(c => (
                      <td key={c.key} className={`py-2 px-3 text-right ${c.key === 'points' ? 'font-semibold text-accent' : 'text-sub'}`}>
                        {row[c.key] != null ? String(row[c.key]) : '—'}
                      </td>
                    ))}
                    <td className="py-2 px-3"><FormPills form={String(row.form ?? '')} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          !error && <div className="text-center py-16 text-sub text-sm">No table data available.</div>
        )
      )}

      {/* ── POSITION RACE ── */}
      {!loading && activeTab === 'race' && (
        posHistory && posHistory.history.length > 0 ? (
          <div className="space-y-4">
            <p className="text-xs text-sub">
              League position after each match played.
              {posHistory.history.length < 34
                ? ' Data reflects the current point in the season.'
                : ''}
              {' '}Click a team to highlight.
            </p>
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
                  tick={{ fill: '#9CA3AF', fontSize: 10 }}
                  label={{ value: 'Match', position: 'insideBottom', offset: -4, fill: '#9CA3AF', fontSize: 10 }} />
                <YAxis reversed domain={[1, numTeams]} tickCount={numTeams}
                  tick={{ fill: '#9CA3AF', fontSize: 10 }}
                  label={{ value: 'Position', angle: -90, position: 'insideLeft', fill: '#9CA3AF', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#12151C', border: '1px solid #1F2937', borderRadius: 8, fontSize: 11 }}
                  itemStyle={{ color: '#9CA3AF' }}
                  formatter={(val, name) => [`${val}`, name]}
                  itemSorter={item => Number(item.value)}
                />
                {[4, 6, 17].map(pos => (
                  <ReferenceLine key={pos} y={pos} stroke="#1F2937" strokeDasharray="3 3" />
                ))}
                {posHistory.teams.map(team => (
                  <Line key={team} type="linear" dataKey={team}
                    stroke={teamColorMap[team]}
                    strokeWidth={focusTeam === null ? 1.5 : focusTeam === team ? 2.5 : 0.5}
                    opacity={focusTeam === null ? 0.85 : focusTeam === team ? 1 : 0.15}
                    dot={false} connectNulls activeDot={{ r: 4 }}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            {/* Team legend */}
            <div className="flex flex-wrap gap-2 justify-center">
              {posHistory.teams.map(team => (
                <button key={team}
                  onClick={() => setFocusTeam(f => f === team ? null : team)}
                  className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border transition-colors"
                  style={{
                    borderColor: teamColorMap[team],
                    backgroundColor: focusTeam === team ? teamColorMap[team] + '33' : 'transparent',
                    color: focusTeam === null || focusTeam === team ? '#fff' : '#6B7280',
                  }}
                >
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: teamColorMap[team] }} />
                  {team}
                </button>
              ))}
            </div>
          </div>
        ) : (
          !error && (
            <div className="text-center py-16 space-y-2">
              <p className="text-sub text-sm">Position history is only available for Understat leagues.</p>
              <p className="text-sub/60 text-xs">Supported: Premier League · La Liga · Bundesliga · Serie A · Ligue 1</p>
            </div>
          )
        )
      )}

      {/* ── LEADERS ── */}
      {!loading && activeTab === 'leaders' && (
        leaders ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <LeaderBoard title="Top Scorers"    entries={leaders.goals ?? []} />
            <LeaderBoard title="Top Assisters"  entries={leaders.assists ?? []} />
            <LeaderBoard title="xG Leaders"     entries={leaders.xg ?? []} />
            <LeaderBoard title="Key Passes"     entries={leaders.key_passes ?? []} />
            <LeaderBoard title="Most Shots"     entries={leaders.shots ?? []} />
          </div>
        ) : (
          !error && <div className="text-center py-16 text-sub text-sm">Leaders not available for this league.</div>
        )
      )}
    </div>
  )
}
