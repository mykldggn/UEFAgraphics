import { useState, useEffect } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import Select from '../components/ui/Select'
import { leaguesApi, type TableRow } from '../api/leagues'
import { SEASONS } from '../utils/constants'

const SEASON_OPTS = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))

export default function LeaguePage() {
  const { leagueId }  = useParams<{ leagueId: string }>()
  const [params]      = useSearchParams()

  const [season, setSeason]     = useState(Number(params.get('season') ?? 2024))
  const [table, setTable]       = useState<TableRow[]>([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  useEffect(() => {
    if (!leagueId) return
    setLoading(true)
    setError(null)
    leaguesApi.table(leagueId, season)
      .then(r => setTable(r.table))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [leagueId, season])

  if (!leagueId) return null

  // Explicit columns: key → header label (rank and team_id excluded)
  const COLS: { key: string; label: string }[] = [
    { key: 'played',        label: 'MP' },
    { key: 'wins',          label: 'W' },
    { key: 'draws',         label: 'D' },
    { key: 'losses',        label: 'L' },
    { key: 'goals_for',     label: 'GF' },
    { key: 'goals_against', label: 'GA' },
    { key: 'goal_diff',     label: 'GD' },
    { key: 'points',        label: 'Pts' },
  ].filter(c => table.length > 0 && table[0][c.key] != null)

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-xl font-bold">{leagueId.replace('-', ' ')}</h1>
        <Select
          value={season}
          options={SEASON_OPTS}
          onChange={v => setSeason(Number(v))}
          className="w-36"
        />
      </div>

      {loading && (
        <div className="flex justify-center py-16 text-sub text-sm">
          Loading league table…
        </div>
      )}

      {error && (
        <div className="bg-red/10 border border-red/30 text-red rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && table.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border text-sub text-xs uppercase tracking-wide">
                <th className="py-2 px-3 text-left w-6">#</th>
                <th className="py-2 px-3 text-left">Team</th>
                {COLS.map(c => (
                  <th key={c.key} className="py-2 px-3 text-right">{c.label}</th>
                ))}
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && table.length === 0 && (
        <div className="text-center py-16 text-sub text-sm">
          No table data available for this selection.
        </div>
      )}
    </div>
  )
}
