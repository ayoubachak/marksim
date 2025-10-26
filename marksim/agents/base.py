"""
Async agent base classes with concurrent execution support.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional
from decimal import Decimal
import logging

from ..core.types import Order, MarketData, Side, OrderType, TimeInForce
from ..core.order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class AsyncAgent(ABC):
    """
    Base class for trading agents.
    All methods are async for non-blocking execution.
    """
    
    def __init__(self, agent_id: str, initial_balance: Decimal = Decimal(10000)):
        self.agent_id = agent_id
        self.balance = initial_balance
        self.position = Decimal(0)
        self.active_orders: List[Order] = []
        
        # Performance tracking
        self.total_trades = 0
        self.total_volume = Decimal(0)
        self.pnl = Decimal(0)
    
    @abstractmethod
    async def generate_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """
        Generate orders based on market state.
        Must be implemented by subclasses.
        """
        pass
    
    async def on_trade_executed(
        self,
        order: Order,
        executed_size: Decimal,
        executed_price: Decimal
    ):
        """Callback when agent's order is executed"""
        self.total_trades += 1
        self.total_volume += executed_size
        
        # Update position
        if order.side == Side.BUY:
            self.position += executed_size
            self.balance -= executed_size * executed_price
        else:
            self.position -= executed_size
            self.balance += executed_size * executed_price
        
        logger.debug(
            f"Agent {self.agent_id}: Trade executed - "
            f"Size: {executed_size}, Price: {executed_price}, "
            f"Position: {self.position}, Balance: {self.balance}"
        )
    
    async def on_order_cancelled(self, order: Order):
        """Callback when agent's order is cancelled"""
        if order in self.active_orders:
            self.active_orders.remove(order)
    
    def get_stats(self) -> dict:
        """Get agent performance statistics"""
        return {
            'agent_id': self.agent_id,
            'balance': float(self.balance),
            'position': float(self.position),
            'total_trades': self.total_trades,
            'total_volume': float(self.total_volume),
            'pnl': float(self.pnl),
            'active_orders': len(self.active_orders)
        }
    
    def get_config(self) -> dict:
        """Get agent configuration - override in subclasses"""
        return {
            'agent_type': 'Base',
            'agent_id': self.agent_id
        }

# ============================================================================
# AGENT POOL (Concurrent Execution)
# ============================================================================

class AsyncAgentPool:
    """
    Manages multiple agents with concurrent execution.
    """
    
    def __init__(
        self,
        agents: List[AsyncAgent],
        max_concurrency: int = 10
    ):
        self.agents = agents
        self.semaphore = asyncio.Semaphore(max_concurrency)
        
        logger.info(f"Agent pool initialized with {len(agents)} agents")
    
    async def generate_all_orders(
        self,
        market_data: MarketData,
        order_book: ImmutableOrderBook
    ) -> List[Order]:
        """
        Generate orders from all agents concurrently.
        Returns flattened list of all orders.
        """
        
        async def _agent_task(agent: AsyncAgent):
            """Single agent task with error handling"""
            async with self.semaphore:  # Limit concurrency
                try:
                    orders = await agent.generate_orders(market_data, order_book)
                    return orders or []
                except Exception as e:
                    logger.error(
                        f"Agent {agent.agent_id} error: {e}",
                        exc_info=True
                    )
                    return []
        
        # Execute all agents concurrently
        results = await asyncio.gather(
            *[_agent_task(agent) for agent in self.agents],
            return_exceptions=True
        )
        
        # Flatten results
        all_orders = []
        for result in results:
            if isinstance(result, list):
                all_orders.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Agent task failed: {result}")
        
        logger.debug(f"Generated {len(all_orders)} orders from {len(self.agents)} agents")
        return all_orders
    
    async def notify_trade(
        self,
        agent_id: str,
        order: Order,
        executed_size: Decimal,
        executed_price: Decimal
    ):
        """Notify specific agent of trade execution"""
        agent = self.get_agent(agent_id)
        if agent:
            await agent.on_trade_executed(order, executed_size, executed_price)
    
    async def notify_cancellation(self, agent_id: str, order: Order):
        """Notify specific agent of order cancellation"""
        agent = self.get_agent(agent_id)
        if agent:
            await agent.on_order_cancelled(order)
    
    def get_agent(self, agent_id: str) -> Optional[AsyncAgent]:
        """Get agent by ID"""
        return next((a for a in self.agents if a.agent_id == agent_id), None)
    
    def get_all_stats(self) -> List[dict]:
        """Get statistics for all agents"""
        return [agent.get_stats() for agent in self.agents]
    
    def get_all_configs(self) -> List[dict]:
        """Get configuration for all agents"""
        return [agent.get_config() for agent in self.agents]