"""
Main market simulation orchestrator.
Pure asyncio, no threads, fully concurrent.
"""
import asyncio
from typing import List, Optional
from decimal import Decimal
import logging
import time

from .core.time_engine import AsyncTimeEngine
from .core.order_book import ImmutableOrderBook
from .core.matching_engine import MatchingEngine
from .core.types import (
    OrderEvent, TradeEvent, AgentWakeupEvent,
    MarketData, Event
)
from .agents.base import AsyncAgentPool, AsyncAgent
from .agents import MarketMakerAgent, NoiseTraderAgent, InformedTraderAgent, TakerAgent
from .streaming.data_stream import BoundedMarketDataStream, TradeStream, CandleStream

logger = logging.getLogger(__name__)

class MarketSimulation:
    """
    Main simulation coordinator.
    All operations are async and non-blocking.
    """
    
    def __init__(
        self,
        agents: List[AsyncAgent],
        initial_price: Decimal = Decimal("50000"),
        agent_wakeup_interval_us: int = 100_000,  # 100ms
        output_stream: Optional[BoundedMarketDataStream] = None,
        candle_stream: Optional[CandleStream] = None,
        speed_multiplier: float = 1.0,
        enable_batching: Optional[bool] = None
    ):
        # Core components
        self.time_engine = AsyncTimeEngine(
            start_time_us=int(time.time() * 1_000_000),
            speed_multiplier=speed_multiplier
        )
        self.order_book = ImmutableOrderBook()
        self.matching_engine = MatchingEngine()
        # Use BatchedAgentPool for automatic optimization if enabled
        # Default: auto-enable for 100+ agents for performance
        if enable_batching is None:
            enable_batching = len(agents) >= 100
        
        if enable_batching:
            from .agents.batched_pool import BatchedAgentPool
            self.agent_pool = BatchedAgentPool(agents, enable_batching=True)
        else:
            from .agents.base import AsyncAgentPool
            self.agent_pool = AsyncAgentPool(agents, max_concurrency=10)
        
        # State
        self.initial_price = initial_price
        self.current_market_data = MarketData(
            timestamp=self.time_engine.current_time_us,
            symbol="BTC/USD",
            last_price=initial_price
        )
        
        # Streaming
        self.output_stream = output_stream or BoundedMarketDataStream()
        self.trade_stream = TradeStream()
        self.candle_stream = candle_stream or CandleStream(timeframes=['1m', '5m', '15m', '1h'], maxsize=100)
        
        # Config
        self.agent_wakeup_interval_us = agent_wakeup_interval_us
        
        # Agent management
        self._agent_counter = {}
        
        # Register event handlers
        self._register_handlers()
        
        # Schedule initial agent wakeups
        self._schedule_agent_wakeups()
        
        logger.info(f"Simulation initialized with {len(agents)} agents")
    
    # ========================================================================
    # AGENT MANAGEMENT
    # ========================================================================
    
    def add_agent(self, agent_type: str, config: dict) -> str:
        """Add a new agent to the simulation"""
        agent_id = f"{agent_type.lower()}_{self._get_next_agent_id(agent_type)}"
        
        if agent_type == 'MarketMaker':
            agent = MarketMakerAgent(
                agent_id=agent_id,
                spread=Decimal(str(config.get('spread', 0.01))),
                order_size=Decimal(str(config.get('order_size', 1.0))),
                max_position=Decimal(str(config.get('max_position', 10.0)))
            )
        elif agent_type == 'NoiseTrader':
            agent = NoiseTraderAgent(
                agent_id=agent_id,
                trade_probability=config.get('trade_probability', 0.1),
                max_size=Decimal(str(config.get('max_size', 5.0)))
            )
        elif agent_type == 'InformedTrader':
            agent = InformedTraderAgent(
                agent_id=agent_id,
                bias_probability=config.get('bias_probability', 0.3),
                bias_strength=config.get('bias_strength', 0.02),
                order_size=Decimal(str(config.get('order_size', 2.0)))
            )
        elif agent_type == 'Taker':
            agent = TakerAgent(
                agent_id=agent_id,
                trade_probability=config.get('trade_probability', 0.15),
                price_deviation=config.get('price_deviation', 0.01),
                min_size=Decimal(str(config.get('min_size', 0.5))),
                max_size=Decimal(str(config.get('max_size', 3.0)))
            )
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        # Add to agent pool
        self.agent_pool.agents.append(agent)
        logger.info(f"Added agent: {agent_id} ({agent_type})")
        
        return agent_id
    
    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the simulation"""
        initial_count = len(self.agent_pool.agents)
        self.agent_pool.agents = [a for a in self.agent_pool.agents if a.agent_id != agent_id]
        
        if len(self.agent_pool.agents) < initial_count:
            logger.info(f"Removed agent: {agent_id}")
            return True
        
        logger.warning(f"Agent not found: {agent_id}")
        return False
    
    def update_agent(self, agent_id: str, config: dict) -> bool:
        """Update agent configuration"""
        agent = self.agent_pool.get_agent(agent_id)
        if not agent:
            logger.warning(f"Agent not found: {agent_id}")
            return False
        
        # Update agent properties
        for key, value in config.items():
            if hasattr(agent, key):
                if isinstance(getattr(agent, key), Decimal):
                    setattr(agent, key, Decimal(str(value)))
                else:
                    setattr(agent, key, value)
        
        logger.info(f"Updated agent: {agent_id} with config: {config}")
        return True
    
    def _get_next_agent_id(self, agent_type: str) -> int:
        """Get next numeric ID for agent"""
        agent_type_lower = agent_type.lower()
        if agent_type_lower not in self._agent_counter:
            self._agent_counter[agent_type_lower] = 0
        
        self._agent_counter[agent_type_lower] += 1
        return self._agent_counter[agent_type_lower]
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    def _register_handlers(self):
        """Register all event handlers"""
        self.time_engine.register_handler(OrderEvent, self._handle_order_event)
        self.time_engine.register_handler(TradeEvent, self._handle_trade_event)
        self.time_engine.register_handler(AgentWakeupEvent, self._handle_agent_wakeup)
    
    async def _handle_order_event(self, event: OrderEvent):
        """Process order submission"""
        order = event.order
        
        logger.debug(f"Processing order: {order.order_id}")
        
        # Match order against book
        new_book, match_result = self.matching_engine.match_order(
            order,
            self.order_book,
            event.timestamp
        )
        
        # Update book state
        self.order_book = new_book
        
        # Handle rejection
        if match_result.rejected:
            logger.warning(
                f"Order rejected: {order.order_id} - {match_result.rejection_reason}"
            )
            return
        
        # Process trades
        for trade in match_result.trades:
            # Schedule trade event (for processing)
            trade_event = TradeEvent(
                timestamp=event.timestamp,
                priority=2,
                trade=trade
            )
            self.time_engine.schedule_event(trade_event)
        
        # Publish market data update
        await self._publish_market_update(event.timestamp)
    
    async def _handle_trade_event(self, event: TradeEvent):
        """Process trade execution"""
        trade = event.trade
        
        logger.debug(f"Trade executed: {trade.trade_id} @ {trade.price}")
        
        # Update market data
        # Get bid/ask from order book or use trade price as fallback
        bid_price = self.order_book.best_bid or trade.price
        ask_price = self.order_book.best_ask or trade.price
        
        self.current_market_data = MarketData(
            timestamp=event.timestamp,
            symbol="BTC/USD",
            last_price=trade.price,
            bid_price=bid_price - Decimal("5"),  # Add small spread for visualization
            ask_price=ask_price + Decimal("5"),
            bid_size=Decimal("10"),  # Placeholder size
            ask_size=Decimal("10"),  # Placeholder size
            volume_24h=self.current_market_data.volume_24h + trade.size,
            trades=[trade]
        )
        
        # Notify agents
        # Find buy agent
        buy_order = self.order_book.get_order(trade.buy_order_id)
        if buy_order:
            await self.agent_pool.notify_trade(
                buy_order.agent_id,
                buy_order,
                trade.size,
                trade.price
            )
        
        # Find sell agent
        sell_order = self.order_book.get_order(trade.sell_order_id)
        if sell_order:
            await self.agent_pool.notify_trade(
                sell_order.agent_id,
                sell_order,
                trade.size,
                trade.price
            )
        
        # Publish to streams
        await self.trade_stream.publish_trade(trade)
        await self.candle_stream.update_from_trade(trade)
        await self.output_stream.publish(self.current_market_data)
    
    async def _handle_agent_wakeup(self, event: AgentWakeupEvent):
        """Agent decision-making time"""
        
        # Generate orders from all agents concurrently
        orders = await self.agent_pool.generate_all_orders(
            self.current_market_data,
            self.order_book
        )
        
        # Schedule order events
        for order in orders:
            order_event = OrderEvent(
                timestamp=event.timestamp,
                priority=3,
                order=order
            )
            self.time_engine.schedule_event(order_event, delay_us=1)
        
        # Schedule next wakeup
        next_wakeup = AgentWakeupEvent(
            timestamp=event.timestamp + self.agent_wakeup_interval_us,
            priority=4,
            agent_id="all"
        )
        self.time_engine.schedule_event(next_wakeup)
    
    # ========================================================================
    # INITIALIZATION
    # ========================================================================
    
    def _schedule_agent_wakeups(self):
        """Schedule initial agent wakeup events"""
        first_wakeup = AgentWakeupEvent(
            timestamp=self.time_engine.current_time_us + self.agent_wakeup_interval_us,
            priority=4,
            agent_id="all"
        )
        self.time_engine.schedule_event(first_wakeup)
        logger.info("Scheduled agent wakeups")
    
    # ========================================================================
    # STREAMING
    # ========================================================================
    
    async def _publish_market_update(self, timestamp: int):
        """Publish current market state"""
        market_data = MarketData(
            timestamp=timestamp,
            symbol="BTC/USD",
            last_price=self.current_market_data.last_price,
            bid_price=self.order_book.best_bid,
            ask_price=self.order_book.best_ask,
            bid_size=Decimal(0),  # TODO: aggregate
            ask_size=Decimal(0)
        )
        
        await self.output_stream.publish(market_data)
    
    # ========================================================================
    # CONTROL
    # ========================================================================
    
    async def run(self, duration_seconds: Optional[float] = None):
        """
        Run simulation.
        
        Args:
            duration_seconds: How long to run (None = forever)
        """
        until_time_us = None
        if duration_seconds:
            until_time_us = self.time_engine.current_time_us + int(duration_seconds * 1_000_000)
        
        logger.info("Starting simulation...")
        
        try:
            await self.time_engine.run(until_time_us=until_time_us)
        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        finally:
            await self.shutdown()
    
    def pause(self):
        """Pause simulation"""
        self.time_engine.pause()
    
    def resume(self):
        """Resume simulation"""
        self.time_engine.resume()
    
    def set_speed(self, multiplier: float):
        """Set simulation speed (1.0 = real-time, 0.0 = unlimited)"""
        self.time_engine.set_speed(multiplier)
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down simulation...")
        
        self.time_engine.stop()
        await self.output_stream.close()
        await self.trade_stream.close()
        
        logger.info("Simulation shutdown complete")
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_stats(self) -> dict:
        """Get simulation statistics"""
        return {
            'time_engine': self.time_engine.get_stats().__dict__,
            'order_book': {
                'version': self.order_book._snapshot.version,
                'bids': len(self.order_book._snapshot.bids),
                'asks': len(self.order_book._snapshot.asks),
                'orders': len(self.order_book._snapshot.orders),
                'spread': float(self.order_book.spread) if self.order_book.spread else None,
                'mid_price': float(self.order_book.mid_price) if self.order_book.mid_price else None
            },
            'agents': self.agent_pool.get_all_stats(),
            'streams': {
                'output': self.output_stream.get_stats().__dict__,
                'trades': self.trade_stream.get_stats().__dict__
            }
        }
    
    def get_order_book_depth(self, levels: int = 10) -> dict:
        """Get order book depth snapshot"""
        return self.order_book.get_depth(levels=levels)
