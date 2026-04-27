interface Tab {
  id: string
  label: string
}

interface Props {
  tabs: Tab[]
  active: string
  onChange: (id: string) => void
}

export default function TabBar({ tabs, active, onChange }: Props) {
  return (
    <div style={{ display: 'flex', borderBottom: '1px solid #1a2235', marginBottom: 24, overflowX: 'auto' }}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          style={{
            padding: '9px 18px',
            marginBottom: -1,
            fontSize: 13,
            fontWeight: active === tab.id ? 600 : 400,
            color: active === tab.id ? '#c9a84c' : '#4d5e7a',
            borderBottom: active === tab.id ? '2px solid #c9a84c' : '2px solid transparent',
            background: 'none',
            border: 'none',
            borderBottomWidth: 2,
            borderBottomStyle: 'solid',
            borderBottomColor: active === tab.id ? '#c9a84c' : 'transparent',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            transition: 'all 0.15s',
            outline: 'none',
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
