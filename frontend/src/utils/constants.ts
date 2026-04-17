export const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

export const CURRENT_SEASON = 2024

export const UNDERSTAT_LEAGUES = [
  { id: 'EPL',        label: 'Premier League' },
  { id: 'La_liga',    label: 'La Liga' },
  { id: 'Bundesliga', label: 'Bundesliga' },
  { id: 'Serie_A',    label: 'Serie A' },
  { id: 'Ligue_1',    label: 'Ligue 1' },
  { id: 'RFPL',       label: 'Russian Premier League' },
]

export const SEASONS = [2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015]

export type InfographicType =
  | 'shotmap'
  | 'career-xg'
  | 'radar'
  | 'summary-card'
  | 'passmap'
  | 'xg-timeline'
  | 'avg-positions'
  | 'season-card'
