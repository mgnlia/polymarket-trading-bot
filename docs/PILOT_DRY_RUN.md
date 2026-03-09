# Pilot Dry-Run Checklist

This checklist validates the Polymarket bot in **simulation mode only**.

## Prerequisites
- Docker Desktop or Docker Engine
- No live wallet, API key, or exchange credentials

## Start locally

```bash
cp .env.example .env

docker compose up
```

Frontend:
- http://localhost:3000

Backend:
- http://localhost:8000
- Docs: http://localhost:8000/docs

## Operator flow

### 1. Verify backend health
```bash
curl http://localhost:8000/health
```

### 2. Verify status surface
```bash
curl http://localhost:8000/status | jq
```
Confirm:
- `simulation_mode: true`
- `bot.running: false` initially
- `markets_scanned` is present

### 3. Start the bot
```bash
curl -X POST http://localhost:8000/bot/start \
  -H 'Authorization: Bearer dev-bot-key'
```

### 4. Wait for one or two cycles
Observe:
- `cycle_count` increases
- `total_trades` begins to increase
- `executor.orders_placed` and `executor.fill_rate` are non-zero

### 5. Inspect trades and airdrop score
```bash
curl http://localhost:8000/trades -H 'Authorization: Bearer dev-bot-key' | jq
curl http://localhost:8000/airdrop -H 'Authorization: Bearer dev-bot-key' | jq
```

### 6. Pause and stop controls
```bash
curl -X POST http://localhost:8000/bot/pause -H 'Authorization: Bearer dev-bot-key'
curl -X POST http://localhost:8000/bot/stop -H 'Authorization: Bearer dev-bot-key'
```

## Success criteria

A dry-run is considered successful when:
- The API stays healthy.
- The dashboard loads locally.
- Bot status updates over time.
- Trades are created in simulation.
- Airdrop metrics populate.
- No live secrets were required.

## Review-only blocker

If the reviewer requests:
- production frontend URL,
- production backend URL, or
- live credential validation,

that is **outside** this task and requires a follow-up approval/secrets step.
