import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom'
import TabBar from '../components/ui/TabBar'
import InfographicViewer from '../components/ui/InfographicViewer'
import Select from '../components/ui/Select'
import { infographicsApi, type LineupPlayer } from '../api/infographics'
import { leaguesApi, type TableRow } from '../api/leagues'
import {
  SEASONS,
  LEAGUE_LABELS,
  FULL_INFOGRAPHIC_LEAGUES,
  FULL_INFOGRAPHIC_SUPPORT_LABEL,
} from '../utils/constants'

const SEASON_OPTS = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))

const TABS = [
  { id: 'xg-timeline',     label: 'xG Timeline' },
  { id: 'season-card',     label: 'Season Card' },
  { id: 'lineup',          label: 'Most Played XI' },
  { id: 'squad-minutes',   label: 'Squad Minutes' },
  { id: 'match-scatter',   label: 'Match Profile' },
  { id: 'situation',       label: 'Situations' },
  { id: 'xpoints',         label: 'xPoints' },
  { id: 'scorer-timeline', label: 'Scorer Timeline' },
]

function matchTeam(a: string, b: string): boolean {
  const norm = (s: string) => s.toLowerCase().replace(/\s+(f\.?c\.?|a\.?f\.?c\.?)$/i, '').trim()
  const an = norm(a), bn = norm(b)
  return an.includes(bn) || bn.includes(an)
}

function StatBadge({ label, value, gold }: { label: string; value: string; gold?: boolean }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '4px 10px',
      borderRadius: 6,
      background: gold ? 'rgba(201,168,76,0.12)' : 'rgba(255,255,255,0.04)',
      border: `1px solid ${gold ? 'rgba(201,168,76,0.35)' : '#1a2235'}`,
      minWidth: 40,
    }}>
      <span style={{ fontSize: 15, fontWeight: 700, color: gold ? '#c9a84c' : '#e6e9f4', lineHeight: 1.1 }}>
        {value}
      </span>
      <span style={{ fontSize: 9, color: '#4d5e7a', letterSpacing: '0.06em', marginTop: 2 }}>
        {label}
      </span>
    </div>
  )
}

export default function TeamPage() {
  const { teamId }   = useParams<{ teamId: string }>()
  const [params]     = useSearchParams()
  const teamName     = params.get('name') ?? teamId ?? ''
  const leagueId     = params.get('league') ?? 'ENG-1'
  const leagueLabel  = LEAGUE_LABELS[leagueId] ?? leagueId
  const isFullInfographicLeague = FULL_INFOGRAPHIC_LEAGUES.has(leagueId)

  const navigate = useNavigate()

  const urlTab = params.get('tab') ?? 'xg-timeline'
  const [activeTab, setActiveTab]     = useState(urlTab)
  const [season, setSeason]           = useState(Number(params.get('season') ?? 2025))
  const [crest, setCrest]             = useState<string | null>(null)
  const [meta, setMeta]               = useState<{ venue: string | null; founded: number | null; address: string | null } | null>(null)
  const [teamRow, setTeamRow]         = useState<TableRow | null>(null)
  const [lineupPlayers, setLineupPlayers] = useState<LineupPlayer[]>([])

  // Sync tab from URL when navigating back/forward
  useEffect(() => {
    const t = params.get('tab') ?? 'xg-timeline'
    setActiveTab(t)
  }, [params])

  useEffect(() => {
    if (!teamName || !leagueId || !isFullInfographicLeague) return
    leaguesApi.teamMeta(leagueId, teamName, season)
      .then(r => {
        setCrest(r.crest)
        setMeta({ venue: r.venue, founded: r.founded, address: r.address })
      })
      .catch(() => setMeta(null))
  }, [teamName, leagueId, season, isFullInfographicLeague])

  // Fetch standings to populate quick stats badges
  useEffect(() => {
    if (!leagueId || !teamName || !isFullInfographicLeague) return
    leaguesApi.table(leagueId, season)
      .then(r => {
        const row = r.table.find(t => matchTeam(teamName, t.team)) ?? null
        setTeamRow(row)
      })
      .catch(() => setTeamRow(null))
  }, [leagueId, season, teamName, isFullInfographicLeague])

  useEffect(() => {
    if (activeTab !== 'lineup' || !teamId || !teamName || !leagueId || !isFullInfographicLeague) return
    infographicsApi.teamLineupPlayers(teamId, teamName, leagueId, season)
      .then(r => setLineupPlayers(r.players))
      .catch(() => setLineupPlayers([]))
  }, [activeTab, teamId, teamName, leagueId, season, isFullInfographicLeague])

  if (!teamId) return null

  function handleTabChange(id: string) {
    setActiveTab(id)
    const p = new URLSearchParams(params)
    p.set('tab', id)
    navigate(`?${p.toString()}`, { replace: true })
  }

  function imgSrc(): string {
    switch (activeTab) {
      case 'xg-timeline':     return infographicsApi.teamXgTimeline(teamId!, teamName, leagueId, season)
      case 'season-card':     return infographicsApi.teamSeasonCard(teamId!, teamName, leagueId, season)
      case 'lineup':          return infographicsApi.teamLineup(teamId!, teamName, leagueId, season)
      case 'squad-minutes':   return infographicsApi.teamSquadMinutes(teamId!, teamName, leagueId, season)
      case 'match-scatter':   return infographicsApi.teamMatchScatter(teamId!, teamName, leagueId, season)
      case 'situation':       return infographicsApi.teamSituation(teamId!, teamName, leagueId, season)
      case 'xpoints':         return infographicsApi.teamXpoints(teamId!, teamName, leagueId, season)
      case 'scorer-timeline': return infographicsApi.teamScorerTimeline(teamId!, teamName, leagueId, season)
      default:                return ''
    }
  }

  const city = meta?.address
    ? meta.address.split(',').slice(-2, -1)[0]?.trim()
    : null

  const gd = teamRow?.goal_diff
  const gdStr = gd !== undefined && gd !== null
    ? (gd >= 0 ? `+${gd}` : `${gd}`)
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Breadcrumb */}
      <div>
        <Link
          to={`/league/${leagueId}?season=${season}`}
          style={{ fontSize: 12, color: '#4d5e7a', textDecoration: 'none', transition: 'color 0.15s' }}
          onMouseEnter={e => (e.currentTarget.style.color = '#c9a84c')}
          onMouseLeave={e => (e.currentTarget.style.color = '#4d5e7a')}
        >
          ← {leagueLabel} {season}/{String(season + 1).slice(-2)}
        </Link>
      </div>

      {/* Header strip */}
      <div style={{
        background: 'linear-gradient(90deg, rgba(201,168,76,0.10), transparent)',
        borderLeft: '4px solid #c9a84c',
        borderRadius: '0 6px 6px 0',
        padding: '14px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
      }}>
        {/* Left: crest + name + metadata + badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0, flex: 1 }}>
          {crest && (
            <img
              src={crest}
              alt={teamName}
              style={{ width: 48, height: 48, objectFit: 'contain', flexShrink: 0 }}
              onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
            />
          )}
          <div style={{ minWidth: 0 }}>
            <h1 style={{
              fontFamily: '"Bebas Neue", sans-serif',
              fontSize: 28,
              letterSpacing: '0.04em',
              color: '#e6e9f4',
              margin: 0,
              lineHeight: 1,
            }}>
              {teamName}
            </h1>

            {/* Venue/city metadata */}
            {(city || meta?.venue || meta?.founded) && (
              <div style={{ display: 'flex', gap: 12, marginTop: 4, flexWrap: 'wrap' }}>
                {city    && <span style={{ fontSize: 11, color: '#4d5e7a' }}>📍 {city}</span>}
                {meta?.venue   && <span style={{ fontSize: 11, color: '#4d5e7a' }}>🏟 {meta.venue}</span>}
                {meta?.founded && <span style={{ fontSize: 11, color: '#4d5e7a' }}>Est. {meta.founded}</span>}
              </div>
            )}

            {/* Quick stats badges */}
            {teamRow && (
              <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                {teamRow.rank    != null && <StatBadge label="POS"  value={`${teamRow.rank}`}                   gold />}
                {teamRow.points  != null && <StatBadge label="PTS"  value={`${teamRow.points}`}                 />}
                {teamRow.wins    != null && <StatBadge label="W"    value={`${teamRow.wins}`}                   />}
                {teamRow.draws   != null && <StatBadge label="D"    value={`${teamRow.draws}`}                  />}
                {teamRow.losses  != null && <StatBadge label="L"    value={`${teamRow.losses}`}                 />}
                {gdStr           != null && <StatBadge label="GD"   value={gdStr}                               />}
              </div>
            )}
          </div>
        </div>

        {/* Right: season selector */}
        <Select value={season} options={SEASON_OPTS} onChange={v => setSeason(Number(v))} />
      </div>

      {!isFullInfographicLeague ? (
        <div style={{
          background: '#0c1321',
          border: '1px solid #1a2235',
          borderRadius: 8,
          padding: '48px 32px',
          textAlign: 'center',
        }}>
          <div style={{ color: '#e6e9f4', fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
            Team infographics unavailable
          </div>
          <div style={{ color: '#4d5e7a', fontSize: 13, maxWidth: 520, margin: '0 auto', lineHeight: 1.6 }}>
            This league is not shown in the infographic selector because full current-season
            Player, Team, and League coverage cannot be replicated at Understat quality yet.
          </div>
          <div style={{ color: '#1e2c44', fontSize: 11, marginTop: 10 }}>
            Supported: {FULL_INFOGRAPHIC_SUPPORT_LABEL}
          </div>
        </div>
      ) : (
        <>
      <TabBar tabs={TABS} active={activeTab} onChange={handleTabChange} />

      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <InfographicViewer
          src={imgSrc()}
          alt={`${teamName} ${activeTab}`}
          className="max-w-3xl w-full"
        />
      </div>

      {/* Clickable XI roster chips below lineup image */}
      {activeTab === 'lineup' && lineupPlayers.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', maxWidth: 640, margin: '0 auto' }}>
          {lineupPlayers.map((p, i) => (
            <button
              key={i}
              onClick={() => {
                if (p.id) {
                  navigate(`/player/${p.id}?season=${season}&league=${leagueId}&name=${encodeURIComponent(p.player)}`)
                }
              }}
              style={{
                padding: '5px 12px',
                borderRadius: 20,
                fontSize: 12,
                fontWeight: 500,
                border: '1px solid #1a2235',
                background: 'transparent',
                color: p.id ? '#e6e9f4' : '#4d5e7a',
                cursor: p.id ? 'pointer' : 'default',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => {
                if (p.id) {
                  (e.currentTarget as HTMLElement).style.borderColor = '#c9a84c'
                  ;(e.currentTarget as HTMLElement).style.color = '#c9a84c'
                }
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.borderColor = '#1a2235'
                ;(e.currentTarget as HTMLElement).style.color = p.id ? '#e6e9f4' : '#4d5e7a'
              }}
            >
              {p.player}
            </button>
          ))}
        </div>
      )}

      <div style={{ textAlign: 'center' }}>
        <a
          href={imgSrc()}
          download={`${teamName}-${activeTab}-${season}.png`}
          style={{ fontSize: 12, color: '#4d5e7a', textDecoration: 'none', transition: 'color 0.15s' }}
          onMouseEnter={e => (e.currentTarget.style.color = '#c9a84c')}
          onMouseLeave={e => (e.currentTarget.style.color = '#4d5e7a')}
        >
          ↓ Download PNG
        </a>
      </div>
        </>
      )}
    </div>
  )
}
