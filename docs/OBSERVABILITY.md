# Observability Runbook

This repository is designed to support **simulation-first pilot dry-runs** before any live trading credentials are introduced.

## Goals

The dry-run pack should let an operator answer five questions quickly:

1. Is the API alive?
2. Is the bot running, paused, or stopped?
3. Are strategies producing fills/trades in simulation?
4. Are risk controls halting the system when they should?
5. Is the airdrop score improving across diversity, volume, profitability, and liquidity?

## Primary Signals

### 1) Health
- Endpoint: `GET /health`
- Success criteria: HTTP 200 and a recent timestamp

Example:
```bash
curl http://localhost:8000/health
```

### 2) Bot status
- Endpoint: `GET /status`
- Use this to confirm:
  - `simulation_mode`
  - `running`
  - `paused`
  - `cycle_count`
  - `markets_scanned`
  - `total_trades`
  - `risk`
  - `airdrop_score`
  - `executor.fill_rate`

Example:
```bash
curl http://localhost:8000/status | jq
```

### 3) Live event stream
- Endpoint: `GET /stream`
- Event type: `status`
- Payload includes latest bot status plus recent logs.

Example:
```bash
curl -N http://localhost:8000/stream
```

### 4) Protected operator endpoints
If `BOT_API_KEY` is set, the following require either:
- `Authorization: Bearer <BOT_API_KEY>`
- `X-Bot-Api-Key: <BOT_API_KEY>`

Protected endpoints:
- `POST /bot/start`
- `POST /bot/stop`
- `POST /bot/pause`
- `POST /bot/cycle`
- `POST /bot/scan`
- `GET /trades`
- `GET /airdrop`
- `GET /logs`

Example:
```bash
curl -X POST http://localhost:8000/bot/start \
  -H 'Authorization: Bearer dev-bot-key'
```

## What to Watch During a Dry-Run

### Bot loop health
Healthy simulation behavior usually looks like:
- `cycle_count` increasing every cycle interval
- `markets_scanned` staying non-zero
- `executor.orders_placed` increasing over time
- `executor.fill_rate` > 0 in simulation
- `total_trades` increasing after manual cycles or bot start

### Risk controls
Watch `status.bot.risk` for:
- `open_positions`
- `total_exposure`
- `daily_pnl`
- `daily_volume`
- `current_drawdown`
- `max_drawdown_seen`
- `halted`
- `halt_reason`

Expected behaviors:
- Oversized orders should be blocked.
- Daily loss breaches should halt trading.
- Drawdown breaches should halt trading.

### Airdrop optimization
Watch `GET /airdrop` for:
- `scores.diversity`
- `scores.volume`
- `scores.profitability`
- `scores.liquidity`
- `scores.overall`
- `tier`
- `recommendations`

Interpretation:
- Low diversity: broaden unique markets traded.
- Low liquidity score: increase limit-order share.
- Low profitability: review momentum thresholds and market selection.

## Suggested Pilot Dashboard Checks

Run these checks in order:

1. `GET /health`
2. `GET /status`
3. Start bot with `POST /bot/start`
4. Wait 1–2 cycles
5. Check `GET /status` again
6. Check `GET /trades`
7. Check `GET /airdrop`
8. Open dashboard and confirm SSE log feed updates

## Frontend Expectations

The Next.js dashboard should show:
- Top stats for P&L, win rate, volume, markets traded, positions, and daily P&L
- Airdrop meter
- Risk dashboard
- Strategy performance summary
- Live log feed
- Market list and trades table

If the backend is unavailable, the frontend intentionally falls back to mock data so the UI remains inspectable.

## Known Pilot Constraints

- Simulation mode is the default safe path.
- No wallet or live CLOB credentials are required for this pack.
- Live deploy URLs are not required to validate dry-run behavior locally.
- Frontend mock fallback can mask backend outages, so always verify `GET /health` separately.

## Minimal Manual Smoke Test

```bash
cp .env.example .env

docker compose up --build

curl http://localhost:8000/health
curl http://localhost:8000/status | jq
curl -X POST http://localhost:8000/bot/start -H 'Authorization: Bearer dev-bot-key'
sleep 20
curl http://localhost:8000/status | jq
curl http://localhost:8000/trades -H 'Authorization: Bearer dev-bot-key' | jq
curl http://localhost:8000/airdrop -H 'Authorization: Bearer dev-bot-key' | jq
```

## Review Handoff Notes

This runbook is intended for **prep/review** environments. If a reviewer wants live deployment URLs or secret-backed live trading validation, that requires a separate approval step and credential injection outside this no-secrets task.
