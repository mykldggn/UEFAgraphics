import { useState, useEffect, useCallback } from 'react'
import { matchesApi, type FootballMatch } from '../../api/matches'

// FotMob integer league IDs → short label
const LEAGUE_SHORT: Record<number, string> = {
  47:    'PL',   87:    'LL',   54:    'BL',
  55:    'SA',   53:    'L1',   48:    'CH',
  57:    'ERE',  61:    'PPL',  58:    'SP',
  42:    'UCL',  73:    'UEL',  10478: 'UECL',
}

// leagueShort string from fdorg fallback → label
const LEAGUE_SHORT_STR: Record<string, string> = {
  'UEFA-CL': 'UCL', 'UEFA-EL': 'UEL', 'UEFA-ECL': 'UECL',
  'ENG-1': 'PL', 'ESP-1': 'LL', 'ITA-1': 'SA', 'DEU-1': 'BL', 'FRA-1': 'L1',
}

function leagueLabel(m: FootballMatch): string {
  if (m.leagueId) {
    const s = LEAGUE_SHORT[m.leagueId]
    if (s) return s
  }
  if ((m as any).leagueShort) return LEAGUE_SHORT_STR[(m as any).leagueShort] ?? ''
  return m.leagueName?.slice(0, 4).toUpperCase() ?? ''
}

const ABBREV: Record<string, string> = {
  // England
  'Arsenal FC': 'ARS', 'Arsenal': 'ARS',
  'Chelsea FC': 'CHE', 'Chelsea': 'CHE',
  'Liverpool FC': 'LIV', 'Liverpool': 'LIV',
  'Manchester City FC': 'MCI', 'Manchester City': 'MCI', 'Man City': 'MCI',
  'Manchester United FC': 'MUN', 'Manchester United': 'MUN', 'Man United': 'MUN',
  'Tottenham Hotspur FC': 'TOT', 'Tottenham Hotspur': 'TOT', 'Tottenham': 'TOT',
  'Newcastle United FC': 'NEW', 'Newcastle United': 'NEW', 'Newcastle': 'NEW',
  'Aston Villa FC': 'AVL', 'Aston Villa': 'AVL',
  'West Ham United FC': 'WHU', 'West Ham United': 'WHU', 'West Ham': 'WHU',
  'Brighton & Hove Albion FC': 'BHA', 'Brighton': 'BHA',
  'Brentford FC': 'BRE', 'Brentford': 'BRE',
  'Fulham FC': 'FUL', 'Fulham': 'FUL',
  'Crystal Palace FC': 'CRY', 'Crystal Palace': 'CRY',
  'Wolverhampton Wanderers FC': 'WOL', 'Wolverhampton Wanderers': 'WOL', 'Wolves': 'WOL',
  'Everton FC': 'EVE', 'Everton': 'EVE',
  'Nottingham Forest FC': 'NFO', 'Nottingham Forest': 'NFO', 'Nottm Forest': 'NFO',
  'Leicester City FC': 'LEI', 'Leicester City': 'LEI', 'Leicester': 'LEI',
  'Ipswich Town FC': 'IPS', 'Ipswich Town': 'IPS', 'Ipswich': 'IPS',
  'Southampton FC': 'SOU', 'Southampton': 'SOU',
  'Bournemouth': 'BOU', 'AFC Bournemouth': 'BOU',
  'Leeds United': 'LEE', 'Leeds United FC': 'LEE',
  // Spain
  'Real Madrid CF': 'RMA', 'Real Madrid': 'RMA',
  'FC Barcelona': 'BAR', 'Barcelona': 'BAR',
  'Club Atlético de Madrid': 'ATL', 'Atlético de Madrid': 'ATL', 'Atletico Madrid': 'ATL',
  'Sevilla FC': 'SEV', 'Sevilla': 'SEV',
  'Real Betis Balompié': 'BET', 'Real Betis': 'BET',
  'Valencia CF': 'VAL', 'Valencia': 'VAL',
  'Athletic Club': 'ATH', 'Athletic Bilbao': 'ATH',
  'Real Sociedad de Fútbol': 'RSO', 'Real Sociedad': 'RSO',
  'Villarreal CF': 'VIL', 'Villarreal': 'VIL',
  'Getafe CF': 'GET', 'Girona FC': 'GIR', 'Osasuna': 'OSA',
  'Celta de Vigo': 'CEL', 'RC Celta': 'CEL', 'Celta Vigo': 'CEL',
  'RCD Mallorca': 'MAL', 'Mallorca': 'MAL',
  'Rayo Vallecano': 'RAY', 'UD Las Palmas': 'LPA',
  'RCD Espanyol': 'ESP', 'Espanyol': 'ESP',
  'Deportivo Alavés': 'ALA', 'CD Leganés': 'LEG',
  'Real Valladolid CF': 'VLD', 'Real Valladolid': 'VLD',
  // Germany
  'FC Bayern München': 'BAY', 'Bayern Munich': 'BAY', 'Bayern': 'BAY',
  'Borussia Dortmund': 'BVB', 'Dortmund': 'BVB',
  'RB Leipzig': 'RBL',
  'Bayer 04 Leverkusen': 'LEV', 'Bayer Leverkusen': 'LEV', 'Leverkusen': 'LEV',
  'Eintracht Frankfurt': 'SGE', 'Frankfurt': 'SGE',
  'VfB Stuttgart': 'STU', 'Stuttgart': 'STU',
  'SC Freiburg': 'SCF', 'Freiburg': 'SCF',
  'TSG Hoffenheim': 'HOF', 'Hoffenheim': 'HOF',
  'Borussia Mönchengladbach': 'BMG', "Borussia M'gladbach": 'BMG',
  '1. FSV Mainz 05': 'MAI', 'Mainz 05': 'MAI', 'Mainz': 'MAI',
  'FC Augsburg': 'AUG', 'Augsburg': 'AUG',
  '1. FC Union Berlin': 'UNB', 'Union Berlin': 'UNB',
  'VfL Wolfsburg': 'WOB', 'Wolfsburg': 'WOB',
  'VfL Bochum': 'BOC', 'Bochum': 'BOC',
  'SV Werder Bremen': 'SVW', 'Werder Bremen': 'SVW',
  '1. FC Heidenheim 1846': 'HDH', '1. FC Heidenheim': 'HDH', 'Heidenheim': 'HDH',
  'Holstein Kiel': 'KIE', 'FC St. Pauli': 'STP',
  // Italy
  'Juventus FC': 'JUV', 'Juventus': 'JUV',
  'FC Internazionale Milano': 'INT', 'Internazionale': 'INT', 'Inter': 'INT',
  'AC Milan': 'MIL', 'Milan': 'MIL',
  'SSC Napoli': 'NAP', 'Napoli': 'NAP',
  'AS Roma': 'ROM', 'Roma': 'ROM',
  'SS Lazio': 'LAZ', 'Lazio': 'LAZ',
  'Atalanta BC': 'ATA', 'Atalanta': 'ATA',
  'ACF Fiorentina': 'FIO', 'Fiorentina': 'FIO',
  'Torino FC': 'TOR', 'Torino': 'TOR',
  'Bologna FC 1909': 'BOL', 'Bologna FC': 'BOL', 'Bologna': 'BOL',
  'Udinese Calcio': 'UDI', 'Udinese': 'UDI',
  'Empoli FC': 'EMP', 'Empoli': 'EMP',
  'US Lecce': 'LEC', 'Lecce': 'LEC',
  'AC Monza': 'MON', 'Monza': 'MON',
  'Hellas Verona FC': 'VER', 'Hellas Verona': 'VER', 'Verona': 'VER',
  'Cagliari Calcio': 'CAG', 'Cagliari': 'CAG',
  'Genoa CFC': 'GEN', 'Genoa': 'GEN',
  'Como 1907': 'COM', 'Venezia FC': 'VEN', 'Parma Calcio 1913': 'PAR',
  // France
  'Paris Saint-Germain FC': 'PSG', 'Paris Saint-Germain': 'PSG', 'PSG': 'PSG',
  'Olympique de Marseille': 'OM', 'Marseille': 'MAR',
  'Olympique Lyonnais': 'OL', 'Lyon': 'LYO',
  'AS Monaco FC': 'MON', 'AS Monaco': 'MCO', 'Monaco': 'MCO',
  'LOSC Lille': 'LIL', 'Lille': 'LIL',
  'Stade Rennais FC': 'REN', 'Rennes': 'REN',
  'OGC Nice': 'NIC', 'Nice': 'NIC',
  'RC Lens': 'LEN', 'Lens': 'LEN',
  'RC Strasbourg Alsace': 'STR', 'Strasbourg': 'STR',
  'FC Nantes': 'NAN', 'Nantes': 'NAN',
  'Stade de Reims': 'REI', 'Reims': 'REI',
  'Stade Brestois 29': 'BRE', 'Brest': 'BRE',
  'Toulouse FC': 'TOU', 'Toulouse': 'TOU',
  'Montpellier HSC': 'MTP', 'Montpellier': 'MTP',
  'Le Havre AC': 'LHV', 'Le Havre': 'LHV',
  'AS Saint-Étienne': 'STE', 'SCO Angers': 'ANG',
  'AJ Auxerre': 'AUX',
  // Portugal
  'SL Benfica': 'BEN', 'Benfica': 'BEN',
  'FC Porto': 'POR', 'Porto': 'POR',
  'Sporting CP': 'SPO', 'Sporting': 'SPO',
  // Netherlands
  'AFC Ajax': 'AJA', 'Ajax': 'AJA',
  'PSV Eindhoven': 'PSV', 'PSV': 'PSV',
  'Feyenoord': 'FEY',
  // UCL/UEL clubs
  'Celtic FC': 'CEL', 'Rangers FC': 'RAN',
  'Club Brugge KV': 'BRU', 'Club Brugge': 'BRU',
  'RSC Anderlecht': 'AND',
  'Galatasaray SK': 'GAL', 'Galatasaray': 'GAL',
  'Fenerbahçe SK': 'FEN', 'Fenerbahçe': 'FEN',
}

function shortName(full: string): string {
  if (!full) return ''
  if (ABBREV[full]) return ABBREV[full]
  // Fallback: first 3 chars of first significant word
  const parts = full.trim().split(/\s+/)
  return parts[0].slice(0, 3).toUpperCase()
}

function addDays(isoDate: string, n: number): string {
  const d = new Date(isoDate + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

function formatDateLabel(isoDate: string): string {
  const today = new Date().toLocaleDateString('en-CA')
  if (isoDate === today) return 'Today'
  const d = new Date(isoDate + 'T12:00:00Z')
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

// ── Competition filter buttons ──────────────────────────────────────────────
const COMP_FILTERS = ['All', 'UCL', 'UEL', 'UECL', 'PL', 'LL', 'BL', 'SA', 'L1', 'CH', 'ERE', 'SP']

function NavBtn({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: 'none',
        border: 'none',
        color: disabled ? '#1e2c44' : '#4d5e7a',
        cursor: disabled ? 'default' : 'pointer',
        fontSize: 13,
        padding: '0 6px',
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      {label}
    </button>
  )
}

function MatchCard({ m }: { m: FootballMatch }) {
  const hasScore = m.homeScore !== null && m.awayScore !== null
  const lbl      = leagueLabel(m)
  const scoreColor = m.isLive ? '#22C55E' : m.isFinished ? '#c9a84c' : '#4d5e7a'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '0 12px', height: '100%', flexShrink: 0,
      borderRight: '1px solid rgba(26,34,53,0.8)',
      userSelect: 'none',
    }}>
      {lbl && (
        <span style={{ fontSize: 9, fontWeight: 700, color: '#4d5e7a', letterSpacing: '0.05em', minWidth: 20 }}>
          {lbl}
        </span>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        {m.homeTeamCrest && (
          <img src={m.homeTeamCrest} alt="" style={{ width: 15, height: 15, objectFit: 'contain', flexShrink: 0 }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
        )}
        <span style={{ fontSize: 12, color: '#e6e9f4', fontWeight: 600, letterSpacing: '0.03em' }}>
          {shortName(m.homeTeam)}
        </span>
      </div>
      <div style={{
        fontSize: 13, fontFamily: '"Bebas Neue", monospace', letterSpacing: '0.06em',
        color: scoreColor, minWidth: 36, textAlign: 'center',
      }}>
        {hasScore ? `${m.homeScore} - ${m.awayScore}` : m.status}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <span style={{ fontSize: 12, color: '#e6e9f4', fontWeight: 600, letterSpacing: '0.03em' }}>
          {shortName(m.awayTeam)}
        </span>
        {m.awayTeamCrest && (
          <img src={m.awayTeamCrest} alt="" style={{ width: 15, height: 15, objectFit: 'contain', flexShrink: 0 }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
        )}
      </div>
      {m.isLive && m.minute && (
        <span style={{ fontSize: 9, color: '#22C55E', fontWeight: 700, letterSpacing: '0.05em' }}>
          {m.minute}
        </span>
      )}
    </div>
  )
}

export default function ScoresTicker() {
  const todayIso = new Date().toLocaleDateString('en-CA')
  const [selectedDate, setSelectedDate] = useState(todayIso)
  const [compFilter, setCompFilter]     = useState('All')
  const [matches, setMatches]           = useState<FootballMatch[]>([])
  const [loading, setLoading]           = useState(true)

  const fetchMatches = useCallback(() => {
    const dateFm = selectedDate.replace(/-/g, '')
    matchesApi.today(dateFm)
      .then(r => { setMatches(Array.isArray(r?.matches) ? r.matches : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [selectedDate])

  useEffect(() => {
    setLoading(true)
    fetchMatches()
    const iv = setInterval(fetchMatches, 60_000)
    return () => clearInterval(iv)
  }, [fetchMatches])

  const visible = compFilter === 'All'
    ? matches
    : matches.filter(m => leagueLabel(m) === compFilter)

  const canGoForward = selectedDate < addDays(todayIso, 7)
  const isToday     = selectedDate === todayIso

  // Always render — controls should be visible even when no matches load
  return (
    <div style={{
      background: '#07090f',
      borderBottom: '1px solid #1a2235',
      flexShrink: 0,
      userSelect: 'none',
    }}>
      {/* ── Controls row ──────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderBottom: '1px solid rgba(26,34,53,0.5)',
        overflowX: 'auto',
        scrollbarWidth: 'none',
      }}>
        {/* Date nav */}
        <NavBtn label="‹" onClick={() => setSelectedDate(d => addDays(d, -1))} />
        <button
          onClick={() => setSelectedDate(todayIso)}
          style={{
            background: isToday ? 'rgba(201,168,76,0.12)' : 'none',
            border: isToday ? '1px solid rgba(201,168,76,0.3)' : '1px solid transparent',
            borderRadius: 4,
            color: isToday ? '#c9a84c' : '#4d5e7a',
            fontSize: 10,
            padding: '2px 8px',
            cursor: 'pointer',
            fontWeight: 600,
            letterSpacing: '0.04em',
            flexShrink: 0,
          }}
        >
          {formatDateLabel(selectedDate).toUpperCase()}
        </button>
        <NavBtn label="›" onClick={() => setSelectedDate(d => addDays(d, 1))} disabled={!canGoForward} />

        {/* Divider */}
        <span style={{ width: 1, height: 14, background: '#1a2235', flexShrink: 0, margin: '0 4px' }} />

        {/* Competition filter pills */}
        {COMP_FILTERS.map(c => (
          <button
            key={c}
            onClick={() => setCompFilter(c)}
            style={{
              background: compFilter === c ? 'rgba(201,168,76,0.12)' : 'none',
              border: compFilter === c ? '1px solid rgba(201,168,76,0.3)' : '1px solid transparent',
              borderRadius: 4,
              color: compFilter === c ? '#c9a84c' : '#4d5e7a',
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: '0.05em',
              padding: '2px 7px',
              cursor: 'pointer',
              flexShrink: 0,
              transition: 'all 0.12s',
            }}
          >
            {c}
          </button>
        ))}
      </div>

      {/* ── Scrollable matches ─────────────────────────────────────────────── */}
      <div style={{
        height: 40,
        display: 'flex',
        alignItems: 'center',
        overflowX: 'auto',
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
      } as React.CSSProperties}>
        {loading ? (
          <span style={{ padding: '0 16px', fontSize: 11, color: '#1e2c44' }}>Loading…</span>
        ) : visible.length === 0 ? (
          <span style={{ padding: '0 16px', fontSize: 11, color: '#1e2c44' }}>
            No matches · {selectedDate}
          </span>
        ) : (
          visible.map((m, i) => <MatchCard key={m.id ?? i} m={m} />)
        )}
      </div>
    </div>
  )
}
