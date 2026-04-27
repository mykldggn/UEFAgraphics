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
  { id: 'lineup',      label: 'Most Played XI' },
]

export default function TeamPage() {
  const { teamId }   = useParams<{ teamId: string }>()
  const [params]     = useSearchParams()
  const teamName     = params.get('name') ?? teamId ?? ''
  const leagueId     = params.get('league') ?? 'ENG-1'

  const [activeTab, setActiveTab] = useState('xg-timeline')
  const [season, setSeason]       = useState(Number(params.get('season') ?? 2025))

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
          {teamName}
        </h1>
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
