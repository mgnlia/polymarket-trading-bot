interface Props {
  scores: {
    diversity: number
    volume: number
    profitability: number
    liquidity: number
  }
}

function Bar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.min(100, Math.max(0, value))
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-poly-muted">{label}</span>
        <span className="text-poly-text font-medium">{pct.toFixed(0)}%</span>
      </div>
      <div className="h-2 bg-poly-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function AirdropMeter({ scores }: Props) {
  const overall = (scores.diversity + scores.volume + scores.profitability + scores.liquidity) / 4
  const tier = overall >= 80 ? 'Diamond' : overall >= 60 ? 'Gold' : overall >= 40 ? 'Silver' : 'Bronze'
  const tierColor = overall >= 80 ? 'text-blue-300' : overall >= 60 ? 'text-yellow-400' : overall >= 40 ? 'text-gray-300' : 'text-orange-400'

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-poly-text">🎁 Airdrop Score</h3>
        <span className={`text-sm font-bold ${tierColor}`}>{tier}</span>
      </div>

      <div className="relative flex items-center justify-center mb-4">
        <svg viewBox="0 0 100 60" className="w-32 h-20">
          <path d="M10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#2a2a3a" strokeWidth="8" strokeLinecap="round" />
          <path
            d="M10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke={overall >= 80 ? '#60a5fa' : overall >= 60 ? '#facc15' : overall >= 40 ? '#9ca3af' : '#fb923c'}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${(overall / 100) * 125.6} 125.6`}
          />
        </svg>
        <div className="absolute bottom-0 text-center">
          <span className="text-2xl font-bold text-poly-text">{overall.toFixed(0)}</span>
          <span className="text-xs text-poly-muted block">/ 100</span>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Bar label="Market Diversity" value={scores.diversity} color="bg-blue-500" />
        <Bar label="Trading Volume" value={scores.volume} color="bg-green-500" />
        <Bar label="Profitability" value={scores.profitability} color="bg-yellow-500" />
        <Bar label="Liquidity Provision" value={scores.liquidity} color="bg-purple-500" />
      </div>
    </div>
  )
}
