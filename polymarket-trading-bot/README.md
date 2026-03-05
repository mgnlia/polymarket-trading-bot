# 🎯 Polymarket Trading Bot

Multi-strategy prediction market trading bot with airdrop optimization. Trades on [Polymarket](https://polymarket.com) using three strategies:

1. **Arbitrage** — YES+NO mispricing detection
2. **Market Making** — two-sided limit orders capturing spread  
3. **Momentum** — sentiment/news-driven directional bets

Built with `py-clob-client` (official Polymarket SDK), FastAPI backend, and Next.js dashboard.

## 🚀 Live Demo

- **Frontend Dashboard**: [Vercel URL]
- **Backend API**: [Railway URL]
- **API Docs**: [Railway URL]/docs

## ✨ Features

- **3 trading strategies** running in parallel
- **Simulation mode** — works without wallet keys for demo
- **Airdrop optimizer** — tracks diversity, volume, liquidity scores
- **Real-time dashboard** — SSE-powered live updates
- **Risk management** — position limits, daily loss limits
- **60+ markets** scanned per cycle

## 🏗 Architecture

```
polymarket-trading-bot/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── main.py            # API routes + SSE
│   │   ├── bot_engine.py      # Main orchestrator
│   │   ├── strategies/
│   │   │   ├── arbitrage.py   # YES+NO mispricing
│   │   │   ├── market_maker.py # Two-sided quotes
│   │   │   └── momentum.py    # Sentiment signals
│   │   ├── executor.py        # Order execution (sim/live)
│   │   ├── risk.py            # Risk management
│   │   ├── airdrop.py         # Airdrop score tracking
│   │   └── market_scanner.py  # Gamma API integration
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                   # Next.js 14 dashboard
│   ├── app/
│   │   ├── page.tsx           # Main dashboard
│   │   ├── components/
│   │   │   ├── StatCard.tsx
│   │   │   ├── AirdropMeter.tsx
│   │   │   ├── TradeTable.tsx
│   │   │   ├── LogFeed.tsx
│   │   │   └── MarketList.tsx
│   │   └── lib/api.ts
│   └── package.json
├── railway.json
└── vercel.json
```

## 🔧 Local Development

### Backend
```bash
cd backend
pip install uv
uv pip install --system -e .
cp ../.env.example .env
python main.py
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# Dashboard at http://localhost:3000
```

## 🌐 Deployment

### Backend (Railway)
```bash
railway login
railway up
```

### Frontend (Vercel)
```bash
vercel --prod
# Set NEXT_PUBLIC_API_URL to your Railway backend URL
```

## 💡 Strategies

### Arbitrage
Scans for markets where `YES_price + NO_price < 0.97`. Buying both sides locks in ~3%+ profit.

### Market Making
Posts limit orders on both sides of the spread. Earns the spread when both fill. High limit order ratio boosts airdrop score.

### Momentum
Uses keyword sentiment + price momentum to take directional bets. Only trades >60% confidence signals.

## 🎁 Airdrop Optimization

The bot optimizes four airdrop factors:
- **Diversity** (30%): Trade 50+ unique markets
- **Volume** (30%): Maximize USDC traded
- **Profitability** (20%): Maintain positive win rate
- **Liquidity** (20%): Use limit orders > market orders

## ⚠️ Disclaimer

This is for educational/research purposes. Prediction market trading involves risk. Always use simulation mode first. Not financial advice.
