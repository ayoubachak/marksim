"""
High Frequency Trader Agent - Fast, frequent trades with small price improvements.
"""
from typing import List
from decimal import Decimal
import logging
import random

from .base import AsyncAgent
from ..core.types import Order, MarketData, Side, OrderType, TimeInForce
from ..core.order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class HighFrequencyTraderAgent(AsyncAgent):
    """
    High frequency trader with very fast trading decisions.
    
    Features:
    - High trade frequency (low probability threshold)
    - Small price improvements to capture spread
    - Very small position sizes
    - Rapid order placement and cancellation
    """
    
    def __init__(
        self,
        agent_id: str,
        trade_probability: float = 0.5,  # High frequency
        order_size: Decimal = Decimal("0.5"),
        price_improvement: Decimal = Decimal("0.001"),  # 0.1% improvement
        max_position: Decimal = Decimal("5.0")
    ):
        super().__init__(agent_id)
        self.trade_probability = trade_probability
        self.order_size = order_size
        self.price_improvement = price_improvement
        self.max_position = max_position
        
        logger.info(f"HighFrequencyTraderAgent {agent_id} initialized: prob={trade_probability}, size={order_size}")
    
    async def generate_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """Generate high-frequency orders with small price improvements"""
        
        # Get reference price
        mid_price = order_book.mid_price
        if not mid_price:
            mid_price = market_data.last_price
            if not mid_price:
                return []
        
        # High frequency traders trade very frequently
        if random.random() > self.trade_probability:
            return []
        
        orders = []
        
        # Randomly choose side
        side = Side.BUY if random.random() > 0.5 else Side.SELL
        
        # Check position limits
        if side == Side.BUY and abs(self.position) >= self.max_position:
            return []
        if side == Side.SELL and abs(self.position) >= self.max_position:
            return []
        
        # Calculate target price with small improvement
        if side == Side.BUY:
            # Try to buy slightly below market to improve
            if order_book._snapshot.bids:
                best_bid = max(order_book._snapshot.bids.keys())
                target_price = best_bid + Decimal(str(self.price_improvement / 100))  # 0.1% better than best bid
            else:
                target_price = mid_price * (Decimal('1') - self.price_improvement)
        else:
            # Try to sell slightly above market
            if order_book._snapshot.asks:
                best_ask = min(order_book._snapshot.asks.keys())
                target_price = best_ask - Decimal(str(self.price_improvement / 100))  # 0.1% better than best ask
            else:
                target_price = mid_price * (Decimal('1') + self.price_improvement)
        
        order = Order(
            order_id=f"{self.agent_id}_hft_{market_data.timestamp}",
            agent_id=self.agent_id,
            side=side,
            order_type=OrderType.LIMIT,
            size=self.order_size,
            price=target_price,
            time_in_force=TimeInForce.IOC,  # Immediate or cancel
            timestamp=market_data.timestamp
        )
        orders.append(order)
        
        logger.debug(f"Agent {self.agent_id}: Placed HFT {side.value} order")
        return orders
    
    def get_config(self) -> dict:
        """Get agent configuration"""
        return {
            'agent_id': self.agent_id,
            'agent_type': 'HighFrequencyTrader',
            'trade_probability': self.trade_probability,
            'order_size': float(self.order_size),
            'price_improvement': float(self.price_improvement),
            'max_position': float(self.max_position)
        }

