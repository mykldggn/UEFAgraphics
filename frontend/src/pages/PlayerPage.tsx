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
  { id: 'shotmap',      label: 'Shot Map' },
  { id: 'career-xg',   label: 'Career xG' },
  { id: 'radar',       label: 'Radar' },
  { id: 'summary',     label: 'Summary Card' },
  { id: 'passmap',     label: 'Pass Map' },
]

export default function PlayerPage() {
  const { playerId }       = useParams<{ playerId: string }>()
  const [params]           = useSearchParams()
  const leagueId           = params.get('league') ?? 'ENG-1'
  const source             = params.get('source') ?? 'understat'

  const [activeTab, setActiveTab] = useState('shotmap')
  const [season, setSeason]       = useState(Number(params.get('season') ?? 2024))
  const [position, setPosition]   = useState('FW')

  if (!playerId) return null

  // Decode name if source=fbref (stored as URL-encoded name)
  const playerName = source === 'fbref' ? decodeURIComponent(playerId) : playerId

  function imgSrc(): string {
    switch (activeTab) {
      case 'shotmap':
        return infographicsApi.shotmap(playerName, season)
      case 'career-xg':
        return infographicsApi.careerXg(playerName)
      case 'radar':
        return infographicsApi.radar(playerName, leagueId, season, position)
      case 'summary':
        return infographicsApi.summaryCard(playerName, leagueId, season, position)
      case 'passmap':
        return infographicsApi.passmap(playerName, leagueId, season)
      default:
        return ''
    }
  }

  const showSeasonSelector = ['shotmap', 'radar', 'summary', 'passmap'].includes(activeTab)
  const showPositionSelector = ['radar', 'summary'].includes(activeTab)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-xl font-bold">{decodeURIComponent(playerName)}</h1>
        <div className="flex gap-3 flex-wrap">
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

      <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />

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
