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

  // Prefer name from URL param; fall back to decoded playerId for fbref
  const playerName = params.get('name')
    ? decodeURIComponent(params.get('name')!)
    : source === 'fbref' ? decodeURIComponent(playerId) : playerId

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
      default:
        return ''
    }
  }

  const showSeasonSelector   = ['shotmap', 'radar', 'summary'].includes(activeTab) && !cumulative
  const showPositionSelector = ['radar', 'summary'].includes(activeTab)
  const showCumulative       = ['shotmap', 'summary'].includes(activeTab)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-xl font-bold">{playerName}</h1>
        <div className="flex gap-3 flex-wrap items-center">
          {showCumulative && (
            <button
              onClick={() => setCumulative(c => !c)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
                cumulative
                  ? 'bg-accent border-accent text-white'
                  : 'border-border text-sub hover:text-white'
              }`}
            >
              All Seasons
            </button>
          )}
          {showSeasonSelector && (
            <Select
              value={season}
              options={SEASON_OPTS}
              onChange={v => setSeason(Number(v))}
              className="w-36"
            />
          )}
          {showPositionSelector && (
            <Select
              value={position}
              options={POSITION_OPTS}
              onChange={setPosition}
              className="w-36"
            />
          )}
        </div>
      </div>

      <TabBar tabs={TABS} active={activeTab} onChange={tab => { setActiveTab(tab); setCumulative(false) }} />

      {/* Infographic */}
      <div className="flex justify-center">
        <InfographicViewer
          src={imgSrc()}
          alt={`${playerName} ${activeTab}`}
          className="max-w-2xl w-full"
        />
      </div>

      {/* Download link */}
      <div className="text-center">
        <a
          href={imgSrc()}
          download={`${playerName}-${activeTab}-${season}.png`}
          className="inline-flex items-center gap-2 text-xs text-sub hover:text-accent transition-colors"
        >
          ↓ Download PNG
        </a>
      </div>
    </div>
  )
}
