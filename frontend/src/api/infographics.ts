import { imgUrl } from './client'

export const infographicsApi = {
  // Player (Understat)
  shotmap: (playerId: string, season: number) =>
    imgUrl(`/infographics/player/${playerId}/shotmap`, { season }),

  careerXg: (playerId: string, seasons?: number[]) =>
    imgUrl(`/infographics/player/${playerId}/career-xg`,
           seasons ? { seasons: seasons.join(',') } : {}),

  // Player (FBref)
  radar: (player: string, leagueId: string, season: number, position: string, compareTo?: string) => {
    const params: Record<string, string | number> = { player, league_id: leagueId, season, position }
    if (compareTo) params.compare_player = compareTo
    return imgUrl('/infographics/player/fbref/radar', params)
  },

  summaryCard: (player: string, leagueId: string, season: number, position: string) =>
    imgUrl('/infographics/player/fbref/summary-card', { player, league_id: leagueId, season, position }),

  passmap: (player: string, leagueId: string, season: number) =>
    imgUrl('/infographics/player/fbref/passmap', { player, league_id: leagueId, season }),

  // Team (Understat)
  teamXgTimeline: (teamId: string, teamName: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/xg-timeline`, { team_name: teamName, season }),

  // Team (FBref)
  teamSeasonCard: (team: string, leagueId: string, season: number) =>
    imgUrl('/infographics/team/fbref/season-card', { team, league_id: leagueId, season }),
}
