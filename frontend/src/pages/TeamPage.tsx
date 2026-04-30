import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import TabBar from '../components/ui/TabBar'
import InfographicViewer from '../components/ui/InfographicViewer'
import Select from '../components/ui/Select'
import { infographicsApi, type LineupPlayer } from '../api/infographics'
import { leaguesApi } from '../api/leagues'
import { SEASONS } from '../utils/constants'

const SEASON_OPTS = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))

const TABS = [
  { id: 'xg-timeline', label: 'xG Timeline' },
  { id: 'season-card', label: 'Season Card' },
  { id: 'lineup',      label: 'Most Played XI' },
]

interface TeamMeta {
  crest: string | null
  venue: string | null
  founded: number | null
  address: string | null
}

export default function TeamPage() {
  const { teamId }   = useParams<{ teamId: string }>()
  const [params]     = useSearchParams()
  const teamName     = params.get('name') ?? teamId ?? ''
  const leagueId     = params.get('league') ?? 'ENG-1'

  const navigate = useNavigate()

  const [activeTab, setActiveTab]     = useState('xg-timeline')
  const [season, setSeason]           = useState(Number(params.get('season') ?? 2024))
  const [meta, setMeta]               = useState<TeamMeta | null>(null)
  const [lineupPlayers, setLineupPlayers] = useState<LineupPlayer[]>([])

  useEffect(() => {
    if (!teamName || !leagueId) return
    leaguesApi.teamMeta(leagueId, teamName, season)
      .then(setMeta)
      .catch(() => setMeta(null))
  }, [teamName, leagueId, season])

  useEffect(() => {
    if (activeTab !== 'lineup' || !teamId || !teamName || !leagueId) return
    infographicsApi.teamLineupPlayers(teamId, teamName, leagueId, season)
      .then(r => setLineupPlayers(r.players))
      .catch(() => setLineupPlayers([]))
  }, [activeTab, teamId, teamName, leagueId, season])

  if (!teamId) return null

  function imgSrc(): string {
    switch (activeTab) {
      case 'xg-timeline':
        return infographicsApi.teamXgTimeline(teamId!, teamName, leagueId, season)
      case 'season-card':
        return infographicsApi.teamSeasonCard(teamId!, teamName, leagueId, season)
      case 'lineup':
        return infographicsApi.teamLineup(teamId!, teamName, leagueId, season)
      default:
        return ''
    }
  }

  // Parse city from address (format: "Street, City, Country")
  const city = meta?.address
    ? meta.address.split(',').slice(-2, -1)[0]?.trim()
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header strip */}
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
        {/* Left: name + metadata */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
          {meta?.crest && (
            <img
              src={meta.crest}
              alt={teamName}
              style={{ width: 48, height: 48, objectFit: 'contain', flexShrink: 0 }}
              onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
            />
          )}
          <div>
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
            {(city || meta?.venue || meta?.founded) && (
              <div style={{ display: 'flex', gap: 12, marginTop: 4, flexWrap: 'wrap' }}>
                {city && (
                  <span style={{ fontSize: 11, color: '#4d5e7a' }}>📍 {city}</span>
                )}
                {meta?.venue && (
                  <span style={{ fontSize: 11, color: '#4d5e7a' }}>🏟 {meta.venue}</span>
                )}
                {meta?.founded && (
                  <span style={{ fontSize: 11, color: '#4d5e7a' }}>Est. {meta.founded}</span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: season selector */}
        <Select value={season} options={SEASON_OPTS} onChange={v => setSeason(Number(v))} />
      </div>

      <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />

      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <InfographicViewer
          src={imgSrc()}
          alt={`${teamName} ${activeTab}`}
          className="max-w-3xl w-full"
        />
      </div>

      {/* T2: Clickable XI roster chips below lineup image */}
      {activeTab === 'lineup' && lineupPlayers.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', maxWidth: 640, margin: '0 auto' }}>
          {lineupPlayers.map((p, i) => (
            <button
              key={i}
              onClick={() => {
                if (p.id) {
                  const src = p.source ?? 'understat'
                  navigate(`/player/${p.id}?season=${season}&league=${leagueId}&name=${encodeURIComponent(p.player)}&source=${src}`)
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
              onMouseEnter={e => { if (p.id) (e.currentTarget as HTMLElement).style.borderColor = '#c9a84c'; if (p.id) (e.currentTarget as HTMLElement).style.color = '#c9a84c' }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = '#1a2235'; (e.currentTarget as HTMLElement).style.color = p.id ? '#e6e9f4' : '#4d5e7a' }}
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
    </div>
  )
}
