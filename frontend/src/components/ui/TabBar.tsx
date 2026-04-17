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
    <div className="flex gap-1 border-b border-border pb-0 mb-6 overflow-x-auto">
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
            active === tab.id
              ? 'text-accent border-accent'
              : 'text-sub border-transparent hover:text-white'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
