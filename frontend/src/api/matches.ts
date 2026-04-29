import request from './client'

export interface FootballMatch {
  id: number | null
  // League info
  leagueName: string
  leagueId: number
  leagueShort?: string   // present on fdorg fallback data
  // Teams
  homeTeam: string
  awayTeam: string
  homeTeamId: number | null
  awayTeamId: number | null
  homeTeamCrest: string
  awayTeamCrest: string
  // Score
  homeScore: number | null
  awayScore: number | null
  // Status
  status: string       // "FT", "HH:MM", "LIVE", "45'"
  minute: string       // e.g. "45'" when live
  isLive: boolean
  isFinished: boolean
  scorers: string[]
}

export const matchesApi = {
  today: (matchDate?: string) =>
    request<{ date: string; matches: FootballMatch[] }>(
      '/matches/today',
      matchDate ? { match_date: matchDate } : {}
    ),
}
