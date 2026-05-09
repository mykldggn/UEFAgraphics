export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

export const CURRENT_SEASON = 2025

export const FULL_INFOGRAPHIC_LEAGUE_IDS = ['ENG-1', 'ESP-1', 'DEU-1', 'ITA-1', 'FRA-1'] as const
export const FULL_INFOGRAPHIC_LEAGUES = new Set<string>(FULL_INFOGRAPHIC_LEAGUE_IDS)
export const FULL_INFOGRAPHIC_SUPPORT_LABEL = 'Premier League · La Liga · Bundesliga · Serie A · Ligue 1'

export const LEAGUE_LABELS: Record<string, string> = {
  'ENG-1':    'Premier League',
  'ENG-2':    'Championship',
  'ENG-3':    'League One',
  'ENG-4':    'League Two',
  'ESP-1':    'La Liga',
  'DEU-1':    'Bundesliga',
  'ITA-1':    'Serie A',
  'FRA-1':    'Ligue 1',
  'NED-1':    'Eredivisie',
  'PRT-1':    'Primeira Liga',
  'BEL-1':    'First Division A',
  'SCO-1':    'Scottish Premiership',
  'CHE-1':    'Super League',
  'TUR-1':    'Süper Lig',
  'GRC-1':    'Super League Greece',
  'AUT-1':    'Austrian Bundesliga',
  'RUS-1':    'Russian Premier League',
  'UEFA-CL':  'Champions League',
  'UEFA-EL':  'Europa League',
  'UEFA-ECL': 'Conference League',
  'INT-EUROS':'European Championship',
  'INT-WC':   'World Cup',
  'INT-NL':   'UEFA Nations League',
}

export const UNDERSTAT_LEAGUES = [
  { id: 'EPL',        label: 'Premier League' },
  { id: 'La_liga',    label: 'La Liga' },
  { id: 'Bundesliga', label: 'Bundesliga' },
  { id: 'Serie_A',    label: 'Serie A' },
  { id: 'Ligue_1',    label: 'Ligue 1' },
]

// Understat coverage starts 2014/15 season
export const SEASONS = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014]

export type InfographicType =
  | 'shotmap'
  | 'career-xg'
  | 'radar'
  | 'summary-card'
  | 'passmap'
  | 'xg-timeline'
  | 'avg-positions'
  | 'season-card'
