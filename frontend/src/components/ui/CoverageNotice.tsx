import { FULL_INFOGRAPHIC_SUPPORT_LABEL } from '../../utils/constants'

type NoticeKind = 'player' | 'team' | 'league'

const PARTIAL_LEAGUE_BODY = 'This league is not shown in the infographic selector because full current-season Player, Team, and League coverage cannot be replicated at Understat quality yet.'

const COPY: Record<NoticeKind, { title: string; body: string }> = {
  player: {
    title: 'Player infographic unavailable',
    body: 'This player infographic requires full current-season Understat coverage across player, team, and league views.',
  },
  team: {
    title: 'Team infographics unavailable',
    body: PARTIAL_LEAGUE_BODY,
  },
  league: {
    title: 'League infographics unavailable',
    body: PARTIAL_LEAGUE_BODY,
  },
}

export default function CoverageNotice({ kind }: { kind: NoticeKind }) {
  const copy = COPY[kind]
  return (
    <div style={{
      background: '#0c1321',
      border: '1px solid #1a2235',
      borderRadius: 8,
      padding: '48px 32px',
      textAlign: 'center',
    }}>
      <div style={{ color: '#e6e9f4', fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
        {copy.title}
      </div>
      <div style={{ color: '#4d5e7a', fontSize: 13, maxWidth: 520, margin: '0 auto', lineHeight: 1.6 }}>
        {copy.body}
      </div>
      <div style={{ color: '#1e2c44', fontSize: 11, marginTop: 10 }}>
        Supported: {FULL_INFOGRAPHIC_SUPPORT_LABEL}
      </div>
    </div>
  )
}
