interface Trade {
  id: string
  market_id: string
  question?: string
  side: string
  size: number
  price: number
  pnl: number
  strategy: string
  status: string
  timestamp: string
}

export default function TradeTable({ trades }: { trades: Trade[] }) {
  if (!trades.length) {
    return (
      <div className="card text-center py-12">
        <span className="text-4xl mb-3 block">📊</span>
        <p className="text-poly-muted text-sm">No trades yet. Start the bot to begin trading.</p>
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <h3 className="text-sm font-semibold text-poly-text mb-3">Recent Trades ({trades.length})</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-poly-border text-poly-muted">
              <th className="text-left py-2 pr-3">Market</th>
              <th className="text-left py-2 pr-3">Strategy</th>
              <th className="text-left py-2 pr-3">Side</th>
              <th className="text-right py-2 pr-3">Size</th>
              <th className="text-right py-2 pr-3">Price</th>
              <th className="text-right py-2 pr-3">P&L</th>
              <th className="text-left py-2 pr-3">Status</th>
              <th className="text-left py-2">Time</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.id} className="border-b border-poly-border/50 hover:bg-poly-card/50">
                <td className="py-2 pr-3 text-poly-text max-w-[200px] truncate">
                  {t.question || t.market_id.slice(0, 16) + '…'}
                </td>
                <td className="py-2 pr-3">
                  <span className={`badge-${t.strategy === 'arbitrage' ? 'green' : t.strategy === 'market_maker' ? 'blue' : 'yellow'}`}>
                    {t.strategy === 'arbitrage' ? 'ARB' : t.strategy === 'market_maker' ? 'MM' : 'MOM'}
                  </span>
                </td>
                <td className={`py-2 pr-3 font-medium ${t.side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                  {t.side}
                </td>
                <td className="py-2 pr-3 text-right text-poly-text">{t.size.toFixed(2)}</td>
                <td className="py-2 pr-3 text-right text-poly-text">{(t.price * 100).toFixed(1)}¢</td>
                <td className={`py-2 pr-3 text-right font-medium ${t.pnl > 0 ? 'text-green-400' : t.pnl < 0 ? 'text-red-400' : 'text-poly-muted'}`}>
                  {t.pnl > 0 ? '+' : ''}{t.pnl.toFixed(3)}
                </td>
                <td className="py-2 pr-3">
                  <span className={`badge-${t.status === 'filled' ? 'green' : t.status === 'pending' ? 'yellow' : 'default'}`}>
                    {t.status}
                  </span>
                </td>
                <td className="py-2 text-poly-muted">
                  {new Date(t.timestamp).toLocaleTimeString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
