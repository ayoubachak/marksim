"""
Taker Agent - Places market orders that immediately execute.
These are the key drivers of price movement in the simulation.
"""
from typing import List
from decimal import Decimal
import logging
import random

from .base import AsyncAgent
from ..core.types import Order, MarketData, Side, OrderType, TimeInForce
from ..core.order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class TakerAgent(AsyncAgent):
    """
    Taker agent that places limit orders that cross the spread.
    
    This is the key difference from the YouTube simulation:
    - Market orders (pure takers) execute immediately but can't be placed on a limit book
    - Instead, we place LIMIT orders at prices that CROSS the spread
    - This achieves the "taker" behavior: immediate execution
    
    Features:
    - Places orders that cross the spread (immediate execution)
    - Random price movements around current price
    - Configurable trade frequency
    - Drives price movement by consuming liquidity
    """
    
    def __init__(
        self,
        agent_id: str,
        trade_probability: float = 0.15,
        price_deviation: float = 0.01,  # 1% max deviation from current price
        min_size: Decimal = Decimal("0.5"),
        max_size: Decimal = Decimal("3.0")
    ):
        super().__init__(agent_id)
        self.trade_probability = trade_probability
        self.price_deviation = price_deviation
        self.min_size = min_size
        self.max_size = max_size
        
        logger.info(f"TakerAgent {agent_id} initialized: prob={trade_probability}, deviation={price_deviation}")
    
    async def generate_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """Generate limit orders that cross the spread (taker behavior)"""
        
        # Random decision to trade
        if random.random() > self.trade_probability:
            return []
        
        # Get reference price
        mid_price = order_book.mid_price
        if not mid_price:
            mid_price = market_data.last_price
            if not mid_price:
                logger.debug(f"Agent {self.agent_id}: No reference price available")
                return []
        
        # Random side
        side = Side.BUY if random.random() > 0.5 else Side.SELL
        
        # Random size
        size = Decimal(str(random.uniform(float(self.min_size), float(self.max_size))))
        
        # Calculate target price that crosses the spread
        if side == Side.BUY:
            # For buy orders, place at best ask + small premium to ensure crossing
            if order_book._snapshot.asks:
                best_ask = min(order_book._snapshot.asks.keys())
                target_price = best_ask + Decimal('0.01')  # Cross by 1 cent to ensure execution
            else:
                # No asks available, place above mid
                deviation = Decimal(str(random.uniform(0, self.price_deviation)))
                target_price = mid_price * (Decimal('1') + deviation)
        else:
            # For sell orders, place at best bid - small discount to ensure crossing
            if order_book._snapshot.bids:
                best_bid = max(order_book._snapshot.bids.keys())
                target_price = best_bid - Decimal('0.01')  # Cross by 1 cent to ensure execution
            else:
                # No bids available, place below mid
                deviation = Decimal(str(random.uniform(0, self.price_deviation)))
                target_price = mid_price * (Decimal('1') - deviation)
        
        order = Order(
            order_id=f"{self.agent_id}_taker_{market_data.timestamp}",
            agent_id=self.agent_id,
            side=side,
            order_type=OrderType.LIMIT,  # Limit order at crossing price
            size=size,
            price=target_price,
            time_in_force=TimeInForce.IOC,  # Immediate or Cancel (pure taker behavior)
            timestamp=market_data.timestamp
        )
        
        logger.debug(f"Agent {self.agent_id}: Placed {side.value} taker order at ${target_price} (size={size})")
        return [order]
    
    def get_config(self) -> dict:
        """Get agent configuration"""
        return {
            'agent_id': self.agent_id,
            'agent_type': 'Taker',
            'trade_probability': self.trade_probability,
            'price_deviation': self.price_deviation,
            'min_size': float(self.min_size),
            'max_size': float(self.max_size)
        }

