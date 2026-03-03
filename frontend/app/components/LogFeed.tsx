'use client'
import { useEffect, useRef } from 'react'

interface LogEntry {
  timestamp: string
  level: string
  message: string
  strategy?: string
}

const levelColor: Record<string, string> = {
  INFO: 'text-blue-400',
  WARN: 'text-yellow-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
  SUCCESS: 'text-green-400',
  TRADE: 'text-purple-400',
  SIGNAL: 'text-cyan-400',
}

export default function LogFeed({ logs }: { logs: LogEntry[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-poly-text mb-3">Live Log Feed</h3>
      <div className="h-48 overflow-y-auto font-mono text-xs bg-black/30 rounded-lg p-3 space-y-0.5">
        {logs.length === 0 ? (
          <span className="text-poly-muted">Waiting for bot activity…</span>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-poly-muted shrink-0">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className={`shrink-0 w-14 ${levelColor[log.level] || 'text-poly-muted'}`}>
                [{log.level}]
              </span>
              {log.strategy && (
                <span className="text-poly-muted shrink-0">[{log.strategy}]</span>
              )}
              <span className="text-poly-text">{log.message}</span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
