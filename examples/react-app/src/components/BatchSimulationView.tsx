import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Play, RotateCcw, TrendingUp, Users, DollarSign, Plus, Trash2 } from 'lucide-react'
import { KlineChart } from '@/components/KlineChart'
import { tradesToCandles, getTimeframeMs, type Trade } from '@/utils/candleUtils'

interface AgentConfigInput {
  id: string
  agent_type: 'MarketMaker' | 'NoiseTrader' | 'InformedTrader' | 'Taker'
  count: number
  config: Record<string, number>
}

interface SimulationResult {
  trades: Array<{ timestamp: number; price: number; size: number }>
  orderbook_states: any[]
  agent_stats: Array<{ agent_id: string; type: string; trades: number }>
  final_price: number
  total_trades: number
}

export function BatchSimulationView() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SimulationResult | null>(null)
  const [selectedTimeframe, setSelectedTimeframe] = useState('1m')
  const [agents, setAgents] = useState<AgentConfigInput[]>([])

  const addAgent = (type: 'MarketMaker' | 'NoiseTrader' | 'InformedTrader' | 'Taker') => {
    const defaultConfig: Record<string, any> = {}
    
    if (type === 'MarketMaker') {
      defaultConfig.spread = 0.01
      defaultConfig.order_size = 1.0
      defaultConfig.max_position = 10.0
    } else if (type === 'NoiseTrader') {
      defaultConfig.trade_probability = 0.1
      defaultConfig.max_size = 5.0
    } else if (type === 'InformedTrader') {
      defaultConfig.bias_probability = 0.3
      defaultConfig.bias_strength = 0.02
      defaultConfig.order_size = 2.0
    } else if (type === 'Taker') {
      defaultConfig.trade_probability = 0.15
      defaultConfig.price_deviation = 0.01
      defaultConfig.min_size = 0.5
      defaultConfig.max_size = 3.0
    }

    const newAgent: AgentConfigInput = {
      id: `${type}_${Date.now()}`,
      agent_type: type,
      count: 1,
      config: defaultConfig
    }
    setAgents([...agents, newAgent])
  }

  const removeAgent = (id: string) => {
    setAgents(agents.filter(a => a.id !== id))
  }

  const updateAgent = (id: string, field: keyof AgentConfigInput, value: string | number | Record<string, number>) => {
    const updated = agents.map(agent => {
      if (agent.id !== id) return agent
      
      if (field === 'config' && typeof value === 'object') {
        return { ...agent, config: { ...agent.config, ...value } }
      } else {
        return { ...agent, [field]: value }
      }
    })
    setAgents(updated)
  }

  const [progress, setProgress] = useState({ progress: 0, trades: 0, current_price: 50000 })
  const [streamingTrades, setStreamingTrades] = useState<Array<{ timestamp: number; price: number; size: number }>>([])

  const runSimulation = async () => {
    setLoading(true)
    setResult(null)
    setStreamingTrades([])
    setProgress({ progress: 0, trades: 0, current_price: 50000 })

    try {
      // Format agents for API
      const apiAgents = agents.map(agent => ({
        type: agent.agent_type,
        count: agent.count,
        params: agent.config
      }))

      const response = await fetch('http://localhost:5000/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agents: apiAgents,
          duration_seconds: 60,
          initial_price: 50000
        })
      })

      if (!response.body) {
        throw new Error('No response body')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.trim()) continue

          try {
            const data = JSON.parse(line)
            
            if (data.type === 'progress') {
              setProgress({
                progress: data.progress,
                trades: data.trades,
                current_price: data.current_price
              })
              
              // Update streaming trades
              if (data.latest_trades && data.latest_trades.length > 0) {
                setStreamingTrades(prev => {
                  const newTrades = data.latest_trades.map((t: any) => ({
                    timestamp: t.timestamp,
                    price: t.price,
                    size: t.size
                  }))
                  // Keep only unique trades
                  const existing = new Set(prev.map(t => t.timestamp))
                  const unique = newTrades.filter((t: any) => !existing.has(t.timestamp))
                  return [...prev, ...unique]
                })
              }
            } else if (data.type === 'final') {
              setResult({
                trades: data.trades,
                orderbook_states: data.orderbook_states || [],
                agent_stats: data.agent_stats || [],
                final_price: data.final_price,
                total_trades: data.total_trades
              })
              setLoading(false)
            }
          } catch (e) {
            console.error('Error parsing stream data:', e, line)
            continue
          }
        }
      }
    } catch (error) {
      console.error('Simulation error:', error)
      setLoading(false)
    }
  }

  // Generate candles from trades (use streaming trades if available)
  const candles = (() => {
    const tradesToUse = result 
      ? result.trades 
      : streamingTrades.length > 0 
        ? streamingTrades 
        : []
    
    if (tradesToUse.length === 0) return []
    
    const timeframeMs = getTimeframeMs(selectedTimeframe)
    const tradeData: Trade[] = tradesToUse.map(t => ({
      timestamp: t.timestamp * 1000,
      price: t.price,
      size: t.size
    }))
    return tradesToCandles(tradeData, timeframeMs)
  })()

  return (
    <div className="space-y-6">
      {/* Quick Add Agents */}
      <Card>
        <CardHeader>
          <CardTitle>Add Agent Types</CardTitle>
          <CardDescription>Quickly add agent configurations</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <Button variant="outline" onClick={() => addAgent('MarketMaker')} className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              Market Maker
            </Button>
            <Button variant="outline" onClick={() => addAgent('NoiseTrader')} className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              Noise Trader
            </Button>
            <Button variant="outline" onClick={() => addAgent('InformedTrader')} className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              Informed
            </Button>
            <Button variant="outline" onClick={() => addAgent('Taker')} className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              Taker
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Agent Configuration Cards */}
      {agents.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center text-muted-foreground">
            No agents configured. Click above to add agent types.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {agents.map((agent, index) => (
            <Card key={agent.id} className="p-4">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-primary"></div>
                  <div>
                    <Label className="text-base font-semibold">
                      {agent.agent_type} #{index + 1}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {agent.count} agent{agent.count !== 1 ? 's' : ''}
                    </p>
                  </div>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => removeAgent(agent.id)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <Label>Count</Label>
                  <Input
                    type="number"
                    min="1"
                    value={agent.count}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'count', parseInt(e.target.value) || 1)}
                    placeholder="Number of agents"
                  />
                </div>
              </div>

              {/* Agent-specific config */}
              {agent.agent_type === 'MarketMaker' && (
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <Label className="text-xs">Spread</Label>
                    <Input
                      placeholder="0.01"
                      type="number"
                      step="0.001"
                      value={agent.config.spread || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { spread: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Order Size</Label>
                    <Input
                      placeholder="1.0"
                      type="number"
                      step="0.1"
                      value={agent.config.order_size || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { order_size: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Max Position</Label>
                    <Input
                      placeholder="10.0"
                      type="number"
                      step="0.1"
                      value={agent.config.max_position || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { max_position: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                </div>
              )}
              
              {agent.agent_type === 'NoiseTrader' && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-xs">Trade Probability</Label>
                    <Input
                      placeholder="0.1"
                      type="number"
                      step="0.01"
                      value={agent.config.trade_probability || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { trade_probability: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Max Size</Label>
                    <Input
                      placeholder="5.0"
                      type="number"
                      step="0.1"
                      value={agent.config.max_size || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { max_size: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                </div>
              )}

              {agent.agent_type === 'InformedTrader' && (
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <Label className="text-xs">Bias Probability</Label>
                    <Input
                      placeholder="0.3"
                      type="number"
                      step="0.01"
                      value={agent.config.bias_probability || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { bias_probability: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Bias Strength</Label>
                    <Input
                      placeholder="0.02"
                      type="number"
                      step="0.001"
                      value={agent.config.bias_strength || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { bias_strength: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Order Size</Label>
                    <Input
                      placeholder="2.0"
                      type="number"
                      step="0.1"
                      value={agent.config.order_size || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { order_size: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                </div>
              )}

              {agent.agent_type === 'Taker' && (
                <>
                  <div className="grid grid-cols-2 gap-2 mb-2">
                    <div>
                      <Label className="text-xs">Trade Probability</Label>
                      <Input
                        placeholder="0.15"
                        type="number"
                        step="0.01"
                        value={agent.config.trade_probability || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { trade_probability: parseFloat(e.target.value) || 0 })}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Price Deviation</Label>
                      <Input
                        placeholder="0.01"
                        type="number"
                        step="0.001"
                        value={agent.config.price_deviation || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { price_deviation: parseFloat(e.target.value) || 0 })}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-xs">Min Size</Label>
                      <Input
                        placeholder="0.5"
                        type="number"
                        step="0.1"
                        value={agent.config.min_size || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { min_size: parseFloat(e.target.value) || 0 })}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Max Size</Label>
                      <Input
                        placeholder="3.0"
                        type="number"
                        step="0.1"
                        value={agent.config.max_size || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'config', { max_size: parseFloat(e.target.value) || 0 })}
                      />
                    </div>
                  </div>
                </>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Controls */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-2">
            <Button 
              onClick={runSimulation} 
              disabled={loading || agents.length === 0}
              className="flex-1"
            >
              <Play className="h-4 w-4 mr-2" />
              {loading ? 'Running...' : 'Run Batch Simulation'}
            </Button>
            {result && (
              <Button variant="outline" onClick={() => setResult(null)}>
                <RotateCcw className="h-4 w-4 mr-2" />
                Clear Results
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Progress Indicator */}
      {loading && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Running simulation...</span>
                <span>{Math.round(progress.progress)}%</span>
              </div>
              <div className="w-full bg-secondary rounded-full h-2">
                <div 
                  className="bg-primary h-2 rounded-full transition-all"
                  style={{ width: `${progress.progress}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Trades: {progress.trades}</span>
                <span>Price: ${progress.current_price.toFixed(2)}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Chart - Show immediately when streaming starts */}
      {(loading || result || streamingTrades.length > 0) && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Trades</p>
                    <p className="text-2xl font-bold">
                      {result ? result.total_trades : streamingTrades.length}
                    </p>
                  </div>
                  <Users className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      {result ? 'Final Price' : 'Current Price'}
                    </p>
                    <p className="text-2xl font-bold">
                      ${result?.final_price?.toFixed(2) || progress.current_price.toFixed(2)}
                    </p>
                  </div>
                  <DollarSign className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Agents</p>
                    <p className="text-2xl font-bold">
                      {result?.agent_stats.length || agents.reduce((sum, a) => sum + a.count, 0)}
                    </p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Chart */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>
                  {loading ? 'Live Chart (Streaming...)' : 'Price Chart'}
                </CardTitle>
                <div className="flex gap-2">
                  {['1s', '3s', '5s', '15s', '30s', '1m', '5m'].map(tf => (
                    <Button
                      key={tf}
                      size="sm"
                      variant={selectedTimeframe === tf ? 'default' : 'outline'}
                      onClick={() => setSelectedTimeframe(tf)}
                    >
                      {tf}
                    </Button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {candles.length === 0 ? (
                <div className="h-96 flex items-center justify-center text-muted-foreground">
                  {loading ? 'Waiting for trades...' : 'No data to display'}
                </div>
              ) : (
                <div className="h-96">
                  <KlineChart candleData={candles} />
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
