"""
Noise Trader Agent - Adds random market activity and volatility.
"""
from typing import List
from decimal import Decimal
import logging
import random

from .base import AsyncAgent
from ..core.types import Order, MarketData, Side, OrderType, TimeInForce
from ..core.order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class NoiseTraderAgent(AsyncAgent):
    """
    Random trader adding noise to the market.
    
    Features:
    - Random trading decisions
    - Market orders for immediate execution
    - Configurable trade probability
    - Random order sizes
    """
    
    def __init__(
        self,
        agent_id: str,
        trade_probability: float = 0.1,
        max_size: Decimal = Decimal("5.0")
    ):
        super().__init__(agent_id)
        self.trade_probability = trade_probability
        self.max_size = max_size
        
        logger.info(f"NoiseTraderAgent {agent_id} initialized: prob={trade_probability}, max_size={max_size}")
    
    async def generate_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """Randomly generate market orders"""
        
        # Random decision to trade
        if random.random() > self.trade_probability:
            return []
        
        # Random side and size
        side = Side.BUY if random.random() > 0.5 else Side.SELL
        size = Decimal(str(random.uniform(0.1, float(self.max_size))))
        
        order = Order(
            order_id=f"{self.agent_id}_noise_{market_data.timestamp}",
            agent_id=self.agent_id,
            side=side,
            order_type=OrderType.MARKET,
            size=size,
            timestamp=market_data.timestamp,
            time_in_force=TimeInForce.IOC
        )
        
        logger.debug(f"Agent {self.agent_id}: Generated {side.value} order for {size}")
        return [order]
    
    def get_config(self) -> dict:
        """Get agent configuration"""
        return {
            'agent_id': self.agent_id,
            'agent_type': 'NoiseTrader',
            'trade_probability': self.trade_probability,
            'max_size': float(self.max_size)
        }

