import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import TabBar from '../components/ui/TabBar'
import InfographicViewer from '../components/ui/InfographicViewer'
import Select from '../components/ui/Select'
import { infographicsApi } from '../api/infographics'
import { SEASONS } from '../utils/constants'

const SEASON_OPTS = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))

const POSITION_OPTS = [
  { value: 'FW', label: 'Forward' },
  { value: 'MF', label: 'Midfielder' },
  { value: 'DF', label: 'Defender' },
  { value: 'GK', label: 'Goalkeeper' },
]

const TABS = [
  { id: 'shotmap',    label: 'Shot Map' },
  { id: 'career-xg', label: 'Career xG' },
  { id: 'radar',     label: 'Radar' },
  { id: 'summary',   label: 'Summary Card' },
]

export default function PlayerPage() {
  const { playerId }       = useParams<{ playerId: string }>()
  const [params]           = useSearchParams()
  const leagueId           = params.get('league') ?? 'ENG-1'
  const source             = params.get('source') ?? 'understat'

  const [activeTab, setActiveTab]   = useState('shotmap')
  const [season, setSeason]         = useState(Number(params.get('season') ?? 2025))
  const [position, setPosition]     = useState('FW')
  const [cumulative, setCumulative] = useState(false)

  if (!playerId) return null

  const playerName = params.get('name')
    ? decodeURIComponent(params.get('name')!)
    : playerId

  function imgSrc(): string {
    switch (activeTab) {
      case 'shotmap':
        return infographicsApi.shotmap(playerId!, cumulative ? undefined : season, source)
      case 'career-xg':
        return infographicsApi.careerXg(playerId!, undefined, source)
      case 'radar':
        return infographicsApi.radar(playerId!, leagueId, season, position, undefined, source)
      case 'summary':
        return infographicsApi.summaryCard(playerId!, leagueId, cumulative ? undefined : season, position, source)
      default:
        return ''
    }
  }

  const showSeasonSelector   = ['shotmap', 'radar', 'summary'].includes(activeTab) && !cumulative
  const showPositionSelector = ['radar', 'summary'].includes(activeTab)
  const showCumulative       = ['shotmap', 'summary'].includes(activeTab)

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

      <TabBar tabs={TABS} active={activeTab} onChange={tab => { setActiveTab(tab); setCumulative(false) }} />

      {/* Infographic */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <InfographicViewer
          src={imgSrc()}
          alt={`${playerName} ${activeTab}`}
          className="max-w-2xl w-full"
        />
      </div>

      {/* Download link */}
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
    </div>
  )
}
