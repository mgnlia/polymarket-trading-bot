interface Props {
  label: string
  value: string | number
  sub?: string
  color?: 'green' | 'red' | 'blue' | 'yellow' | 'default'
}

const colorMap = {
  green: 'text-green-400',
  red: 'text-red-400',
  blue: 'text-blue-400',
  yellow: 'text-yellow-400',
  default: 'text-poly-text',
}

export default function StatCard({ label, value, sub, color = 'default' }: Props) {
  return (
    <div className="card">
      <p className="text-xs text-poly-muted mb-1">{label}</p>
      <p className={`text-lg font-bold ${colorMap[color]}`}>{value}</p>
      {sub && <p className="text-xs text-poly-muted mt-0.5">{sub}</p>}
    </div>
  )
}
