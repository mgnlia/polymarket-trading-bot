import {
  getMockStatus,
  getMockTrades,
  getMockAirdrop,
  getMockMarkets,
  getMockLogs,
} from './mock'

const BASE = process.env.NEXT_PUBLIC_API_URL || ''

// Whether we've confirmed the backend is unreachable
let backendDown = false
let lastBackendCheck = 0
const BACKEND_RETRY_MS = 30_000 // retry every 30s

async function apiFetch(path: string, opts?: RequestInit) {
  // If no API URL configured, go straight to mock
  if (!BASE) {
    backendDown = true
  }

  // If backend was down, check if we should retry
  if (backendDown && Date.now() - lastBackendCheck < BACKEND_RETRY_MS) {
    throw new Error('backend_unavailable')
  }

  try {
    const res = await fetch(`${BASE}${path}`, {
      ...opts,
      signal: AbortSignal.timeout(5000),
      headers: { 'Content-Type': 'application/json', ...(opts?.headers || {}) },
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`${res.status}: ${text}`)
    }
    backendDown = false
    return res.json()
  } catch (e: any) {
    if (e.message !== 'backend_unavailable') {
      backendDown = true
      lastBackendCheck = Date.now()
    }
    throw new Error('backend_unavailable')
  }
}

// Wrapper that falls back to mock data on backend failure
async function withMock<T>(fetcher: () => Promise<T>, mockFn: () => T): Promise<T> {
  try {
    return await fetcher()
  } catch {
    return mockFn()
  }
}

export const fetchStatus = () =>
  withMock(() => apiFetch('/status'), getMockStatus)

export const fetchTrades = (limit = 50) =>
  withMock(() => apiFetch(`/trades?limit=${limit}`), () => getMockTrades(limit))

export const fetchAirdrop = () =>
  withMock(() => apiFetch('/airdrop'), getMockAirdrop)

export const fetchMarkets = (limit = 30) =>
  withMock(() => apiFetch(`/markets?limit=${limit}`), () => getMockMarkets())

export const fetchLogs = (limit = 40) =>
  withMock(() => apiFetch(`/logs?limit=${limit}`), () => getMockLogs(limit))

export const botStart = () =>
  withMock(() => apiFetch('/bot/start', { method: 'POST' }), () => ({ ok: true, message: 'Bot started (simulation)' }))

export const botStop = () =>
  withMock(() => apiFetch('/bot/stop', { method: 'POST' }), () => ({ ok: true, message: 'Bot stopped (simulation)' }))

export const botPause = () =>
  withMock(() => apiFetch('/bot/pause', { method: 'POST' }), () => ({ ok: true, paused: true }))

export const runCycle = () =>
  withMock(() => apiFetch('/bot/cycle', { method: 'POST' }), () => ({ ok: true, message: 'Cycle complete (simulation)', trades: 3 }))

export const scanMarkets = () =>
  withMock(() => apiFetch('/bot/scan', { method: 'POST' }), () => ({ ok: true, markets_found: 15 }))

export const getSSEUrl = () => BASE ? `${BASE}/stream` : ''

export const isSimulationMode = () => backendDown || !BASE
