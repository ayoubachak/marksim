import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Play, RotateCcw, TrendingUp, Users, DollarSign } from 'lucide-react'
import { KlineChart } from '@/components/KlineChart'
import { tradesToCandles, getTimeframeMs, type Trade } from '@/utils/candleUtils'

interface AgentConfigInput {
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
  const [agents, setAgents] = useState<AgentConfigInput[]>([{
    agent_type: 'NoiseTrader',
    count: 100,
    config: { trade_probability: 0.1, max_size: 1 }
  }])

  const addAgent = () => {
    setAgents([...agents, {
      agent_type: 'NoiseTrader',
      count: 1,
      config: {}
    }])
  }

  const removeAgent = (index: number) => {
    setAgents(agents.filter((_, i) => i !== index))
  }

  const updateAgent = (index: number, field: keyof AgentConfigInput, value: string | number | Record<string, number>) => {
    const updated = [...agents]
    if (field === 'config' && typeof value === 'object') {
      updated[index] = { ...updated[index], config: { ...updated[index].config, ...value } }
    } else {
      updated[index] = { ...updated[index], [field]: value }
    }
    setAgents(updated)
  }

  const runSimulation = async () => {
    setLoading(true)
    setResult(null)

    try {
      const response = await fetch('http://localhost:8000/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agents: agents,
          duration: 60,
          initial_price: 50000
        })
      })

      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error('Simulation error:', error)
    } finally {
      setLoading(false)
    }
  }

  // Generate candles from trades
  const candles = result ? (() => {
    const timeframeMs = getTimeframeMs(selectedTimeframe)
    const trades: Trade[] = result.trades.map(t => ({
      timestamp: t.timestamp * 1000, // Convert to microseconds for candleUtils
      price: t.price,
      size: t.size
    }))
    return tradesToCandles(trades, timeframeMs)
  })() : []

  return (
    <div className="space-y-6">
      {/* Configuration Section */}
      <Card>
        <CardHeader>
          <CardTitle>Agent Configuration</CardTitle>
          <CardDescription>Configure agent types and parameters for batch simulation</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {agents.map((agent, index) => (
            <Card key={index} className="p-4">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  <Label>Agent #{index + 1}</Label>
                </div>
                <Button variant="ghost" size="sm" onClick={() => removeAgent(index)}>
                  Remove
                </Button>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <Label>Type</Label>
                  <Select
                    value={agent.agent_type}
                    onValueChange={(value: string) => updateAgent(index, 'agent_type', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="MarketMaker">Market Maker</SelectItem>
                      <SelectItem value="NoiseTrader">Noise Trader</SelectItem>
                      <SelectItem value="InformedTrader">Informed Trader</SelectItem>
                      <SelectItem value="Taker">Taker</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <Label>Count</Label>
                  <Input
                    type="number"
                    min="1"
                    value={agent.count}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(index, 'count', parseInt(e.target.value) || 1)}
                  />
                </div>
              </div>

              {/* Agent-specific config */}
              {agent.agent_type === 'MarketMaker' && (
                <div className="grid grid-cols-3 gap-2">
                  <Input
                    placeholder="Spread"
                    type="number"
                    value={agent.config.spread || ''}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(index, 'config', { spread: parseFloat(e.target.value) || 0 })}
                  />
                  <Input
                    placeholder="Order Size"
                    type="number"
                    value={agent.config.order_size || ''}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(index, 'config', { order_size: parseFloat(e.target.value) || 0 })}
                  />
                  <Input
                    placeholder="Max Position"
                    type="number"
                    value={agent.config.max_position || ''}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(index, 'config', { max_position: parseFloat(e.target.value) || 0 })}
                  />
                </div>
              )}
              
              {agent.agent_type === 'NoiseTrader' && (
                <div className="grid grid-cols-2 gap-2">
                  <Input
                    placeholder="Trade Probability"
                    type="number"
                    step="0.01"
                    value={agent.config.trade_probability || ''}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(index, 'config', { trade_probability: parseFloat(e.target.value) || 0 })}
                  />
                  <Input
                    placeholder="Max Size"
                    type="number"
                    value={agent.config.max_size || ''}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(index, 'config', { max_size: parseFloat(e.target.value) || 0 })}
                  />
                </div>
              )}
            </Card>
          ))}

          <Button variant="outline" onClick={addAgent} className="w-full">
            + Add Agent
          </Button>
        </CardContent>
      </Card>

      {/* Controls */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-2">
            <Button 
              onClick={runSimulation} 
              disabled={loading}
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

      {/* Results */}
      {result && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Trades</p>
                    <p className="text-2xl font-bold">{result.total_trades}</p>
                  </div>
                  <Users className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Final Price</p>
                    <p className="text-2xl font-bold">${result.final_price?.toFixed(2) || '0.00'}</p>
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
                    <p className="text-2xl font-bold">{result.agent_stats.length}</p>
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
                <CardTitle>Price Chart</CardTitle>
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
              <div className="h-96">
                <KlineChart candleData={candles} />
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

