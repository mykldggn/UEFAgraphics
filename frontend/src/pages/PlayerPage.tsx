import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom'
import TabBar from '../components/ui/TabBar'
import InfographicViewer from '../components/ui/InfographicViewer'
import Select from '../components/ui/Select'
import { infographicsApi } from '../api/infographics'
import {
  SEASONS,
  LEAGUE_LABELS,
  FULL_INFOGRAPHIC_LEAGUES,
  FULL_INFOGRAPHIC_SUPPORT_LABEL,
} from '../utils/constants'

const SEASON_OPTS = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))

const POSITION_OPTS = [
  { value: 'FW', label: 'Forward' },
  { value: 'MF', label: 'Midfielder' },
  { value: 'DF', label: 'Defender' },
  { value: 'GK', label: 'Goalkeeper' },
]

const TABS = [
  { id: 'shotmap',        label: 'Shot Map' },
  { id: 'career-xg',     label: 'Career xG' },
  { id: 'radar',         label: 'Radar' },
  { id: 'summary',       label: 'Summary Card' },
  { id: 'xg-arc',        label: 'xG Arc' },
  { id: 'shot-quality',  label: 'Shot Quality' },
  { id: 'shot-situation',label: 'Situations' },
  { id: 'season-compare',label: 'Season Compare' },
  { id: 'rolling-form',  label: 'Rolling Form' },
]


function NotAvailableCard({ tab }: { tab: string }) {
  const label = TABS.find(t => t.id === tab)?.label ?? 'Infographic'
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 16,
      background: '#0c1321', borderRadius: 8, padding: '64px 32px',
      border: '1px solid #1a2235', minHeight: 240,
    }}>
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.4 }}>
        <circle cx="12" cy="12" r="10" stroke="#4d5e7a" strokeWidth="1.5"/>
        <path d="M12 8v4M12 16h.01" stroke="#4d5e7a" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
      <div style={{ textAlign: 'center' }}>
        <div style={{ color: '#e6e9f4', fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
          {label} not available
        </div>
        <div style={{ color: '#4d5e7a', fontSize: 13, maxWidth: 340, lineHeight: 1.6 }}>
          This player infographic requires full current-season Understat coverage across
          player, team, and league views.
        </div>
        <div style={{ color: '#1e2c44', fontSize: 11, maxWidth: 360, lineHeight: 1.5, marginTop: 8 }}>
          Supported: {FULL_INFOGRAPHIC_SUPPORT_LABEL}
        </div>
      </div>
    </div>
  )
}

export default function PlayerPage() {
  const { playerId }       = useParams<{ playerId: string }>()
  const [params]           = useSearchParams()
  const navigate           = useNavigate()
  const leagueId  = params.get('league') ?? 'ENG-1'
  const leagueLabel = LEAGUE_LABELS[leagueId] ?? leagueId
  const isFullInfographicLeague = FULL_INFOGRAPHIC_LEAGUES.has(leagueId)

  const urlTab = params.get('tab') ?? 'shotmap'
  const [activeTab, setActiveTab]   = useState(urlTab)
  const [season, setSeason]         = useState(Number(params.get('season') ?? 2025))
  const [position, setPosition]     = useState('FW')
  const [cumulative, setCumulative] = useState(false)

  // Sync tab from URL when navigating back/forward
  useEffect(() => {
    const t = params.get('tab') ?? 'shotmap'
    setActiveTab(t)
  }, [params])

  if (!playerId) return null

  const playerName = params.get('name')
    ? decodeURIComponent(params.get('name')!)
    : playerId

  const showNotAvailable = !isFullInfographicLeague

  function imgSrc(): string {
    switch (activeTab) {
      case 'shotmap':
        return infographicsApi.shotmap(playerId!, cumulative ? undefined : season)
      case 'career-xg':
        return infographicsApi.careerXg(playerId!)
      case 'radar':
        return infographicsApi.radar(playerId!, leagueId, season, position)
      case 'summary':
        return infographicsApi.summaryCard(playerId!, leagueId, cumulative ? undefined : season, position)
      case 'xg-arc':
        return infographicsApi.playerXgArc(playerId!, season)
      case 'shot-quality':
        return infographicsApi.playerShotQuality(playerId!, season)
      case 'shot-situation':
        return infographicsApi.playerShotSituation(playerId!, season)
      case 'season-compare':
        return infographicsApi.playerSeasonCompare(playerId!)
      case 'rolling-form':
        return infographicsApi.playerRollingForm(playerId!, season)
      default:
        return ''
    }
  }

  const showSeasonSelector   = ['shotmap', 'radar', 'summary', 'xg-arc', 'shot-quality', 'shot-situation', 'rolling-form'].includes(activeTab) && !cumulative
  const showPositionSelector = ['radar', 'summary'].includes(activeTab)
  const showCumulative       = ['shotmap', 'summary'].includes(activeTab) && isFullInfographicLeague

  function handleTabChange(id: string) {
    setActiveTab(id)
    setCumulative(false)
    const p = new URLSearchParams(params)
    p.set('tab', id)
    navigate(`?${p.toString()}`, { replace: true })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Breadcrumb */}
      <div>
        <Link
          to={`/?tab=Player&league=${leagueId}&season=${season}`}
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
        }}>
          {playerName}
        </h1>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {showCumulative && (
            <button
              onClick={() => setCumulative(c => !c)}
              style={{
                padding: '6px 14px',
                borderRadius: 5,
                fontSize: 12,
                fontWeight: 500,
                border: `1px solid ${cumulative ? '#c9a84c' : '#1a2235'}`,
                background: cumulative ? 'rgba(201,168,76,0.15)' : 'transparent',
                color: cumulative ? '#c9a84c' : '#4d5e7a',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              All Seasons
            </button>
          )}
          {showSeasonSelector && (
            <Select value={season} options={SEASON_OPTS} onChange={v => setSeason(Number(v))} />
          )}
          {showPositionSelector && (
            <Select value={position} options={POSITION_OPTS} onChange={setPosition} />
          )}
        </div>
      </div>

      <TabBar tabs={TABS} active={activeTab} onChange={handleTabChange} />

      {/* Infographic */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        {showNotAvailable ? (
          <div style={{ width: '100%', maxWidth: 672 }}>
            <NotAvailableCard tab={activeTab} />
          </div>
        ) : (
          <InfographicViewer
            src={imgSrc()}
            alt={`${playerName} ${activeTab}`}
            className="max-w-2xl w-full"
          />
        )}
      </div>

      {/* Download link — only when infographic is shown */}
      {!showNotAvailable && (
        <div style={{ textAlign: 'center' }}>
          <a
            href={imgSrc()}
            download={`${playerName}-${activeTab}-${season}.png`}
            style={{ fontSize: 12, color: '#4d5e7a', textDecoration: 'none', transition: 'color 0.15s' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#c9a84c')}
            onMouseLeave={e => (e.currentTarget.style.color = '#4d5e7a')}
          >
            ↓ Download PNG
          </a>
        </div>
      )}
    </div>
  )
}
