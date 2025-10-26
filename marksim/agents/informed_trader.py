"""
Informed Trader Agent - Makes directional trades based on information bias.
"""
from typing import List
from decimal import Decimal
import logging
import random

from .base import AsyncAgent
from ..core.types import Order, MarketData, Side, OrderType, TimeInForce
from ..core.order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class InformedTraderAgent(AsyncAgent):
    """
    Informed trader with directional bias based on information.
    
    Features:
    - Directional trading bias
    - Configurable bias strength
    - Information-driven decisions
    - Limit orders at target prices
    """
    
    def __init__(
        self,
        agent_id: str,
        bias_probability: float = 0.3,
        bias_strength: float = 0.02,  # 2% price movement expectation
        order_size: Decimal = Decimal("2.0")
    ):
        super().__init__(agent_id)
        self.bias_probability = bias_probability
        self.bias_strength = Decimal(str(bias_strength))
        self.order_size = order_size
        self.current_bias = None  # BUY or SELL
        
        logger.info(f"InformedTraderAgent {agent_id} initialized: bias_prob={bias_probability}, bias_strength={bias_strength}")
    
    async def generate_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """Generate orders based on information bias"""
        
        # Check if we should update our bias
        if random.random() < self.bias_probability:
            self.current_bias = Side.BUY if random.random() > 0.5 else Side.SELL
            logger.debug(f"Agent {self.agent_id}: Updated bias to {self.current_bias.value}")
        
        # If no bias, don't trade
        if not self.current_bias:
            return []
        
        # Get reference price
        mid_price = order_book.mid_price
        if not mid_price:
            # Bootstrap with last price if no mid price available
            mid_price = market_data.last_price
            if not mid_price:
                logger.debug(f"Agent {self.agent_id}: No reference price available")
                return []
        
        # Calculate target price based on bias - make it cross with current order book
        if self.current_bias == Side.BUY:
            # Place buy order above the best ask to ensure crossing
            if order_book._snapshot.asks:
                best_ask = min(order_book._snapshot.asks.keys())
                target_price = best_ask + Decimal('1.0')  # Cross the spread by $1
            else:
                target_price = mid_price * (Decimal('1') + Decimal(str(self.bias_strength)) * Decimal('0.1'))
            side = Side.BUY
        else:
            # Place sell order below the best bid to ensure crossing
            if order_book._snapshot.bids:
                best_bid = max(order_book._snapshot.bids.keys())
                target_price = best_bid - Decimal('1.0')  # Cross the spread by $1
            else:
                target_price = mid_price * (Decimal('1') - Decimal(str(self.bias_strength)) * Decimal('0.1'))
            side = Side.SELL
        
        order = Order(
            order_id=f"{self.agent_id}_informed_{market_data.timestamp}",
            agent_id=self.agent_id,
            side=side,
            order_type=OrderType.LIMIT,
            size=self.order_size,
            price=target_price,
            time_in_force=TimeInForce.GTC,
            timestamp=market_data.timestamp
        )
        
        logger.debug(f"Agent {self.agent_id}: Placed {side.value} order at ${target_price} (bias: {self.current_bias.value})")
        return [order]
    
    def get_config(self) -> dict:
        """Get agent configuration"""
        return {
            'agent_id': self.agent_id,
            'agent_type': 'InformedTrader',
            'bias_probability': self.bias_probability,
            'bias_strength': float(self.bias_strength),
            'order_size': float(self.order_size),
            'current_bias': self.current_bias.value if self.current_bias else None
        }
