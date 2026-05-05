import request, { imgUrl } from './client'

export const infographicsApi = {
  // Player
  shotmap: (playerId: string, season?: number) =>
    imgUrl(`/infographics/player/${playerId}/shotmap`,
           { ...(season != null ? { season } : {}) }),

  careerXg: (playerId: string, seasons?: number[]) =>
    imgUrl(`/infographics/player/${playerId}/career-xg`,
           { ...(seasons ? { seasons: seasons.join(',') } : {}) }),

  radar: (playerId: string, leagueId: string, season: number, position: string,
          compareId?: string) => {
    const params: Record<string, string | number> = { league_id: leagueId, season, position }
    if (compareId) params.compare_id = compareId
    return imgUrl(`/infographics/player/${playerId}/radar`, params)
  },

  summaryCard: (playerId: string, leagueId: string, season?: number, position?: string) => {
    const params: Record<string, string | number> = { league_id: leagueId }
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

  // Team — new analytics
  teamSquadMinutes: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/squad-minutes`, { team_name: teamName, league_id: leagueId, season }),

  teamMatchScatter: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/match-scatter`, { team_name: teamName, league_id: leagueId, season }),

  teamSituation: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/situation`, { team_name: teamName, league_id: leagueId, season }),

  teamXpoints: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/xpoints`, { team_name: teamName, league_id: leagueId, season }),

  teamScorerTimeline: (teamId: string, teamName: string, leagueId: string, season: number) =>
    imgUrl(`/infographics/team/${teamId}/scorer-timeline`, { team_name: teamName, league_id: leagueId, season }),

  // Player — new analytics (Understat only)
  playerXgArc: (playerId: string, season: number) =>
    imgUrl(`/infographics/player/${playerId}/xg-arc`, { season }),

  playerShotQuality: (playerId: string, season: number) =>
    imgUrl(`/infographics/player/${playerId}/shot-quality`, { season }),

  playerShotSituation: (playerId: string, season: number) =>
    imgUrl(`/infographics/player/${playerId}/shot-situation`, { season }),

  playerSeasonCompare: (playerId: string) =>
    imgUrl(`/infographics/player/${playerId}/season-compare`, {}),

  playerRollingForm: (playerId: string, season: number) =>
    imgUrl(`/infographics/player/${playerId}/rolling-form`, { season }),

  // League — infographic images
  leagueXgTable: (leagueId: string, season: number) =>
    imgUrl(`/infographics/league/${leagueId}/xg-table`, { season }),

  leagueQuadrant: (leagueId: string, season: number) =>
    imgUrl(`/infographics/league/${leagueId}/quadrant`, { season }),

  leagueGoldenBoot: (leagueId: string, season: number) =>
    imgUrl(`/infographics/league/${leagueId}/golden-boot`, { season }),

  leagueFormTable: (leagueId: string, season: number) =>
    imgUrl(`/infographics/league/${leagueId}/form-table`, { season }),

  leagueOverperformers: (leagueId: string, season: number) =>
    imgUrl(`/infographics/league/${leagueId}/overperformers`, { season }),
}

export interface LineupPlayer {
  player: string
  position: string
  minutes: number
  id?: string
  source?: string   // 'understat' | 'fotmob'
}
