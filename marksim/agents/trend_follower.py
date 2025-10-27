"""
Trend Follower Agent - Follows recent price trends.
"""
from typing import List
from decimal import Decimal
import logging
import random

from .base import AsyncAgent
from ..core.types import Order, MarketData, Side, OrderType, TimeInForce
from ..core.order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class TrendFollowerAgent(AsyncAgent):
    """
    Trend follower that identifies and follows price trends.
    
    Features:
    - Uses recent price history to identify trends
    - Enters positions in direction of trend
    - Uses trailing stop logic
    - Configurable trend sensitivity
    """
    
    def __init__(
        self,
        agent_id: str,
        lookback_period: int = 5,
        trend_sensitivity: float = 0.02,  # 2% movement to confirm trend
        trade_probability: float = 0.15,
        order_size: Decimal = Decimal("2.0"),
        max_position: Decimal = Decimal("10.0")
    ):
        super().__init__(agent_id)
        self.lookback_period = lookback_period
        self.trend_sensitivity = Decimal(str(trend_sensitivity))
        self.trade_probability = trade_probability
        self.order_size = order_size
        self.max_position = max_position
        self.price_history = []
        self.current_bias = None
        
        logger.info(f"TrendFollowerAgent {agent_id} initialized: lookback={lookback_period}, sensitivity={trend_sensitivity}")
    
    async def generate_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """Generate orders based on trend following logic"""
        
        # Get reference price
        mid_price = order_book.mid_price
        if not mid_price:
            mid_price = market_data.last_price
            if not mid_price:
                return []
        
        # Update price history
        self.price_history.append(float(mid_price))
        if len(self.price_history) > self.lookback_period:
            self.price_history.pop(0)
        
        # Need at least lookback_period prices to identify trend
        if len(self.price_history) < self.lookback_period:
            return []
        
        # Calculate trend: positive for uptrend, negative for downtrend
        price_change = self.price_history[-1] - self.price_history[0]
        price_change_pct = price_change / self.price_history[0] if self.price_history[0] > 0 else 0
        
        # Determine trend direction
        if abs(price_change_pct) >= float(self.trend_sensitivity):
            if price_change_pct > 0:
                trend = Side.BUY
            else:
                trend = Side.SELL
        else:
            trend = None
        
        # Update bias based on trend
        if trend:
            self.current_bias = trend
            logger.debug(f"Agent {self.agent_id}: Trend detected: {trend.value}, change={price_change_pct:.2%}")
        
        # Only trade if we have a clear bias
        if not self.current_bias:
            return []
        
        # Randomly decide whether to trade
        if random.random() > self.trade_probability:
            return []
        
        # Check position limits
        if self.current_bias == Side.BUY and abs(self.position) >= self.max_position:
            return []
        if self.current_bias == Side.SELL and abs(self.position) >= self.max_position:
            return []
        
        # Place market order in direction of trend
        side = self.current_bias
        target_price = mid_price
        
        # If buying, place order above best ask to cross
        if side == Side.BUY and order_book._snapshot.asks:
            best_ask = min(order_book._snapshot.asks.keys())
            target_price = best_ask + Decimal('0.5')
        # If selling, place order below best bid to cross
        elif side == Side.SELL and order_book._snapshot.bids:
            best_bid = max(order_book._snapshot.bids.keys())
            target_price = best_bid - Decimal('0.5')
        
        order = Order(
            order_id=f"{self.agent_id}_trend_{market_data.timestamp}",
            agent_id=self.agent_id,
            side=side,
            order_type=OrderType.LIMIT,
            size=self.order_size,
            price=target_price,
            time_in_force=TimeInForce.IOC,
            timestamp=market_data.timestamp
        )
        
        logger.debug(f"Agent {self.agent_id}: Following trend with {side.value} order")
        return [order]
    
    def get_config(self) -> dict:
        """Get agent configuration"""
        return {
            'agent_id': self.agent_id,
            'agent_type': 'TrendFollower',
            'lookback_period': self.lookback_period,
            'trend_sensitivity': float(self.trend_sensitivity),
            'trade_probability': self.trade_probability,
            'order_size': float(self.order_size),
            'max_position': float(self.max_position)
        }

