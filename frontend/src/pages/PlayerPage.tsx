import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom'
import TabBar from '../components/ui/TabBar'
import InfographicViewer from '../components/ui/InfographicViewer'
import Select from '../components/ui/Select'
import CoverageNotice from '../components/ui/CoverageNotice'
import { infographicsApi } from '../api/infographics'
import { leaguesApi } from '../api/leagues'
import {
  SEASONS,
  LEAGUE_LABELS,
  FULL_INFOGRAPHIC_LEAGUES,
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

const UNDERSTAT_ID_RE = /^\d+$/

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function normaliseName(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
}

function playerResultName(result: { name?: string; player?: string }): string {
  return result.name ?? result.player ?? ''
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
  const [resolvedPlayerId, setResolvedPlayerId] = useState<string | null>(null)
  const [resolvingPlayer, setResolvingPlayer]   = useState(false)

  const routePlayerId = playerId ?? ''
  const paramsKey = params.toString()
  const needsPlayerResolution = Boolean(
    routePlayerId && isFullInfographicLeague && !UNDERSTAT_ID_RE.test(routePlayerId)
  )

  // Sync tab from URL when navigating back/forward
  useEffect(() => {
    const t = params.get('tab') ?? 'shotmap'
    setActiveTab(t)
  }, [params])

  // Older leaderboard links used the player name as the route param. Understat
  // infographic endpoints need the numeric player id, so resolve name-like URLs
  // before requesting images.
  useEffect(() => {
    if (!routePlayerId || !needsPlayerResolution) {
      setResolvedPlayerId(null)
      setResolvingPlayer(false)
      return
    }

    let cancelled = false
    const query = params.get('name')
      ? safeDecode(params.get('name')!)
      : safeDecode(routePlayerId)

    setResolvedPlayerId(null)
    setResolvingPlayer(true)

    leaguesApi.searchPlayers(leagueId, query, season)
      .then(({ results }) => {
        if (cancelled) return

        const q = normaliseName(query)
        const exact = results.find(r => normaliseName(playerResultName(r)) === q)
        const fuzzy = results.find(r => {
          const name = normaliseName(playerResultName(r))
          return name.includes(q) || q.includes(name)
        })
        const match = exact ?? fuzzy ?? results[0]
        if (!match?.id) return

        const nextId = String(match.id)
        const nextParams = new URLSearchParams(params)
        nextParams.set('name', playerResultName(match) || query)
        nextParams.set('source', match.source || 'understat')

        setResolvedPlayerId(nextId)
        navigate(`/player/${encodeURIComponent(nextId)}?${nextParams.toString()}`, { replace: true })
      })
      .finally(() => {
        if (!cancelled) setResolvingPlayer(false)
      })

    return () => {
      cancelled = true
    }
  }, [routePlayerId, needsPlayerResolution, leagueId, season, paramsKey, navigate])

  if (!playerId) return null

  const playerName = params.get('name')
    ? safeDecode(params.get('name')!)
    : safeDecode(playerId)

  const showNotAvailable = !isFullInfographicLeague
  const effectivePlayerId = needsPlayerResolution ? (resolvedPlayerId ?? '') : playerId

  function imgSrc(): string {
    if (!effectivePlayerId) return ''

    switch (activeTab) {
      case 'shotmap':
        return infographicsApi.shotmap(effectivePlayerId, cumulative ? undefined : season)
      case 'career-xg':
        return infographicsApi.careerXg(effectivePlayerId)
      case 'radar':
        return infographicsApi.radar(effectivePlayerId, leagueId, season, position)
      case 'summary':
        return infographicsApi.summaryCard(effectivePlayerId, leagueId, cumulative ? undefined : season, position)
      case 'xg-arc':
        return infographicsApi.playerXgArc(effectivePlayerId, season)
      case 'shot-quality':
        return infographicsApi.playerShotQuality(effectivePlayerId, season)
      case 'shot-situation':
        return infographicsApi.playerShotSituation(effectivePlayerId, season)
      case 'season-compare':
        return infographicsApi.playerSeasonCompare(effectivePlayerId)
      case 'rolling-form':
        return infographicsApi.playerRollingForm(effectivePlayerId, season)
      default:
        return ''
    }
  }

  const showSeasonSelector   = ['shotmap', 'radar', 'summary', 'xg-arc', 'shot-quality', 'shot-situation', 'rolling-form'].includes(activeTab) && !cumulative
  const showPositionSelector = ['radar', 'summary'].includes(activeTab)
  const showCumulative       = ['shotmap', 'summary'].includes(activeTab) && isFullInfographicLeague
  const canShowInfographic   = !showNotAvailable && Boolean(effectivePlayerId)

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
            <CoverageNotice kind="player" />
          </div>
        ) : resolvingPlayer ? (
          <div style={{
            width: '100%',
            maxWidth: 672,
            minHeight: 320,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 8,
            background: '#0b0f16',
            color: '#4d5e7a',
            fontSize: 13,
          }}>
            Loading player data…
          </div>
        ) : !effectivePlayerId ? (
          <div style={{
            width: '100%',
            maxWidth: 672,
            minHeight: 320,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 8,
            background: '#0b0f16',
            color: '#4d5e7a',
            fontSize: 13,
          }}>
            Player data unavailable
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
      {canShowInfographic && (
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
