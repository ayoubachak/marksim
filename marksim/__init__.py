"""
Realistic Market Simulation Engine

A high-fidelity, event-driven market simulation engine that generates realistic
order book dynamics, price movements, and market microstructure.
"""

__version__ = "2.0.0"
__author__ = "Market Simulation Team"

# Import MarketSimulation - load it on demand to avoid conflicts
# with both simulation.py and simulation/ directory
MarketSimulation = None  # Will be lazy-loaded when needed

from .core.types import Order, Trade, MarketData, OrderType, Side, OrderStatus
from .core.order_book import ImmutableOrderBook
from .core.time_engine import AsyncTimeEngine
from .core.matching_engine import MatchingEngine
from .agents import AsyncAgent, MarketMakerAgent, NoiseTraderAgent, InformedTraderAgent
from .streaming.data_stream import BoundedMarketDataStream
from .streaming.websocket import AsyncWebSocketServer

__all__ = [
    "MarketSimulation",
    "Order",
    "Trade", 
    "MarketData",
    "OrderType",
    "Side",
    "OrderStatus",
    "ImmutableOrderBook",
    "AsyncTimeEngine",
    "MatchingEngine",
    "AsyncAgent",
    "MarketMakerAgent",
    "NoiseTraderAgent", 
    "InformedTraderAgent",
    "BoundedMarketDataStream",
    "AsyncWebSocketServer"
]