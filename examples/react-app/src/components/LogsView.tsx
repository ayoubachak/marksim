import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FileText } from 'lucide-react'
import { useState } from 'react'

interface LogEntry {
  timestamp: string
  message: string
  type: 'info' | 'success' | 'error' | 'warning'
}

interface LogsViewProps {
  logs: LogEntry[]
}

export function LogsView({ logs }: LogsViewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Activity Logs
        </CardTitle>
        <CardDescription>Real-time system and connection events</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="max-h-[600px] overflow-y-auto space-y-2 font-mono text-sm">
          {logs.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No logs yet. Connect to start receiving events.</p>
            </div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex gap-2 p-2 rounded border bg-card">
                <span className="text-muted-foreground">[{log.timestamp}]</span>
                <span className={getLogColor(log.type)}>{log.message}</span>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function getLogColor(type: LogEntry['type']): string {
  switch (type) {
    case 'success':
      return 'text-green-600'
    case 'error':
      return 'text-red-600'
    case 'warning':
      return 'text-yellow-600'
    default:
      return 'text-foreground'
  }
}

