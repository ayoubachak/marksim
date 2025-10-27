"""
Whale Trader Agent - Large institutional trader with significant market impact.
"""
from typing import List
from decimal import Decimal
import logging
import random

from .base import AsyncAgent
from ..core.types import Order, MarketData, Side, OrderType, TimeInForce
from ..core.order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class WhaleAgent(AsyncAgent):
    """
    Whale trader with large position sizes and market impact.
    
    Features:
    - Very large order sizes
    - Infrequent but significant trades
    - Market impact awareness
    - Configurable trading frequency
    - Can be bullish or bearish
    """
    
    def __init__(
        self,
        agent_id: str,
        trade_probability: float = 0.05,  # Low frequency, high impact
        order_size: Decimal = Decimal("20.0"),  # Large orders
        min_size: Decimal = Decimal("15.0"),
        max_size: Decimal = Decimal("50.0"),
        market_impact_factor: float = 0.02,  # 2% expected price impact
        max_position: Decimal = Decimal("100.0")
    ):
        super().__init__(agent_id)
        self.trade_probability = trade_probability
        self.order_size = order_size
        self.min_size = min_size
        self.max_size = max_size
        self.market_impact_factor = Decimal(str(market_impact_factor))
        self.max_position = max_position
        
        logger.info(f"WhaleAgent {agent_id} initialized: prob={trade_probability}, size={order_size}")
    
    async def generate_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """Generate large whale orders with market impact"""
        
        # Get reference price
        mid_price = order_book.mid_price
        if not mid_price:
            mid_price = market_data.last_price
            if not mid_price:
                return []
        
        # Whale traders trade infrequently but with large size
        if random.random() > self.trade_probability:
            return []
        
        # Randomly choose side (whales can be bullish or bearish)
        side = Side.BUY if random.random() > 0.5 else Side.SELL
        
        # Check position limits
        if side == Side.BUY and abs(self.position) >= self.max_position:
            logger.debug(f"Agent {self.agent_id}: Position limit reached")
            return []
        if side == Side.SELL and abs(self.position) >= self.max_position:
            logger.debug(f"Agent {self.agent_id}: Position limit reached")
            return []
        
        # Large random order size
        size_range = float(self.max_size) - float(self.min_size)
        random_size = Decimal(str(random.uniform(float(self.min_size), float(self.max_size))))
        
        # Calculate target price with market impact consideration
        # Large orders should be aware they move the market
        impact = self.market_impact_factor * random_size / Decimal("20.0")  # Scale impact by size
        
        if side == Side.BUY:
            # Buy at slightly above market to ensure execution
            if order_book._snapshot.asks:
                best_ask = min(order_book._snapshot.asks.keys())
                target_price = best_ask * (Decimal('1') + impact)
            else:
                target_price = mid_price * (Decimal('1') + impact)
        else:
            # Sell at slightly below market
            if order_book._snapshot.bids:
                best_bid = max(order_book._snapshot.bids.keys())
                target_price = best_bid * (Decimal('1') - impact)
            else:
                target_price = mid_price * (Decimal('1') - impact)
        
        order = Order(
            order_id=f"{self.agent_id}_whale_{market_data.timestamp}",
            agent_id=self.agent_id,
            side=side,
            order_type=OrderType.LIMIT,
            size=random_size,
            price=target_price,
            time_in_force=TimeInForce.GTC,  # Large orders take time to fill
            timestamp=market_data.timestamp
        )
        
        logger.debug(f"Agent {self.agent_id}: Whaling with {side.value} order for {random_size}")
        return [order]
    
    def get_config(self) -> dict:
        """Get agent configuration"""
        return {
            'agent_id': self.agent_id,
            'agent_type': 'Whale',
            'trade_probability': self.trade_probability,
            'order_size': float(self.order_size),
            'min_size': float(self.min_size),
            'max_size': float(self.max_size),
            'market_impact_factor': float(self.market_impact_factor),
            'max_position': float(self.max_position)
        }

