'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  fetchStatus, fetchTrades, fetchAirdrop, fetchMarkets,
  fetchLogs, botStart, botStop, botPause, runCycle, scanMarkets, getSSEUrl
} from './lib/api'
import StatCard from './components/StatCard'
import AirdropMeter from './components/AirdropMeter'
import TradeTable from './components/TradeTable'
import LogFeed from './components/LogFeed'
import MarketList from './components/MarketList'

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null)
  const [trades, setTrades] = useState<any[]>([])
  const [airdrop, setAirdrop] = useState<any>(null)
  const [markets, setMarkets] = useState<any[]>([])
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'markets' | 'trades'>('overview')
  const [actionLoading, setActionLoading] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [s, t, a, m, l] = await Promise.allSettled([
        fetchStatus(),
        fetchTrades(50),
        fetchAirdrop(),
        fetchMarkets(30),
        fetchLogs(40),
      ])
      if (s.status === 'fulfilled') setStatus(s.value)
      if (t.status === 'fulfilled') setTrades(t.value.trades || [])
      if (a.status === 'fulfilled') setAirdrop(a.value)
      if (m.status === 'fulfilled') setMarkets(m.value.markets || [])
      if (l.status === 'fulfilled') setLogs(l.value.logs || [])
      setError(null)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [loadData])

  // SSE for real-time updates
  useEffect(() => {
    let es: EventSource
    try {
      es = new EventSource(getSSEUrl())
      es.addEventListener('status', (e: any) => {
        try {
          const data = JSON.parse(e.data)
          setStatus({ ok: true, bot: data.bot })
          if (data.recent_logs) setLogs(data.recent_logs)
        } catch {}
      })
    } catch {}
    return () => es?.close()
  }, [])

  const handleAction = async (action: () => Promise<any>, label: string) => {
    setActionLoading(true)
    try {
      await action()
      await loadData()
    } catch (e: any) {
      alert(`${label} failed: ${e.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  const bot = status?.bot
  const isRunning = bot?.running && !bot?.paused
  const isPaused = bot?.paused
  const simMode = status?.simulation_mode ?? true

  const airdropScores = airdrop?.scores || { diversity: 0, volume: 0, profitability: 0, liquidity: 0 }
  const airdropMetrics = airdrop?.metrics || {}

  // P&L calculation from trades
  const totalPnl = trades.reduce((sum: number, t: any) => sum + (t.pnl || 0), 0)
  const winRate = trades.length > 0
    ? (trades.filter((t: any) => t.pnl > 0).length / trades.length * 100)
    : 0

  return (
    <div className="min-h-screen bg-poly-dark text-poly-text">
      {/* Header */}
      <header className="border-b border-poly-border bg-poly-card/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎯</span>
            <div>
              <h1 className="text-base font-bold text-poly-text">Polymarket Trading Bot</h1>
              <p className="text-xs text-poly-muted">Multi-strategy · Airdrop Optimized</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {simMode && (
              <span className="badge-yellow text-xs">SIM MODE</span>
            )}
            <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-400 animate-pulse' : isPaused ? 'bg-yellow-400' : 'bg-red-400'}`} />
            <span className="text-xs text-poly-muted">
              {isRunning ? 'Running' : isPaused ? 'Paused' : 'Stopped'}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {error && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-800 rounded-lg text-red-400 text-sm">
            ⚠️ API connection issue: {error}. Backend may not be running yet.
          </div>
        )}

        {/* Bot Controls */}
        <div className="flex items-center gap-2 mb-6 flex-wrap">
          {!isRunning && !isPaused && (
            <button
              onClick={() => handleAction(botStart, 'Start')}
              disabled={actionLoading}
              className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              ▶ Start Bot
            </button>
          )}
          {isRunning && (
            <button
              onClick={() => handleAction(botPause, 'Pause')}
              disabled={actionLoading}
              className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              ⏸ Pause
            </button>
          )}
          {(isRunning || isPaused) && (
            <button
              onClick={() => handleAction(botStop, 'Stop')}
              disabled={actionLoading}
              className="px-4 py-2 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              ⏹ Stop
            </button>
          )}
          <button
            onClick={() => handleAction(runCycle, 'Cycle')}
            disabled={actionLoading}
            className="px-4 py-2 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            ⚡ Run Cycle
          </button>
          <button
            onClick={() => handleAction(scanMarkets, 'Scan')}
            disabled={actionLoading}
            className="px-4 py-2 bg-poly-card hover:bg-poly-border disabled:opacity-50 text-poly-text text-sm font-medium rounded-lg border border-poly-border transition-colors"
          >
            🔍 Scan Markets
          </button>
          <span className="text-xs text-poly-muted ml-auto">
            Cycle #{bot?.cycle_count || 0} · {bot?.markets_scanned || 0} markets
          </span>
        </div>

        {/* Top Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
          <StatCard
            label="Total P&L"
            value={`$${totalPnl.toFixed(2)}`}
            color={totalPnl >= 0 ? 'green' : 'red'}
            sub="Simulated"
          />
          <StatCard
            label="Win Rate"
            value={`${winRate.toFixed(1)}%`}
            color={winRate >= 55 ? 'green' : winRate >= 40 ? 'yellow' : 'red'}
            sub={`${trades.length} trades`}
          />
          <StatCard
            label="Total Volume"
            value={`$${(airdropMetrics.total_volume || 0).toFixed(0)}`}
            color="blue"
            sub="USDC traded"
          />
          <StatCard
            label="Markets Traded"
            value={airdropMetrics.markets_traded || 0}
            color="blue"
            sub={`Target: ${airdrop?.targets?.markets_target || 50}`}
          />
          <StatCard
            label="Open Positions"
            value={bot?.risk?.open_positions || 0}
            sub={`Max: ${bot?.risk?.max_positions || 10}`}
          />
          <StatCard
            label="Daily P&L"
            value={`$${(bot?.risk?.daily_pnl || 0).toFixed(2)}`}
            color={(bot?.risk?.daily_pnl || 0) >= 0 ? 'green' : 'red'}
            sub={`Limit: $${bot?.risk?.daily_loss_limit || 100}`}
          />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-4 border-b border-poly-border">
          {(['overview', 'markets', 'trades'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-poly-muted hover:text-poly-text'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Airdrop Meter */}
            <div>
              <AirdropMeter scores={airdropScores} />
            </div>

            {/* Strategy Performance */}
            <div className="card">
              <h3 className="text-sm font-semibold text-poly-text mb-3">Strategy Performance</h3>
              <div className="flex flex-col gap-3">
                {bot?.strategies && Object.entries(bot.strategies).map(([name, stats]: [string, any]) => (
                  <div key={name} className="flex items-center justify-between">
                    <span className="text-xs text-poly-muted capitalize">{name.replace('_', ' ')}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-poly-text">
                        {stats.signals_generated || stats.orders_placed || 0} signals
                      </span>
                      <span className={`badge-${name === 'arbitrage' ? 'green' : name === 'market_maker' ? 'blue' : 'yellow'}`}>
                        {name === 'arbitrage' ? 'ARB' : name === 'market_maker' ? 'MM' : 'MOM'}
                      </span>
                    </div>
                  </div>
                ))}
                {!bot?.strategies && (
                  <span className="text-xs text-poly-muted">Start the bot to see strategy stats</span>
                )}
              </div>
            </div>

            {/* Risk Dashboard */}
            <div className="card">
              <h3 className="text-sm font-semibold text-poly-text mb-3">Risk Dashboard</h3>
              <div className="flex flex-col gap-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-poly-muted">Daily P&L</span>
                  <span className={`font-medium ${(bot?.risk?.daily_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${(bot?.risk?.daily_pnl || 0).toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-poly-muted">Loss Limit</span>
                  <span className="text-poly-text">${bot?.risk?.daily_loss_limit || 100}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-poly-muted">Open Positions</span>
                  <span className="text-poly-text">{bot?.risk?.open_positions || 0} / {bot?.risk?.max_positions || 10}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-poly-muted">Total Exposure</span>
                  <span className="text-poly-text">${(bot?.risk?.total_exposure || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-poly-muted">Fill Rate</span>
                  <span className="text-poly-text">{(bot?.executor?.fill_rate || 0).toFixed(1)}%</span>
                </div>
              </div>
            </div>

            {/* Log Feed — full width */}
            <div className="lg:col-span-3">
              <LogFeed logs={logs} />
            </div>
          </div>
        )}

        {/* Markets Tab */}
        {activeTab === 'markets' && (
          <MarketList markets={markets} />
        )}

        {/* Trades Tab */}
        {activeTab === 'trades' && (
          <TradeTable trades={trades} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-poly-border mt-8 py-4 text-center text-xs text-poly-muted">
        Polymarket Trading Bot · Simulation Mode · Not financial advice ·{' '}
        <a href="/docs" className="text-blue-400 hover:underline" target="_blank">API Docs</a>
      </footer>
    </div>
  )
}
