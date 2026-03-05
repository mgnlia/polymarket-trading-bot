/**
 * Mock data for simulation mode — used when backend is unavailable.
 * Generates realistic-looking trading data for demo purposes.
 */

let cycleCount = 0
let totalPnl = 0
const startTime = Date.now()

const MARKET_NAMES = [
  'Will Bitcoin exceed $150k by end of 2026?',
  'Will the Fed cut rates in Q3 2026?',
  'Will Trump sign the crypto bill before August?',
  'Will Ethereum ETF AUM exceed $10B?',
  'Will the S&P 500 hit 7000 by December 2026?',
  'Will Kamala Harris run in 2028?',
  'Will Apple release AR glasses in 2026?',
  'Will OpenAI IPO in 2026?',
  'Will the Euro drop below 1.05 USD?',
  'Will there be a US recession in 2026?',
  'Will Solana flip Ethereum by market cap?',
  'Will the UK rejoin the EU single market?',
  'Will SpaceX land on Mars before 2030?',
  'Will Polymarket volume exceed $10B in 2026?',
  'Will AI replace 10% of jobs by 2027?',
]

const STRATEGIES = ['arbitrage', 'market_maker', 'momentum']

function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000
  return x - Math.floor(x)
}

export function getMockStatus() {
  cycleCount++
  const elapsed = (Date.now() - startTime) / 1000
  const mockPnl = Math.sin(elapsed / 30) * 45 + elapsed * 0.08 + 12.5
  
  return {
    ok: true,
    simulation_mode: true,
    bot: {
      running: true,
      paused: false,
      cycle_count: cycleCount + 47,
      markets_scanned: 15,
      last_cycle: new Date().toISOString(),
      strategies: {
        arbitrage: { signals_generated: Math.floor(cycleCount * 0.3 + 8), last_signal: new Date(Date.now() - 45000).toISOString() },
        market_maker: { orders_placed: Math.floor(cycleCount * 1.2 + 23), spread_captured: 0.0089 },
        momentum: { signals_generated: Math.floor(cycleCount * 0.5 + 12), confidence: 0.72 },
      },
      risk: {
        open_positions: 3 + (cycleCount % 4),
        max_positions: 10,
        daily_pnl: mockPnl,
        daily_loss_limit: 100,
        total_exposure: 187.5 + (cycleCount % 50),
      },
      executor: {
        fill_rate: 94.3 - (cycleCount % 5),
        total_orders: 47 + cycleCount,
        filled: 44 + Math.floor(cycleCount * 0.9),
      },
    },
    timestamp: new Date().toISOString(),
  }
}

export function getMockTrades(limit = 50) {
  const trades = []
  const now = Date.now()
  
  for (let i = 0; i < Math.min(limit, 24); i++) {
    const seed = i * 137.5
    const strategy = STRATEGIES[i % 3]
    const market = MARKET_NAMES[i % MARKET_NAMES.length]
    const side = seededRandom(seed) > 0.5 ? 'BUY' : 'SELL'
    const size = Math.round((seededRandom(seed + 1) * 40 + 5) * 100) / 100
    const price = Math.round((seededRandom(seed + 2) * 0.6 + 0.2) * 100) / 100
    const pnl = (seededRandom(seed + 3) - 0.38) * size * 0.15
    const status = i < 20 ? 'FILLED' : i < 22 ? 'PENDING' : 'CANCELLED'
    
    trades.push({
      id: `sim-${1000 + i}`,
      timestamp: new Date(now - i * 180000 - seededRandom(seed + 4) * 60000).toISOString(),
      market: market.substring(0, 45) + (market.length > 45 ? '...' : ''),
      strategy,
      side,
      size,
      price,
      pnl: status === 'FILLED' ? Math.round(pnl * 100) / 100 : 0,
      status,
    })
  }
  
  return {
    trades,
    count: trades.length,
    total_pnl: trades.reduce((s: number, t: any) => s + t.pnl, 0),
  }
}

export function getMockAirdrop() {
  const elapsed = (Date.now() - startTime) / 1000
  const progress = Math.min(elapsed / 300, 0.85) // grows over 5 minutes to 85%
  
  return {
    composite_score: Math.round((0.42 + progress * 0.35) * 100) / 100,
    scores: {
      diversity: Math.round((0.55 + progress * 0.3) * 100) / 100,
      volume: Math.round((0.38 + progress * 0.4) * 100) / 100,
      profitability: Math.round((0.61 + progress * 0.2) * 100) / 100,
      liquidity: Math.round((0.48 + progress * 0.35) * 100) / 100,
    },
    metrics: {
      total_volume: Math.round((1247 + elapsed * 2.3) * 100) / 100,
      markets_traded: Math.min(15, Math.floor(3 + elapsed / 20)),
      unique_categories: 5,
      maker_orders: Math.floor(23 + elapsed / 15),
      taker_orders: Math.floor(8 + elapsed / 40),
    },
    targets: {
      volume_target: 10000,
      markets_target: 50,
      diversity_target: 10,
    },
    recommendation: 'Focus on market making in high-volume prediction markets to maximize maker rebates and airdrop score.',
  }
}

export function getMockMarkets() {
  const markets = MARKET_NAMES.map((name, i) => {
    const seed = i * 73.1
    const yes = Math.round((seededRandom(seed) * 0.7 + 0.15) * 100) / 100
    const volume = Math.round(seededRandom(seed + 1) * 500000 + 10000)
    const spread = Math.round((seededRandom(seed + 2) * 0.04 + 0.005) * 1000) / 1000
    
    return {
      id: `0x${Array.from({length: 8}, (_, j) => Math.floor(seededRandom(seed + j) * 16).toString(16)).join('')}`,
      question: name,
      yes_price: yes,
      no_price: Math.round((1 - yes - spread) * 100) / 100,
      spread,
      volume_24h: volume,
      liquidity: Math.round(volume * (seededRandom(seed + 3) * 0.3 + 0.1)),
      category: ['crypto', 'politics', 'economics', 'tech', 'sports'][i % 5],
      arb_opportunity: seededRandom(seed + 4) > 0.85,
      end_date: new Date(Date.now() + (30 + i * 7) * 86400000).toISOString().split('T')[0],
    }
  })
  
  return { markets, total: markets.length }
}

export function getMockLogs(limit = 40) {
  const now = Date.now()
  const levels = ['INFO', 'INFO', 'INFO', 'INFO', 'DEBUG', 'WARNING']
  const messages = [
    '🔍 Scanning 15 active prediction markets...',
    '📊 Arbitrage: checking YES/NO price discrepancies',
    '💧 Market Maker: placing limit orders on BTC/USD market',
    '📈 Momentum: BTC signal strength 0.72 — above threshold',
    '✅ Order filled: BUY 12.50 YES @ $0.63 (BTC $150k market)',
    '💰 Maker rebate credited: +$0.031 USDC',
    '🎯 Airdrop score updated: 0.74 composite',
    '⚖️ Risk check: 4/10 positions, $187.50 exposure',
    '🔄 Cycle #52 complete — 0 new signals this cycle',
    '📡 Fetching orderbook for Ethereum ETF market',
    '🚫 Skipping market: spread too wide (4.2% > 3% threshold)',
    '✅ Order filled: SELL 8.75 NO @ $0.41 (Fed rate cut)',
    '📊 Daily P&L: +$14.23 (+14.2% of daily limit)',
    '🔍 Found potential arb: 1.2% discrepancy on BTC market',
    '💧 Market Maker: spread captured 0.89% on 3 fills',
  ]
  
  const logs = []
  for (let i = 0; i < Math.min(limit, messages.length); i++) {
    logs.push({
      timestamp: new Date(now - i * 45000 - Math.random() * 20000).toISOString(),
      level: levels[i % levels.length],
      message: messages[i % messages.length],
    })
  }
  
  return { logs, count: logs.length }
}
