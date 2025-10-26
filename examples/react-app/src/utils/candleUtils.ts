/**
 * Convert trades to candles for a given timeframe
 */
export interface Trade {
  timestamp: number
  price: number
  size: number
}

export interface Candle {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

/**
 * Convert trades to candles for a specific timeframe
 */
export function tradesToCandles(trades: Trade[], timeframeMs: number): Candle[] {
  if (trades.length === 0) return []

  // Sort trades by timestamp
  const sortedTrades = [...trades].sort((a, b) => a.timestamp - b.timestamp)

  const candles: Candle[] = []
  let currentCandle: Partial<Candle> | null = null

  for (const trade of sortedTrades) {
    // Convert from microseconds to milliseconds
    const timestampMs = trade.timestamp / 1000
    const candleStart = Math.floor(timestampMs / timeframeMs) * timeframeMs

    if (!currentCandle || currentCandle.timestamp !== candleStart) {
      // Close previous candle if exists
      if (currentCandle) {
        candles.push({
          timestamp: currentCandle.timestamp!,
          open: currentCandle.open!,
          high: currentCandle.high!,
          low: currentCandle.low!,
          close: currentCandle.close!,
          volume: currentCandle.volume!
        })
      }

      // Start new candle
      currentCandle = {
        timestamp: candleStart,
        open: trade.price,
        high: trade.price,
        low: trade.price,
        close: trade.price,
        volume: trade.size
      }
    } else {
      // Update current candle
      currentCandle.high = Math.max(currentCandle.high!, trade.price)
      currentCandle.low = Math.min(currentCandle.low!, trade.price)
      currentCandle.close = trade.price
      currentCandle.volume = (currentCandle.volume || 0) + trade.size
    }
  }

  // Close last candle
  if (currentCandle) {
    candles.push({
      timestamp: currentCandle.timestamp!,
      open: currentCandle.open!,
      high: currentCandle.high!,
      low: currentCandle.low!,
      close: currentCandle.close!,
      volume: currentCandle.volume!
    })
  }

  return candles
}

/**
 * Get timeframe in milliseconds
 */
export function getTimeframeMs(timeframe: string): number {
  const unit = timeframe.slice(-1)
  const value = parseInt(timeframe.slice(0, -1))

  const multipliers: Record<string, number> = {
    's': 1000,
    'm': 60 * 1000,
    'h': 3600 * 1000,
    'd': 86400 * 1000
  }

  return value * (multipliers[unit] || 1000)
}

