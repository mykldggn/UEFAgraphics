interface Option {
  value: string | number
  label: string
}

interface Props {
  label?: string
  value: string | number
  options: Option[]
  onChange: (value: string) => void
  disabled?: boolean
  className?: string
}

export default function Select({ label, value, options, onChange, disabled, className = '' }: Props) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {label && <label className="text-xs text-sub font-medium uppercase tracking-wide">{label}</label>}
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className="bg-card border border-border text-white text-sm rounded-md px-3 py-2
                   focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50
                   disabled:cursor-not-allowed appearance-none cursor-pointer"
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  )
}
