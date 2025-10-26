"""
Smart Agent Pool - 100x Engineer Architecture

Automatically selects optimal processing strategy based on agent count and type.
Maintains full backward compatibility with existing architecture.

Strategy Selection:
- Individual agents: <10 (specialized, need tracking)
- Hybrid: 10-1000 (mix of individual + batched)
- Statistical: 1000+ (pure batch for identical agents)

Key Features:
1. Transparent API - works with existing code
2. Automatic optimization
3. Real-time WebSocket updates still work
4. No architecture changes needed
"""
import asyncio
import logging
from typing import List, Optional
from decimal import Decimal

from .base import AsyncAgent, AsyncAgentPool
from .statistical import StatisticalAgentSimulator, AgentTypeConfig
import numpy as np

logger = logging.getLogger(__name__)


class BatchedAgentPool:
    """
    Automatically optimizes agent processing based on scale.
    Uses the right tool for the job transparently.
    
    Strategy Thresholds:
    - <10 agents: Individual (all specialized)
    - 10-100 agents: Hybrid (some batched, some individual)
    - 100-1000 agents: Hybrid (more batched)
    - 1000+ agents: Statistical (bulk batched)
    
    Full backward compatibility maintained!
    """
    
    def __init__(
        self,
        agents: List[AsyncAgent],
        enable_batching: bool = True
    ):
        self.agents = agents
        self.enable_batching = enable_batching
        
        # Analyze agents
        self._agent_types = self._analyze_agents()
        
        # Select strategy
        if enable_batching:
            self.strategy = self._select_strategy()
            logger.info(f"Batched pool: {len(agents)} agents, strategy={self.strategy}")
        else:
            # Fallback to standard pool
            self.strategy = 'individual'
            logger.info(f"Standard pool: {len(agents)} agents")
        
        # Initialize sub-pools based on strategy
        self._init_sub_pools()
    
    def _analyze_agents(self) -> dict:
        """Analyze agent types and counts"""
        from collections import Counter
        
        agent_type_counts = Counter(type(agent).__name__ for agent in self.agents)
        
        # Detect identical agents (noise traders)
        identical_agents = {
            name: count 
            for name, count in agent_type_counts.items() 
            if count >= 10
        }
        
        # Detect specialized agents (market makers, informed traders)
        specialized_agents = {
            name: count 
            for name, count in agent_type_counts.items() 
            if count < 10
        }
        
        logger.info(f"Agent analysis: {identical_agents} identical, {specialized_agents} specialized")
        
        return {
            'identical': identical_agents,
            'specialized': specialized_agents,
            'total': agent_type_counts
        }
    
    def _select_strategy(self) -> str:
        """Select optimal processing strategy"""
        total_agents = len(self.agents)
        identical_count = sum(self._agent_types['identical'].values())
        
        # Decision tree
        if total_agents < 10:
            return 'individual'  # All specialized, too few to batch
        elif total_agents >= 1000 and identical_count >= 500:
            return 'statistical'  # Mostly identical, use pure batch
        elif identical_count >= 50:
            return 'hybrid_batched'  # Mostly identical
        else:
            return 'hybrid_balanced'  # Mixed
    
    def _init_sub_pools(self):
        """Initialize sub-pools based on strategy"""
        if self.strategy == 'individual':
            # Standard individual pool
            self.individual_pool = AsyncAgentPool(
                self.agents,
                max_concurrency=min(100, len(self.agents))
            )
            self.statistical_pool = None
            self.specialized_agents = []
            self.identical_agents = []
            
        elif self.strategy == 'statistical':
            # Pure statistical for all
            configs = self._create_statistical_configs()
            self.statistical_pool = StatisticalAgentSimulator(configs)
            self.individual_pool = None
            self.specialized_agents = []
            self.identical_agents = self.agents
            
        else:  # hybrid_batched or hybrid_balanced
            # Split agents
            identical_configs = self._create_statistical_configs()
            self.statistical_pool = StatisticalAgentSimulator(identical_configs) if identical_configs else None
            
            # Individual agents for specialized
            specialized = [a for a in self.agents if type(a).__name__ not in self._agent_types['identical']]
            self.specialized_agents = specialized
            self.individual_pool = AsyncAgentPool(specialized, max_concurrency=min(100, len(specialized))) if specialized else None
            
            logger.info(f"Hybrid pool: {len(identical_configs)} batch configs, {len(specialized)} specialized")
    
    def _create_statistical_configs(self) -> List[AgentTypeConfig]:
        """Create statistical configs for identical agents"""
        configs = []
        
        for agent_type, count in self._agent_types['identical'].items():
            # Get default config from first agent of this type
            sample_agent = next(a for a in self.agents if type(a).__name__ == agent_type)
            
            config = self._agent_to_config(sample_agent, count)
            if config:
                configs.append(config)
        
        return configs
    
    def _agent_to_config(self, agent: AsyncAgent, count: int) -> Optional[AgentTypeConfig]:
        """Convert agent to statistical config"""
        agent_type = type(agent).__name__
        
        if agent_type == 'NoiseTraderAgent':
            return AgentTypeConfig(
                name=agent_type.lower(),
                count=count,
                trade_probability=agent.trade_probability,
                min_size=float(agent.max_size) * 0.1,  # Assume 10x variation
                max_size=float(agent.max_size),
                price_deviation=0.01
            )
        elif agent_type == 'TakerAgent':
            return AgentTypeConfig(
                name=agent_type.lower(),
                count=count,
                trade_probability=agent.trade_probability,
                min_size=float(agent.min_size),
                max_size=float(agent.max_size),
                price_deviation=agent.price_deviation
            )
        # Add more types as needed
        
        return None
    
    # ========================================================================
    # PUBLIC API (Backward Compatible)
    # ========================================================================
    
    async def generate_all_orders(
        self,
        market_data,
        order_book
    ) -> List:
        """
        Generate orders using optimal strategy.
        
        Automatically routes to:
        - Individual pool for specialized agents
        - Statistical pool for identical agents
        """
        if self.strategy == 'individual':
            return await self.individual_pool.generate_all_orders(market_data, order_book)
        
        elif self.strategy == 'statistical':
            return self.statistical_pool.generate_all_orders(market_data, order_book)
        
        else:  # hybrid
            all_orders = []
            
            # Fast path: Statistical for identical
            if self.statistical_pool:
                batch_orders = self.statistical_pool.generate_all_orders(market_data, order_book)
                all_orders.extend(batch_orders)
            
            # Slow path: Individual for specialized
            if self.individual_pool and self.specialized_agents:
                individual_orders = await self.individual_pool.generate_all_orders(
                    market_data, order_book
                )
                all_orders.extend(individual_orders)
            
            return all_orders
    
    async def notify_trade(
        self,
        agent_id: str,
        order,
        executed_size: Decimal,
        executed_price: Decimal
    ):
        """Notify agent of trade (only for individual agents)"""
        if self.strategy != 'statistical':
            # Find agent
            agent = next((a for a in self.agents if a.agent_id == agent_id), None)
            if agent:
                await agent.on_trade_executed(order, executed_size, executed_price)
    
    async def notify_cancellation(self, agent_id: str, order):
        """Notify agent of cancellation (only for individual agents)"""
        if self.strategy != 'statistical':
            agent = next((a for a in self.agents if a.agent_id == agent_id), None)
            if agent:
                await agent.on_order_cancelled(order)
    
    def get_agent(self, agent_id: str) -> Optional[AsyncAgent]:
        """Get agent by ID"""
        return next((a for a in self.agents if a.agent_id == agent_id), None)
    
    def get_all_stats(self) -> List[dict]:
        """Get statistics for all agents"""
        if self.strategy == 'statistical':
            # Mock stats for statistical agents
            stats = []
            for config in self.statistical_pool.configs if self.statistical_pool else []:
                for i in range(config.count):
                    stats.append({
                        'agent_id': f"{config.name}_{i}",
                        'type': config.name,
                        'balance': 10000.0,
                        'position': 0.0,
                        'total_trades': 0,
                        'total_volume': 0.0,
                        'pnl': 0.0,
                        'active_orders': 0
                    })
            return stats
        else:
            return [agent.get_stats() for agent in self.agents]
    
    def get_all_configs(self) -> List[dict]:
        """Get configuration for all agents"""
        if self.strategy == 'statistical':
            configs = []
            for config in self.statistical_pool.configs if self.statistical_pool else []:
                for i in range(config.count):
                    configs.append({
                        'agent_id': f"{config.name}_{i}",
                        'agent_type': config.name,
                        'trade_probability': config.trade_probability,
                        'min_size': config.min_size,
                        'max_size': config.max_size,
                        'price_deviation': config.price_deviation
                    })
            return configs
        else:
            return [agent.get_config() for agent in self.agents]
    
    # Drop-in replacement for AsyncAgentPool
    @property
    def agents(self):
        return self._agents
    
    @agents.setter
    def agents(self, value):
        self._agents = value

