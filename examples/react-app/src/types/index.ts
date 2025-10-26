// Market Data Types
export interface MarketData {
  lastPrice: number | null
  spread: number | null
  volume: number
  tradeCount: number
  timestamp: number
}

// Orderbook Types
export interface OrderbookLevel {
  price: number
  size: number
}

export interface OrderbookData {
  bids: OrderbookLevel[]
  asks: OrderbookLevel[]
  spread: number
  midPrice: number
  timestamp: number
}

// Agent Types
export type AgentType = 'MarketMaker' | 'NoiseTrader' | 'InformedTrader'

export interface AgentConfig {
  agent_id: string
  agent_type: AgentType
  [key: string]: string | number | null | undefined
}

// WebSocket Message Types
export interface MarketDataMessage {
  type: 'market_data'
  timestamp: number
  symbol: string
  last_price: number | null
  bid_price?: number | null
  ask_price?: number | null
  bid_size?: number | null
  ask_size?: number | null
  volume_24h: number
  trade_count: number
}

export interface OrderbookMessage {
  type: 'orderbook'
  bids: [number, number][]
  asks: [number, number][]
  spread: number
  mid_price: number
  timestamp: number
}

export interface AgentConfigMessage {
  type: 'agent_configs'
  configs: AgentConfig[]
}

export interface KlineMessage {
  e: 'kline'
  E: number
  s: string
  k: {
    t: number
    T: number
    s: string
    i: string
    f: number
    L: number
    o: number
    c: number
    h: number
    l: number
    v: number
    n: number
    x: boolean
    q: number
    V: number
    Q: number
    B: string
  }
}

export type WebSocketMessage = 
  | MarketDataMessage 
  | OrderbookMessage 
  | AgentConfigMessage 
  | KlineMessage

// Candle Data
export interface CandleData {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

