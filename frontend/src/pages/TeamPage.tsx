import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import TabBar from '../components/ui/TabBar'
import InfographicViewer from '../components/ui/InfographicViewer'
import Select from '../components/ui/Select'
import { infographicsApi } from '../api/infographics'
import { SEASONS } from '../utils/constants'

const SEASON_OPTS = SEASONS.map(s => ({ value: s, label: `${s}/${String(s + 1).slice(-2)}` }))

const TABS = [
  { id: 'xg-timeline', label: 'xG Timeline' },
  { id: 'season-card', label: 'Season Card' },
]

export default function TeamPage() {
  const { teamId }   = useParams<{ teamId: string }>()
  const [params]     = useSearchParams()
  const teamName     = params.get('name') ?? teamId ?? ''
  const leagueId     = params.get('league') ?? 'ENG-1'

  const [activeTab, setActiveTab] = useState('xg-timeline')
  const [season, setSeason]       = useState(Number(params.get('season') ?? 2024))

  if (!teamId) return null

  function imgSrc(): string {
    switch (activeTab) {
      case 'xg-timeline':
        return infographicsApi.teamXgTimeline(teamId!, teamName, season)
      case 'season-card':
        return infographicsApi.teamSeasonCard(teamId!, teamName, leagueId, season)
      default:
        return ''
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-xl font-bold">{teamName}</h1>
        <Select
          value={season}
          options={SEASON_OPTS}
          onChange={v => setSeason(Number(v))}
          className="w-36"
        />
      </div>

      <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />

      <div className="flex justify-center">
        <InfographicViewer
          src={imgSrc()}
          alt={`${teamName} ${activeTab}`}
          className="max-w-3xl w-full"
        />
      </div>

      <div className="text-center">
        <a
          href={imgSrc()}
          download={`${teamName}-${activeTab}-${season}.png`}
          className="inline-flex items-center gap-2 text-xs text-sub hover:text-accent transition-colors"
        >
          ↓ Download PNG
        </a>
      </div>
    </div>
  )
}
