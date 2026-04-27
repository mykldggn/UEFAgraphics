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
    <div className={className} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {label && (
        <label style={{ fontSize: 10, color: '#4d5e7a', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          {label}
        </label>
      )}
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        style={{
          background: '#111b2f',
          border: '1px solid #1a2235',
          color: '#e6e9f4',
          fontSize: 13,
          borderRadius: 5,
          padding: '7px 10px',
          outline: 'none',
          appearance: 'none',
          cursor: 'pointer',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value} style={{ background: '#0c1321' }}>{opt.label}</option>
        ))}
      </select>
    </div>
  )
}
