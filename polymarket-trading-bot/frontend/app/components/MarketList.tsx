interface Market {
  condition_id: string
  question: string
  yes_price: number
  no_price: number
  volume: number
  spread: number
  arb_opportunity?: boolean
  category?: string
  end_date?: string
}

export default function MarketList({ markets }: { markets: Market[] }) {
  if (!markets.length) {
    return (
      <div className="card text-center py-12">
        <span className="text-4xl mb-3 block">🔍</span>
        <p className="text-poly-muted text-sm">No markets loaded. Click "Scan Markets" to fetch live markets.</p>
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <h3 className="text-sm font-semibold text-poly-text mb-3">Active Markets ({markets.length})</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-poly-border text-poly-muted">
              <th className="text-left py-2 pr-3">Question</th>
              <th className="text-right py-2 pr-3">YES</th>
              <th className="text-right py-2 pr-3">NO</th>
              <th className="text-right py-2 pr-3">Spread</th>
              <th className="text-right py-2 pr-3">Volume</th>
              <th className="text-left py-2">Signals</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((m) => (
              <tr key={m.condition_id} className="border-b border-poly-border/50 hover:bg-poly-card/50">
                <td className="py-2 pr-3 text-poly-text max-w-[280px] truncate">{m.question}</td>
                <td className="py-2 pr-3 text-right text-green-400 font-medium">
                  {(m.yes_price * 100).toFixed(1)}¢
                </td>
                <td className="py-2 pr-3 text-right text-red-400 font-medium">
                  {(m.no_price * 100).toFixed(1)}¢
                </td>
                <td className={`py-2 pr-3 text-right font-medium ${m.spread > 0.05 ? 'text-yellow-400' : 'text-poly-muted'}`}>
                  {(m.spread * 100).toFixed(1)}¢
                </td>
                <td className="py-2 pr-3 text-right text-poly-muted">
                  ${(m.volume || 0).toLocaleString()}
                </td>
                <td className="py-2 flex gap-1 flex-wrap">
                  {m.arb_opportunity && (
                    <span className="badge-green">ARB</span>
                  )}
                  {m.spread > 0.03 && (
                    <span className="badge-blue">MM</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
