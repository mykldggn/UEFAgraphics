import request from './client'

export interface League {
  id: string
  label: string
  country: string
}

export interface Team {
  id: string
  name: string
}

export interface Player {
  id?: string
  player?: string
  name?: string
  team: string
  pos?: string
}

export interface TableRow {
  team: string
  points?: number
  wins?: number
  draws?: number
  losses?: number
  goals_for?: number
  goals_against?: number
  [key: string]: unknown
}

export const leaguesApi = {
  list: () => request<League[]>('/leagues'),

  teams: (leagueId: string, season: number) =>
    request<{ teams: Team[] }>(`/leagues/${leagueId}/teams`, { season }),

  searchPlayers: (leagueId: string, q: string, season: number) =>
    request<{ results: Player[] }>(`/leagues/${leagueId}/players/search`, { q, season }),

  understatSearch: (q: string) =>
    request<{ results: Player[] }>('/leagues/understat/search', { q }),

  understatPlayers: (league: string, season: number) =>
    request<{ players: Player[] }>(`/leagues/understat/${league}/players`, { season }),

  table: (leagueId: string, season: number) =>
    request<{ table: TableRow[] }>(`/leagues/${leagueId}/table`, { season }),

  teamXgHistory: (teamId: string, season: number) =>
    request<{ history: unknown[] }>(`/leagues/understat/team/${teamId}/xg-history`, { season }),
}
