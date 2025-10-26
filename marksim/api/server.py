"""
FastAPI server for batch simulation endpoints.

Provides REST API for running simulations on-demand.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio
import logging
from decimal import Decimal

from ..agents import (
    MarketMakerAgent, NoiseTraderAgent,
    InformedTraderAgent, TakerAgent
)
from ..core.matching_engine import MatchingEngine
from ..core.order_book import ImmutableOrderBook
from ..core.types import Order, MarketData
from ..agents.base import AsyncAgentPool
from ..agents.batched_pool import BatchedAgentPool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Market Simulation API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class AgentConfig(BaseModel):
    type: str
    count: int
    params: Dict[str, float] = {}

class SimulationRequest(BaseModel):
    agents: List[AgentConfig]
    duration_seconds: int = 60
    initial_price: float = 50000

class SimulationResponse(BaseModel):
    trades: List[Dict]
    orderbook_states: List[Dict]
    agent_stats: List[Dict]
    final_price: float
    total_trades: int

def create_agents_from_config(agent_configs: List[AgentConfig]):
    """Create agents from configuration"""
    agents = []
    agent_id = 0
    
    for config in agent_configs:
        agent_type = config.type
        count = config.count
        params = config.params
        
        for i in range(count):
            agent_id_str = f"{agent_type.lower()}_{agent_id}"
            
            if agent_type == 'MarketMaker':
                agent = MarketMakerAgent(
                    agent_id=agent_id_str,
                    spread=Decimal(str(params.get('spread', 0.01))),
                    order_size=Decimal(str(params.get('order_size', 1.0))),
                    max_position=Decimal(str(params.get('max_position', 10.0)))
                )
            elif agent_type == 'NoiseTrader':
                agent = NoiseTraderAgent(
                    agent_id=agent_id_str,
                    trade_probability=params.get('trade_probability', 0.1),
                    max_size=Decimal(str(params.get('max_size', 5.0)))
                )
            elif agent_type == 'InformedTrader':
                agent = InformedTraderAgent(
                    agent_id=agent_id_str,
                    bias_probability=params.get('bias_probability', 0.3),
                    bias_strength=params.get('bias_strength', 0.02),
                    order_size=Decimal(str(params.get('order_size', 2.0)))
                )
            elif agent_type == 'Taker':
                agent = TakerAgent(
                    agent_id=agent_id_str,
                    trade_probability=params.get('trade_probability', 0.15),
                    price_deviation=params.get('price_deviation', 0.01),
                    min_size=Decimal(str(params.get('min_size', 0.5))),
                    max_size=Decimal(str(params.get('max_size', 3.0)))
                )
            else:
                raise ValueError(f'Unknown agent type: {agent_type}')
            
            agents.append(agent)
            agent_id += 1
    
    return agents

@app.get("/")
def root():
    """API root"""
    return {
        "message": "Market Simulation API",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
def health():
    """Health check"""
    return {"status": "ok"}

@app.post("/api/simulation/run", response_model=SimulationResponse)
async def run_simulation(request: SimulationRequest):
    """Run batch simulation and return results"""
    try:
        logger.info(f"Running simulation: {len(request.agents)} agent types, {request.duration_seconds}s")
        
        # Create agents
        agents = create_agents_from_config(request.agents)
        logger.info(f"Created {len(agents)} agents")
        
        # Run simulation
        result = await run_batch_simulation(
            agents, 
            Decimal(str(request.initial_price)), 
            request.duration_seconds
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Simulation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def run_batch_simulation(agents, initial_price, duration_seconds):
    """Run batch simulation and return all data"""
    
    # Use batched pool if 100+ agents
    use_batching = len(agents) >= 100
    
    if use_batching:
        logger.info("Using batched pool for performance")
        agent_pool = BatchedAgentPool(agents, enable_batching=True)
    else:
        agent_pool = AsyncAgentPool(agents, max_concurrency=100)
    
    order_book = ImmutableOrderBook()
    matching_engine = MatchingEngine()
    
    trades = []
    order_book_states = []
    current_price = initial_price
    
    # Adaptive step size based on duration and agent count
    # Formula: Larger steps for longer durations with fewer agents
    total_steps = duration_seconds * 10  # Target ~10 steps per second
    step_us = (duration_seconds * 1_000_000) // max(total_steps, 100)
    
    # Clamp step size between 10ms and 1s
    step_us = max(10_000, min(step_us, 1_000_000))
    
    logger.info(f"Step size: {step_us / 1_000}ms, Duration: {duration_seconds}s, Agents: {len(agents)}")
    
    # Scale agent probabilities based on duration and agent count
    # Longer durations with fewer agents = higher probabilities to ensure liquidity
    agent_multiplier = max(1.0, duration_seconds / max(len(agents), 1) / 10.0)
    
    # Apply probability scaling to agents
    for agent in agents:
        if hasattr(agent, 'trade_probability'):
            # Scale trade probability based on market conditions
            agent.trade_probability *= min(agent_multiplier, 5.0)  # Cap at 5x
        if hasattr(agent, 'order_size'):
            # Ensure minimum order size for liquidity
            agent.order_size = max(agent.order_size, Decimal('0.1'))
    
    # Simulate
    end_time = duration_seconds * 1_000_000  # microseconds
    current_time = 0
    progress_checkpoint = 0
    
    while current_time < end_time:
        # Log progress every 10%
        progress = (current_time / end_time) * 100
        if progress >= progress_checkpoint:
            logger.info(f"Simulation progress: {progress:.0f}% ({len(trades)} trades so far)")
            progress_checkpoint += 10
        # Create market data
        market_data = MarketData(
            timestamp=current_time,
            symbol="BTC/USD",
            last_price=order_book.mid_price or current_price,
            volume_24h=Decimal(0),
            trades=[]
        )
        
        # Generate orders
        orders = await agent_pool.generate_all_orders(market_data, order_book)
        
        # Process orders
        for order in orders:
            new_book, match_result = matching_engine.match_order(
                order, order_book, current_time
            )
            order_book = new_book
            
            if match_result.trades:
                for trade in match_result.trades:
                    trades.append({
                        'trade_id': trade.trade_id,
                        'timestamp': trade.timestamp,
                        'price': float(trade.price),
                        'size': float(trade.size),
                        'buy_order_id': trade.buy_order_id,
                        'sell_order_id': trade.sell_order_id
                    })
        
        # Store order book state every second
        if current_time % 1_000_000 == 0:
            depth = order_book.get_depth(levels=20)
            order_book_states.append({
                'timestamp': current_time,
                'bids': depth['bids'],
                'asks': depth['asks'],
                'spread': depth['spread'],
                'mid_price': depth['mid_price']
            })
        
        current_time += step_us
    
    # Get agent stats
    agent_stats = [agent.get_stats() for agent in agents]
    
    logger.info(f"Simulation complete: {len(trades)} trades, Final price: ${float(order_book.mid_price or initial_price):.2f}")
    
    return SimulationResponse(
        trades=trades,
        orderbook_states=order_book_states,
        agent_stats=agent_stats,
        final_price=float(order_book.mid_price or initial_price),
        total_trades=len(trades)
    )

