import request, { imgUrl } from './client'

export const infographicsApi = {
  // Player
  shotmap: (playerId: string, season?: number, source = 'understat') =>
    imgUrl(`/infographics/player/${playerId}/shotmap`,
           { ...(season != null ? { season } : {}), source }),

  careerXg: (playerId: string, seasons?: number[], source = 'understat') =>
    imgUrl(`/infographics/player/${playerId}/career-xg`,
           { ...(seasons ? { seasons: seasons.join(',') } : {}), source }),

  radar: (playerId: string, leagueId: string, season: number, position: string,
          compareId?: string, source = 'understat') => {
    const params: Record<string, string | number> = { league_id: leagueId, season, position, source }
    if (compareId) params.compare_id = compareId
    return imgUrl(`/infographics/player/${playerId}/radar`, params)
  },

  summaryCard: (playerId: string, leagueId: string, season?: number, position?: string,
                source = 'understat') => {
    const params: Record<string, string | number> = { league_id: leagueId, source }
    if (season != null) params.season = season
    if (position)       params.position = position
    return imgUrl(`/infographics/player/${playerId}/summary-card`, params)
  },

  // Team (Understat)
  teamXgTimeline: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/xg-timeline`, { team_name: teamName, league_id: leagueId, season }),

  // Team (API-Football)
  teamSeasonCard: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/season-card`, { team_name: teamName, league_id: leagueId, season }),

  teamLineup: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/lineup`, { team_name: teamName, league_id: leagueId, season }),

  teamLineupPlayers: (teamId: string, teamName: string, leagueId: string, season: number) =>
    request<{ players: LineupPlayer[]; formation: string }>(
      `/infographics/team/${teamId}/lineup-players`,
      { team_name: teamName, league_id: leagueId, season }
    ),
}

export interface LineupPlayer {
  player: string
  position: string
  minutes: number
  id?: string
  source?: string   // 'understat' | 'fotmob'
}
