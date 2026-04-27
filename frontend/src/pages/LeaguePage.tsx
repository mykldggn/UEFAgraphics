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

function LeaderBoard({ title, entries, unit = '' }: { title: string; entries: LeaderEntry[]; unit?: string }) {
  return (
    <div style={{
      background: '#0c1321',
      border: '1px solid #1a2235',
      borderRadius: 8,
      padding: 16,
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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {entries.slice(0, 10).map((e, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span style={{
              fontFamily: '"Bebas Neue", sans-serif',
              fontSize: 13,
              color: '#1e2c44',
              width: 18,
              textAlign: 'right',
              flexShrink: 0,
            }}>{i + 1}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <span style={{ color: '#e6e9f4', fontWeight: 500 }}>{e.player}</span>
              <span style={{ color: '#4d5e7a', fontSize: 11, marginLeft: 4 }}>({e.team})</span>
            </div>
            <span style={{
              fontFamily: '"Bebas Neue", sans-serif',
              fontSize: 17,
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
    posHistory.teams.forEach((t, i) => { teamColorMap[t] = PALETTE[i % PALETTE.length] })
  }
  const numTeams = posHistory?.teams.length ?? 20

  const leagueName = leagueId.replace('-', ' ')

  // Position zone border colors
  function posZoneColor(pos: number): string {
    if (pos <= 4) return '#c9a84c'   // CL — gold
    if (pos <= 6) return '#4a9eff'   // EL — blue
    return 'transparent'
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
                {table.map((row, i) => (
                  <tr
                    key={i}
                    style={{
                      borderBottom: '1px solid rgba(26,34,53,0.6)',
                      borderLeft: `2px solid ${posZoneColor(i + 1)}`,
                      background: i % 2 === 1 ? 'rgba(201,168,76,0.025)' : 'transparent',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(201,168,76,0.05)')}
                    onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 1 ? 'rgba(201,168,76,0.025)' : 'transparent')}
                  >
                    <td style={{ padding: '8px 12px', color: '#4d5e7a', fontFamily: '"Bebas Neue", sans-serif', fontSize: 16, letterSpacing: '0.04em' }}>{i + 1}</td>
                    <td style={{ padding: '8px 12px', color: '#e6e9f4', fontWeight: 500 }}>{row.team}</td>
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
                ))}
              </tbody>
            </table>
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
                    contentStyle={{ backgroundColor: '#0c1321', border: '1px solid #1a2235', borderRadius: 8, fontSize: 11 }}
                    itemStyle={{ color: '#4d5e7a' }}
                    formatter={(val, name) => [`${val}`, name]}
                    itemSorter={item => Number(item.value)}
                  />
                  {[4, 6, 17].map(pos => (
                    <ReferenceLine key={pos} y={pos} stroke="#1a2235" strokeDasharray="3 3" />
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
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14 }}>
            <LeaderBoard title="Top Scorers"    entries={leaders.goals ?? []} />
            <LeaderBoard title="Top Assisters"  entries={leaders.assists ?? []} />
            <LeaderBoard title="xG Leaders"     entries={leaders.xg ?? []} />
            <LeaderBoard title="Key Passes"     entries={leaders.key_passes ?? []} />
            <LeaderBoard title="Most Shots"     entries={leaders.shots ?? []} />
          </div>
        ) : (
          !error && <div style={{ textAlign: 'center', padding: '48px 0', color: '#4d5e7a', fontSize: 13 }}>Leaders not available for this league.</div>
        )
      )}
    </div>
  )
}
