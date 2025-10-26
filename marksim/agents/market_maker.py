"""
Market Maker Agent - Provides liquidity by placing orders on both sides of the market.
"""
from typing import List
from decimal import Decimal
import logging

from .base import AsyncAgent
from ..core.types import Order, MarketData, Side, OrderType, TimeInForce
from ..core.order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class MarketMakerAgent(AsyncAgent):
    """
    Market maker providing liquidity by placing limit orders on both sides.
    
    Features:
    - Places buy orders below mid price
    - Places sell orders above mid price
    - Maintains spread around mid price
    - Risk management with position limits
    """
    
    def __init__(
        self,
        agent_id: str,
        spread: Decimal = Decimal("0.01"),  # 1% spread
        order_size: Decimal = Decimal("1.0"),
        max_position: Decimal = Decimal("10.0")
    ):
        super().__init__(agent_id)
        self.spread = spread
        self.order_size = order_size
        self.max_position = max_position
        
        logger.info(f"MarketMakerAgent {agent_id} initialized: spread={spread}, size={order_size}, max_pos={max_position}")
    
    async def generate_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """Place limit orders on both sides of the market"""
        
        # Check if we have too much position
        if abs(self.position) >= self.max_position:
            logger.debug(f"Agent {self.agent_id}: Risk limit hit, skipping orders")
            return []  # Risk limit hit
        
        # Get reference price
        mid_price = order_book.mid_price
        if not mid_price:
            # Bootstrap with last price if no mid price available
            mid_price = market_data.last_price
            if not mid_price:
                logger.debug(f"Agent {self.agent_id}: No reference price available")
                return []
        
        orders = []
        
        # Buy order (below mid)
        if self.position < self.max_position:
            buy_price = mid_price * (1 - self.spread / 2)
            buy_order = Order(
                order_id=f"{self.agent_id}_buy_{market_data.timestamp}",
                agent_id=self.agent_id,
                side=Side.BUY,
                order_type=OrderType.LIMIT,
                size=self.order_size,
                price=buy_price,
                time_in_force=TimeInForce.GTC,
                timestamp=market_data.timestamp
            )
            orders.append(buy_order)
            logger.debug(f"Agent {self.agent_id}: Placed buy order at ${buy_price}")
        
        # Sell order (above mid)
        if self.position > -self.max_position:
            sell_price = mid_price * (1 + self.spread / 2)
            sell_order = Order(
                order_id=f"{self.agent_id}_sell_{market_data.timestamp}",
                agent_id=self.agent_id,
                side=Side.SELL,
                order_type=OrderType.LIMIT,
                size=self.order_size,
                price=sell_price,
                time_in_force=TimeInForce.GTC,
                timestamp=market_data.timestamp
            )
            orders.append(sell_order)
            logger.debug(f"Agent {self.agent_id}: Placed sell order at ${sell_price}")
        
        return orders
    
    def get_config(self) -> dict:
        """Get agent configuration"""
        return {
            'agent_id': self.agent_id,
            'agent_type': 'MarketMaker',
            'spread': float(self.spread),
            'order_size': float(self.order_size),
            'max_position': float(self.max_position)
        }
