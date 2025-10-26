import { useState, useEffect, useCallback } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { Button } from '@/components/ui/button'
import { Moon, Sun, Target, BarChart, Settings, FileText, LogOut } from 'lucide-react'
import { ChartView } from '@/components/ChartView'
import { AgentControlPanel } from '@/components/AgentControlPanel'
import { LogsView } from '@/components/LogsView'
import type { MarketData, OrderbookData, AgentConfig, CandleData } from '@/types'

interface LogEntry {
  timestamp: string
  message: string
  type: 'info' | 'success' | 'error' | 'warning'
}

export default function App() {
  const [darkMode, setDarkMode] = useState(true)
  const [activeTab, setActiveTab] = useState('chart')
  
  const [marketData, setMarketData] = useState<MarketData>({
    lastPrice: null,
    spread: null,
    volume: 0,
    tradeCount: 0,
    timestamp: 0,
  })
  
  const [orderbook, setOrderbook] = useState<OrderbookData>({
    bids: [],
    asks: [],
    spread: 0,
    midPrice: 0,
    timestamp: 0,
  })
  
  const [agentConfigs, setAgentConfigs] = useState<AgentConfig[]>([])
  const [messageCount, setMessageCount] = useState(0)
  const [logs, setLogs] = useState<LogEntry[]>([])
  // Store candles by timeframe
  const [candlesByTimeframe, setCandlesByTimeframe] = useState<Record<string, CandleData[]>>({})
  const [currentCandleByTimeframe, setCurrentCandleByTimeframe] = useState<Record<string, CandleData | null>>({})
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1m')

  const { isConnected, connect, disconnect, send, addMessageHandler } = useWebSocket('ws://localhost:8765')

  // Initialize dark mode
  useEffect(() => {
    document.documentElement.classList.add('dark')
    const saved = localStorage.getItem('darkMode')
    if (saved === 'false') {
      setDarkMode(false)
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    }
  }, [])

  // Define addLog before using it
  const addLog = useCallback((message: string, type: LogEntry['type'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev.slice(-49), { timestamp, message, type }])
  }, [])

  const toggleDarkMode = () => {
    const newDark = !darkMode
    setDarkMode(newDark)
    localStorage.setItem('darkMode', newDark.toString())
    console.log('Toggling to:', newDark ? 'dark' : 'light')
    
    if (newDark) {
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    }
    
    // Force a style recalculation
    document.body.style.display = 'none'
    document.body.offsetHeight // trigger reflow
    document.body.style.display = ''
  }

  // Setup message handlers
  useEffect(() => {
    return addMessageHandler((message) => {
      setMessageCount(prev => prev + 1)

      if (message.type === 'market_data') {
        setMarketData(prev => ({
          lastPrice: message.last_price,
          spread: message.ask_price && message.bid_price 
            ? message.ask_price - message.bid_price 
            : prev.spread,
          volume: message.volume_24h || 0,
          tradeCount: message.trade_count || 0,
          timestamp: message.timestamp,
        }))
      } else if (message.e === 'kline') {
        // Handle candle data
        const k = message.k
        const candle: CandleData = {
          timestamp: k.t,
          open: k.o,
          high: k.h,
          low: k.l,
          close: k.c,
          volume: k.v
        }
        
        const timeframe = k.i // e.g., '1m', '5m', etc.

        if (k.x) {
          // Closed candle - add to history for this timeframe
          setCandlesByTimeframe(prev => ({
            ...prev,
            [timeframe]: [...(prev[timeframe] || []).slice(-199), candle]
          }))
          setCurrentCandleByTimeframe(prev => ({
            ...prev,
            [timeframe]: null
          }))
        } else {
          // Live candle - update current for this timeframe
          setCurrentCandleByTimeframe(prev => ({
            ...prev,
            [timeframe]: candle
          }))
        }
      } else if (message.type === 'orderbook') {
        setOrderbook({
          bids: message.bids.map(([price, size]) => ({ price, size })),
          asks: message.asks.map(([price, size]) => ({ price, size })),
          spread: message.spread || 0,
          midPrice: message.mid_price || 0,
          timestamp: message.timestamp,
        })
      } else if (message.type === 'agent_configs') {
        setAgentConfigs(message.configs || [])
      } else if (message.type === 'agent_response') {
        // Handle agent management responses
        const { action, agent_id, success } = message
        if (success) {
          addLog(`✅ Agent ${action}: ${agent_id}`, 'success')
        } else {
          addLog(`❌ Failed to ${action} agent: ${agent_id}`, 'error')
        }
      }
    })
  }, [addMessageHandler, addLog])

  // Add connection status to logs
  useEffect(() => {
    if (isConnected) {
      addLog('✅ Connected to WebSocket server', 'success')
    }
  }, [isConnected, addLog])

  const handleConnect = () => {
    console.log('Connecting to WebSocket...')
    addLog('Connecting to WebSocket server at ws://localhost:8765...', 'info')
    connect()
  }

  const handleDisconnect = () => {
    disconnect()
    addLog('Disconnected from WebSocket server', 'warning')
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header with Navigation */}
      <header className="border-b border-border bg-card sticky top-0 z-50">
        <div className="container mx-auto px-4">
          {/* Top Row - Title and Actions */}
          <div className="flex justify-between items-center py-3">
            <div className="flex items-center gap-2">
              <Target className="h-6 w-6" />
              <h1 className="text-xl font-bold">Market Simulation</h1>
            </div>
            <div className="flex gap-2">
              <Button 
                variant={isConnected ? 'default' : 'secondary'} 
                onClick={isConnected ? handleDisconnect : handleConnect}
                size="sm"
              >
                {isConnected ? '🟢 Connected' : 'Disconnected'}
              </Button>
              <Button variant="outline" size="icon" onClick={toggleDarkMode}>
                {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex gap-1 border-t border-border">
            <button
              onClick={() => setActiveTab('chart')}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'chart'
                  ? 'border-b-2 border-primary text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <BarChart className="h-4 w-4" />
                Chart
              </div>
            </button>
            <button
              onClick={() => setActiveTab('agents')}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'agents'
                  ? 'border-b-2 border-primary text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <Settings className="h-4 w-4" />
                Agents
              </div>
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'logs'
                  ? 'border-b-2 border-primary text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <FileText className="h-4 w-4" />
                Logs
      </div>
        </button>
          </div>
        </div>
      </header>

      {/* Content Area */}
      <div className="container mx-auto px-4 py-6">
        {activeTab === 'chart' && (
          <ChartView 
            marketData={marketData} 
            orderbook={orderbook}
            candleData={candlesByTimeframe[selectedTimeframe] || []}
            currentCandle={currentCandleByTimeframe[selectedTimeframe] || undefined}
            selectedTimeframe={selectedTimeframe}
            onTimeframeChange={setSelectedTimeframe}
          />
        )}
        {activeTab === 'agents' && (
          <AgentControlPanel 
            agentConfigs={agentConfigs}
            onAddAgent={(type, config) => {
              addLog(`Creating new ${type} agent...`, 'info')
              send({
                type: 'agent_command',
                action: 'create',
                agent_type: type,
                config: config
              })
            }}
            onDeleteAgent={(agentId) => {
              addLog(`Deleting agent ${agentId}...`, 'warning')
              send({
                type: 'agent_command',
                action: 'delete',
                agent_id: agentId
              })
            }}
            onUpdateAgent={(agentId, config) => {
              addLog(`Updating agent ${agentId}...`, 'info')
              send({
                type: 'agent_command',
                action: 'update',
                agent_id: agentId,
                config: config
              })
            }}
          />
        )}
        {activeTab === 'logs' && <LogsView logs={logs} />}
      </div>
    </div>
  )
}
