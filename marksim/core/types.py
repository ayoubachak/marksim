"""
Domain models for market simulation.
All models are immutable for thread-safety.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List
from decimal import Decimal
import time

# ============================================================================
# ENUMS
# ============================================================================

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LIMIT = "STOP_LIMIT"

class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class TimeInForce(Enum):
    GTC = "GTC"  # Good till cancelled
    IOC = "IOC"  # Immediate or cancel
    FOK = "FOK"  # Fill or kill
    DAY = "DAY"  # Day order

# ============================================================================
# CORE MODELS (Immutable)
# ============================================================================

@dataclass(frozen=True)
class Order:
    """Immutable order representation"""
    order_id: str
    agent_id: str
    side: Side
    order_type: OrderType
    size: Decimal
    price: Optional[Decimal] = None  # None for market orders
    time_in_force: TimeInForce = TimeInForce.GTC
    timestamp: int = field(default_factory=lambda: int(time.time() * 1_000_000))
    status: OrderStatus = OrderStatus.PENDING
    filled_size: Decimal = Decimal(0)
    
    def __post_init__(self):
        # Validate
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("Limit orders must have a price")
        if self.size <= 0:
            raise ValueError("Order size must be positive")

@dataclass(frozen=True)
class Trade:
    """Immutable trade execution"""
    trade_id: str
    timestamp: int
    price: Decimal
    size: Decimal
    buy_order_id: str
    sell_order_id: str
    aggressor_side: Side

@dataclass(frozen=True)
class MarketData:
    """Market data snapshot"""
    timestamp: int
    symbol: str
    last_price: Optional[Decimal] = None
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    bid_size: Optional[Decimal] = None
    ask_size: Optional[Decimal] = None
    volume_24h: Decimal = Decimal(0)
    trades: List[Trade] = field(default_factory=list)

@dataclass(frozen=True)
class Candle:
    """OHLCV candlestick"""
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trade_count: int
    timeframe: str  # '1m', '5m', '1h', etc.

# ============================================================================
# EVENT MODELS
# ============================================================================

@dataclass(frozen=True)
class Event:
    """Base event class"""
    timestamp: int
    priority: int  # Lower = higher priority
    
    def __lt__(self, other):
        """For heapq comparison"""
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        return self.priority < other.priority

@dataclass(frozen=True)
class OrderEvent(Event):
    """Order submission event"""
    order: Order

@dataclass(frozen=True)
class TradeEvent(Event):
    """Trade execution event"""
    trade: Trade

@dataclass(frozen=True)
class AgentWakeupEvent(Event):
    """Agent decision-making event"""
    agent_id: str

@dataclass(frozen=True)
class CandleCloseEvent(Event):
    """Candle close event"""
    timeframe: str

@dataclass(frozen=True)
class SnapshotEvent(Event):
    """Order book snapshot event"""
    pass

# ============================================================================
# MATCH RESULT
# ============================================================================

@dataclass(frozen=True)
class MatchResult:
    """Result of order matching"""
    order: Order
    trades: List[Trade] = field(default_factory=list)
    remaining_order: Optional[Order] = None
    rejected: bool = False
    rejection_reason: Optional[str] = None
