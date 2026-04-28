import request from './client'

export interface FootballMatch {
  competition: string
  competitionId: string
  homeTeam: string
  homeShort: string
  homeCrest: string
  homeScore: number | null
  awayTeam: string
  awayShort: string
  awayCrest: string
  awayScore: number | null
  statusRaw: string
  statusLabel: string
  isLive: boolean
  isFinished: boolean
  utcDate: string
}

export const matchesApi = {
  today: (matchDate?: string) =>
    request<{ date: string; matches: FootballMatch[] }>(
      '/matches/today',
      matchDate ? { match_date: matchDate } : {}
    ),
}
