const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch(path: string, opts?: RequestInit) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts?.headers || {}) },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

export const fetchStatus = () => apiFetch('/status')
export const fetchTrades = (limit = 50) => apiFetch(`/trades?limit=${limit}`)
export const fetchAirdrop = () => apiFetch('/airdrop')
export const fetchMarkets = (limit = 30) => apiFetch(`/markets?limit=${limit}`)
export const fetchLogs = (limit = 40) => apiFetch(`/logs?limit=${limit}`)

export const botStart = () => apiFetch('/bot/start', { method: 'POST' })
export const botStop = () => apiFetch('/bot/stop', { method: 'POST' })
export const botPause = () => apiFetch('/bot/pause', { method: 'POST' })
export const runCycle = () => apiFetch('/bot/cycle', { method: 'POST' })
export const scanMarkets = () => apiFetch('/bot/scan', { method: 'POST' })

export const getSSEUrl = () => `${BASE}/stream`
