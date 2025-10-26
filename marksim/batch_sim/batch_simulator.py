"""
Batch simulation mode - runs full simulation in one shot and returns all data.
"""
import asyncio
from decimal import Decimal
from typing import Dict, List
import logging

from ..core.time_engine import AsyncTimeEngine
from ..core.order_book import ImmutableOrderBook
from ..core.matching_engine import MatchingEngine
from ..core.types import MarketData
from ..agents.base import AsyncAgent
from ..streaming.data_stream import BoundedMarketDataStream, CandleStream

logger = logging.getLogger(__name__)


class BatchSimulationResult:
    """Results from batch simulation"""
    
    def __init__(self):
        self.trades = []
        self.order_book_states = []
        self.candles = {}
        self.market_data_points = []
        self.agent_stats = []
        self.final_price = None
        self.total_trades = 0


class BatchSimulator:
    """
    Runs simulation in batch mode - executes everything upfront and returns results.
    
    No WebSocket, no streaming - just compute and return.
    """
    
    def __init__(
        self,
        agents: List[AsyncAgent],
        initial_price: Decimal = Decimal("50000"),
        duration_seconds: int = 60,
        speed_multiplier: float = 1000.0  # Fast execution
    ):
        self.agents = agents
        self.initial_price = initial_price
        self.duration_seconds = duration_seconds
        self.speed_multiplier = speed_multiplier
        
        # Initialize components
        self.time_engine = AsyncTimeEngine(
            start_time_us=0,
            speed_multiplier=speed_multiplier
        )
        self.order_book = ImmutableOrderBook()
        self.matching_engine = MatchingEngine()
        self.order_book_states = []
        
    async def run(self) -> BatchSimulationResult:
        """
        Run batch simulation and return all results.
        
        Returns:
            BatchSimulationResult with all trades, candles, etc.
        """
        logger.info(f"Starting batch simulation: {len(self.agents)} agents, {self.duration_seconds}s")
        
        result = BatchSimulationResult()
        
        # Simulate for duration
        end_time = self.duration_seconds * 1_000_000  # microseconds
        step_us = 100_000  # 100ms steps
        
        current_time = 0
        
        while current_time < end_time:
            # Generate market data
            market_data = MarketData(
                timestamp=current_time,
                symbol="BTC/USD",
                last_price=self.initial_price
            )
            
            # Wake agents every step
            # Generate orders from all agents
            from ..agents.base import AsyncAgentPool
            agent_pool = AsyncAgentPool(self.agents, max_concurrency=100)
            
            orders = await agent_pool.generate_all_orders(market_data, self.order_book)
            
            # Process each order
            for order in orders:
                new_book, match_result = self.matching_engine.match_order(
                    order, self.order_book, current_time
                )
                self.order_book = new_book
                
                # Collect trades
                if match_result.trades:
                    result.trades.extend(match_result.trades)
                    result.total_trades += len(match_result.trades)
            
            # Store order book state
            if current_time % 1_000_000 == 0:  # Every second
                depth = self.order_book.get_depth(levels=20)
                result.order_book_states.append({
                    'timestamp': current_time,
                    'bids': depth['bids'],
                    'asks': depth['asks'],
                    'spread': depth['spread'],
                    'mid_price': depth['mid_price']
                })
            
            current_time += step_us
        
        # Get final stats
        result.agent_stats = [agent.get_stats() for agent in self.agents]
        result.final_price = self.order_book.mid_price or self.initial_price
        
        logger.info(f"Batch simulation complete: {result.total_trades} trades generated")
        
        return result
    
    def get_config() -> dict:
        """Get current configuration"""
        return {
            'agents': len(self.agents),
            'initial_price': float(self.initial_price),
            'duration_seconds': self.duration_seconds,
            'speed_multiplier': self.speed_multiplier
        }

