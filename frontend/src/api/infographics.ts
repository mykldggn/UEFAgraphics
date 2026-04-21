import { imgUrl } from './client'

export const infographicsApi = {
  // Player (Understat)
  shotmap: (playerId: string, season: number) =>
    imgUrl(`/infographics/player/${playerId}/shotmap`, { season }),

  careerXg: (playerId: string, seasons?: number[]) =>
    imgUrl(`/infographics/player/${playerId}/career-xg`,
           seasons ? { seasons: seasons.join(',') } : {}),

  // Player (API-Football)
  radar: (playerId: string, leagueId: string, season: number, position: string, compareId?: string) => {
    const params: Record<string, string | number> = { league_id: leagueId, season, position }
    if (compareId) params.compare_id = compareId
    return imgUrl(`/infographics/player/${playerId}/radar`, params)
  },

  summaryCard: (playerId: string, leagueId: string, season: number, position: string) =>
    imgUrl(`/infographics/player/${playerId}/summary-card`, { league_id: leagueId, season, position }),

  // Team (Understat)
  teamXgTimeline: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/xg-timeline`, { team_name: teamName, league_id: leagueId, season }),

  // Team (API-Football)
  teamSeasonCard: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/season-card`, { team_name: teamName, league_id: leagueId, season }),
}
