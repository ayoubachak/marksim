import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TrendingUp, BarChart3, Activity, Settings } from 'lucide-react'
import { formatCurrency } from '@/lib/utils'
import { KlineChart } from './KlineChart'
import type { MarketData, OrderbookData, CandleData } from '@/types'

interface ChartViewProps {
  marketData: MarketData
  orderbook: OrderbookData
  candleData: CandleData[]
  currentCandle?: CandleData
  selectedTimeframe: string
  onTimeframeChange: (timeframe: string) => void
}

export function ChartView({ marketData, orderbook, candleData, currentCandle, selectedTimeframe, onTimeframeChange }: ChartViewProps) {
  const timeframes = ['1s', '5s', '15s', '30s', '1m', '5m', '15m', '30m', '1h', '4h', '1d']
  
  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Last Price</CardDescription>
            <CardTitle className="text-green-600">{formatCurrency(marketData.lastPrice)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-muted-foreground">
              <TrendingUp className="h-4 w-4" />
              <span className="text-xs">Real-time</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Spread</CardDescription>
            <CardTitle>{formatCurrency(marketData.spread)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-muted-foreground">
              <BarChart3 className="h-4 w-4" />
              <span className="text-xs">Bid-Ask</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Volume 24h</CardDescription>
            <CardTitle>{marketData.volume.toFixed(2)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Activity className="h-4 w-4" />
              <span className="text-xs">Total volume</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Trades</CardDescription>
            <CardTitle>{marketData.tradeCount}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Settings className="h-4 w-4" />
              <span className="text-xs">Trade count</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Chart */}
      <Card className="h-[500px]">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Price Chart</CardTitle>
              <CardDescription>Real-time candlestick visualization</CardDescription>
            </div>
            {/* Timeframe Selector */}
            <div className="flex gap-2">
              {timeframes.map(tf => (
                <button
                  key={tf}
                  onClick={() => onTimeframeChange(tf)}
                  className={`px-3 py-1 text-sm rounded-md transition-colors ${
                    selectedTimeframe === tf
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted hover:bg-muted/80'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="h-[calc(100%-120px)]">
          <KlineChart candleData={candleData} currentCandle={currentCandle} />
        </CardContent>
      </Card>

      {/* Orderbook */}
      <Card>
        <CardHeader>
          <CardTitle>Order Book</CardTitle>
          <CardDescription>Spread: {formatCurrency(orderbook.spread)}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="text-sm font-semibold mb-2 text-green-600">Bids</h3>
              <div className="space-y-1 max-h-[300px] overflow-y-auto">
                {orderbook.bids.slice().reverse().map((level, i) => (
                  <div key={i} className="flex justify-between text-sm bg-green-950/30 p-2 rounded border-l-2 border-green-500">
                    <span className="font-mono">{formatCurrency(level.price)}</span>
                    <span className="text-muted-foreground">{level.size.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold mb-2 text-red-600">Asks</h3>
              <div className="space-y-1 max-h-[300px] overflow-y-auto">
                {orderbook.asks.map((level, i) => (
                  <div key={i} className="flex justify-between text-sm bg-red-950/30 p-2 rounded border-l-2 border-red-500">
                    <span className="font-mono">{formatCurrency(level.price)}</span>
                    <span className="text-muted-foreground">{level.size.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
