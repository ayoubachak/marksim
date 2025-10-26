"""
WebSocket-focused market simulation.
Demonstrates robust streaming architecture with WebSocket server.
"""
import asyncio
import logging
import argparse
from decimal import Decimal
from pathlib import Path

from .simulation import MarketSimulation
from .agents import MarketMakerAgent, NoiseTraderAgent, InformedTraderAgent, TakerAgent
from .streaming.data_stream import BoundedMarketDataStream, CandleStream
from .streaming.websocket import AsyncWebSocketServer
from .streaming.archiver import RollingDataStore, DataArchiver, MemoryMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_agents_from_args(args):
    """
    Create agents based on command-line arguments.
    """
    agents = []
    
    # Market makers
    for i in range(args.market_makers):
        agents.append(MarketMakerAgent(
            agent_id=f"mm_{i}",
            spread=Decimal(str(args.mm_spread)),
            order_size=Decimal(str(args.mm_order_size)),
            max_position=Decimal(str(args.mm_max_position))
        ))
    
    # Noise traders
    for i in range(args.noise_traders):
        agents.append(NoiseTraderAgent(
            agent_id=f"noise_{i}",
            trade_probability=args.noise_probability,
            max_size=Decimal(str(args.noise_max_size))
        ))
    
    # Informed traders
    for i in range(args.informed_traders):
        agents.append(InformedTraderAgent(
            agent_id=f"informed_{i}",
            bias_probability=args.informed_bias_prob,
            bias_strength=Decimal(str(args.informed_bias_strength)),
            order_size=Decimal(str(args.informed_order_size))
        ))
    
    # Takers (the key to price movement!)
    for i in range(args.takers):
        agents.append(TakerAgent(
            agent_id=f"taker_{i}",
            trade_probability=args.taker_probability,
            price_deviation=args.taker_price_deviation,
            min_size=Decimal(str(args.taker_min_size)),
            max_size=Decimal(str(args.taker_max_size))
        ))
    
    logger.info(f"Created {len(agents)} agents:")
    logger.info(f"  - {args.market_makers} Market Makers (spread: {args.mm_spread}, size: {args.mm_order_size})")
    logger.info(f"  - {args.noise_traders} Noise Traders (prob: {args.noise_probability}, max_size: {args.noise_max_size})")
    logger.info(f"  - {args.informed_traders} Informed Traders (bias_prob: {args.informed_bias_prob}, bias_strength: {args.informed_bias_strength})")
    logger.info(f"  - {args.takers} Takers (prob: {args.taker_probability}, deviation: {args.taker_price_deviation}, size: {args.taker_min_size}-{args.taker_max_size})")
    
    return agents

def apply_config_preset(args):
    """Apply preset configuration based on --config argument"""
    if args.config == 'default':
        # Simple, lightweight default
        args.market_makers = 2
        args.noise_traders = 5
        args.informed_traders = 2
        args.takers = 0
        args.mm_spread = 0.005
        args.mm_order_size = 0.5
        args.noise_probability = 0.05
        args.noise_max_size = 1.0
        
    elif args.config == 'krafer':
        # Krafer's setup: 1000 random traders, zero makers
        args.market_makers = 0
        args.noise_traders = 1000  # 1000 random traders!
        args.informed_traders = 0
        args.takers = 0
        args.noise_probability = 0.01  # Low probability to avoid spam
        args.noise_max_size = 2.0
        
    elif args.config == 'balanced':
        # Balanced market with movement
        args.market_makers = 0
        args.noise_traders = 0
        args.informed_traders = 2
        args.takers = 15
        args.taker_probability = 0.15
        args.taker_min_size = 0.5
        args.taker_max_size = 3.0
        
    # 'custom' uses individual flags as-is
    return args

def parse_arguments():
    """Parse command-line arguments for agent configuration."""
    parser = argparse.ArgumentParser(
        description="Market Simulation with WebSocket Streaming",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Configuration preset
    parser.add_argument(
        '--config',
        choices=['default', 'krafer', 'balanced', 'custom'],
        default='default',
        help='Pre-configured agent setup. Choices: "default" (lightweight), "krafer" (1000 traders like YouTube), "balanced" (dynamic movement), or "custom" (use flags).'
    )
    
    # Agent counts
    parser.add_argument(
        '--market-makers', '-mm',
        type=int,
        default=5,
        help='Number of market maker agents'
    )
    parser.add_argument(
        '--noise-traders', '-nt',
        type=int,
        default=10,
        help='Number of noise trader agents'
    )
    parser.add_argument(
        '--informed-traders', '-it',
        type=int,
        default=3,
        help='Number of informed trader agents'
    )
    parser.add_argument(
        '--takers', '-tk',
        type=int,
        default=0,
        help='Number of taker agents (drives price movement)'
    )
    
    # Market maker configuration
    parser.add_argument(
        '--mm-spread',
        type=float,
        default=0.005,
        help='Market maker spread (as decimal, e.g., 0.005 = 0.5%%)'
    )
    parser.add_argument(
        '--mm-order-size',
        type=float,
        default=0.5,
        help='Market maker order size'
    )
    parser.add_argument(
        '--mm-max-position',
        type=float,
        default=10.0,
        help='Market maker maximum position'
    )
    
    # Noise trader configuration
    parser.add_argument(
        '--noise-probability',
        type=float,
        default=0.05,
        help='Noise trader trade probability (0.0-1.0)'
    )
    parser.add_argument(
        '--noise-max-size',
        type=float,
        default=2.0,
        help='Noise trader maximum order size'
    )
    
    # Informed trader configuration
    parser.add_argument(
        '--informed-bias-prob',
        type=float,
        default=0.3,
        help='Informed trader bias probability (0.0-1.0)'
    )
    parser.add_argument(
        '--informed-bias-strength',
        type=float,
        default=0.02,
        help='Informed trader bias strength (as decimal, e.g., 0.02 = 2%%)'
    )
    parser.add_argument(
        '--informed-order-size',
        type=float,
        default=1.5,
        help='Informed trader order size'
    )
    
    # Taker configuration
    parser.add_argument(
        '--taker-probability',
        type=float,
        default=0.15,
        help='Taker trade probability (0.0-1.0)'
    )
    parser.add_argument(
        '--taker-price-deviation',
        type=float,
        default=0.01,
        help='Taker price deviation from current price (as decimal, e.g., 0.01 = 1%%)'
    )
    parser.add_argument(
        '--taker-min-size',
        type=float,
        default=0.5,
        help='Taker minimum order size'
    )
    parser.add_argument(
        '--taker-max-size',
        type=float,
        default=3.0,
        help='Taker maximum order size'
    )
    
    # Simulation configuration
    parser.add_argument(
        '--initial-price',
        type=float,
        default=50000.0,
        help='Initial market price'
    )
    parser.add_argument(
        '--speed-multiplier',
        type=float,
        default=10.0,
        help='Simulation speed multiplier (1.0 = real-time)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=300,
        help='Simulation duration in seconds'
    )
    parser.add_argument(
        '--wakeup-interval',
        type=int,
        default=100000,
        help='Agent wakeup interval in microseconds'
    )
    
    # WebSocket configuration
    parser.add_argument(
        '--host',
        default='localhost',
        help='WebSocket server host'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8765,
        help='WebSocket server port'
    )
    parser.add_argument(
        '--client-buffer-size',
        type=int,
        default=100,
        help='WebSocket client buffer size'
    )
    
    # Data stream configuration
    parser.add_argument(
        '--stream-buffer-size',
        type=int,
        default=1000,
        help='Market data stream buffer size'
    )
    
    # Archive configuration
    parser.add_argument(
        '--archive-dir',
        default='./archive',
        help='Data archive directory'
    )
    parser.add_argument(
        '--archive-interval',
        type=int,
        default=60,
        help='Archive interval in seconds'
    )
    parser.add_argument(
        '--no-compress',
        action='store_true',
        help='Disable archive compression'
    )
    
    # Memory monitoring
    parser.add_argument(
        '--memory-warning-threshold',
        type=int,
        default=500,
        help='Memory warning threshold in MB'
    )
    parser.add_argument(
        '--memory-check-interval',
        type=int,
        default=10,
        help='Memory check interval in seconds'
    )
    
    # Logging
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    # Candle timeframes
    parser.add_argument(
        '--timeframes',
        nargs='*',  # Changed from '+' to '*' to allow empty list
        default=None,  # Changed from default list to None
        help='Candle timeframes to stream (e.g., 1s 3s 5s 1m 5m 1h). If not specified, all timeframes are enabled.'
    )
    
    return parser.parse_args()

async def run_websocket_simulation(args):
    """
    WebSocket-focused simulation demonstrating robust streaming architecture.
    """
    
    logger.info("=" * 80)
    logger.info("MARKET SIMULATION - WEBSOCKET STREAMING ARCHITECTURE")
    logger.info("=" * 80)
    
    # ========================================================================
    # 1. CREATE AGENTS FROM COMMAND LINE ARGS
    # ========================================================================
    
    logger.info("Creating agents from configuration...")
    agents = create_agents_from_args(args)
    
    # ========================================================================
    # 2. CREATE SHARED STREAMS
    # ========================================================================
    
    logger.info("Setting up data streams...")
    
    # Main market data stream (all consumers share this)
    market_stream = BoundedMarketDataStream(maxsize=args.stream_buffer_size)
    
    # Candle timeframes - generate all common timeframes dynamically
    all_timeframes = [
        # Sub-minute
        '1s', '3s', '5s', '10s', '15s', '30s',
        # Minutes  
        '1m', '3m', '5m', '15m', '30m',
        # Hours
        '1h', '2h', '4h', '6h', '8h', '12h',
        # Days
        '1d', '3d',
        # Weeks/Months
        '1w', '1M'
    ]
    
    # Use provided timeframes or default to all
    selected_timeframes = args.timeframes if args.timeframes else all_timeframes
    
    logger.info(f"Selected timeframes: {selected_timeframes}")
    
    candle_stream = CandleStream(timeframes=selected_timeframes, maxsize=100)
    
    # Rolling data store (fixed memory)
    rolling_store = RollingDataStore(window_size=5000)
    
    # ========================================================================
    # 3. CREATE SIMULATION
    # ========================================================================
    
    logger.info("Creating simulation...")
    
    simulation = MarketSimulation(
        agents=agents,
        initial_price=Decimal(str(args.initial_price)),
        agent_wakeup_interval_us=args.wakeup_interval,
        output_stream=market_stream,
        candle_stream=candle_stream,
        speed_multiplier=args.speed_multiplier
    )
    
    # ========================================================================
    # 4. CREATE WEBSOCKET SERVER
    # ========================================================================
    
    logger.info("Creating WebSocket server...")
    
    websocket_server = AsyncWebSocketServer(
        market_stream=market_stream,
        candle_stream=candle_stream,
        simulation=simulation,
        host=args.host,
        port=args.port,
        client_buffer_size=args.client_buffer_size
    )
    
    # ========================================================================
    # 5. CREATE ARCHIVER & MEMORY MONITOR
    # ========================================================================
    
    logger.info("Creating archiver and memory monitor...")
    
    archiver = DataArchiver(
        rolling_store=rolling_store,
        archive_dir=Path(args.archive_dir),
        archive_interval_seconds=args.archive_interval,
        compress=not args.no_compress
    )
    
    memory_monitor = MemoryMonitor(
        check_interval_seconds=args.memory_check_interval,
        warning_threshold_mb=args.memory_warning_threshold
    )
    
    # ========================================================================
    # 6. CREATE DATA CONSUMER (Feed rolling store)
    # ========================================================================
    
    async def consume_to_rolling_store():
        """Consumer that feeds rolling store"""
        async for market_data in market_stream.subscribe():
            rolling_store.add_market_data(market_data)
            
            # Also store trades
            for trade in market_data.trades:
                rolling_store.add_trade(trade)
    
    async def consume_candles_to_rolling_store():
        """Consumer that feeds candle data to rolling store"""
        for timeframe in selected_timeframes:
            asyncio.create_task(_consume_timeframe_candles(timeframe))
    
    async def _consume_timeframe_candles(timeframe: str):
        """Consume candles for specific timeframe"""
        # Don't store candle data in rolling store - it's not MarketData
        # Candles are already archived through their own stream
        pass
    
    # ========================================================================
    # 7. STATISTICS REPORTER
    # ========================================================================
    
    async def report_statistics():
        """Periodic statistics reporter"""
        while True:
            await asyncio.sleep(10)  # Every 10 seconds
            
            logger.info("\n" + "=" * 80)
            logger.info("WEBSOCKET SIMULATION STATISTICS")
            logger.info("=" * 80)
            
            # Simulation stats
            sim_stats = simulation.get_stats()
            logger.info(f"Time Engine: {sim_stats['time_engine']['events_processed']} events processed")
            logger.info(f"Order Book: {sim_stats['order_book']['orders']} active orders")
            logger.info(f"Spread: ${sim_stats['order_book']['spread']}")
            logger.info(f"Mid Price: ${sim_stats['order_book']['mid_price']}")
            
            # WebSocket stats
            ws_stats = websocket_server.get_stats()
            logger.info(f"WebSocket: {ws_stats['active_clients']} clients, {ws_stats['messages_sent']} messages sent")
            
            # Stream stats
            stream_stats = market_stream.get_stats()
            logger.info(f"Stream: {stream_stats.messages_published} published, {stream_stats.messages_dropped} dropped")
            
            # Archiver stats
            archive_stats = archiver.get_stats()
            logger.info(f"Archiver: {archive_stats['archives_created']} archives, {archive_stats['total_archived_data']} records")
            
            # Memory stats
            memory_stats = memory_monitor.get_stats()
            logger.info(f"Memory: {memory_stats['peak_memory_mb']:.2f} MB peak")
            
            logger.info("=" * 80 + "\n")
    
    # ========================================================================
    # 8. RUN WEBSOCKET SIMULATION
    # ========================================================================
    
    logger.info("\n🚀 Starting WebSocket simulation...")
    logger.info(f"📡 WebSocket server: ws://{args.host}:{args.port}")
    logger.info(f"💾 Data archiver: {args.archive_dir}")
    logger.info("📊 Memory monitor: Active")
    logger.info(f"⚡ Simulation speed: {args.speed_multiplier}x")
    logger.info(f"⏱️  Duration: {args.duration} seconds")
    logger.info(f"💰 Initial price: ${args.initial_price}")
    
    logger.info("\n🔌 Connect WebSocket clients to: ws://{args.host}:{args.port}")
    logger.info("📱 Run Dash consumer: python examples/dash_websocket_consumer.py")
    logger.info("\nPress Ctrl+C to stop\n")
    
    try:
        # Run all tasks concurrently
        await asyncio.gather(
            # Core simulation
            simulation.run(duration_seconds=args.duration),
            
            # WebSocket server
            websocket_server.start(),
            
            # Data archiver
            archiver.start(),
            
            # Rolling store consumer
            consume_to_rolling_store(),
            
            # Candle consumer
            consume_candles_to_rolling_store(),
            
            # Memory monitor
            memory_monitor.start(),
            
            # Statistics reporter
            report_statistics(),
        )
        
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        await simulation.shutdown()
        await websocket_server.shutdown()
        logger.info("WebSocket simulation shutdown complete")

# ============================================================================
# SIMPLE EXAMPLES
# ============================================================================

async def simple_websocket_simulation():
    """Simplest WebSocket simulation"""
    
    logger.info("Running simple WebSocket simulation...")
    
    # Create stream
    stream = BoundedMarketDataStream()
    
    # Create agents
    agents = [
        MarketMakerAgent(f"mm_{i}") for i in range(3)
    ] + [
        NoiseTraderAgent(f"noise_{i}") for i in range(5)
    ]
    
    # Create simulation
    sim = MarketSimulation(
        agents=agents,
        initial_price=Decimal("50000"),
        output_stream=stream,
        speed_multiplier=1.0  # Real-time
    )
    
    # Create WebSocket server
    ws_server = AsyncWebSocketServer(stream, port=8765)
    
    logger.info("WebSocket server on ws://localhost:8765")
    logger.info("Connect with: wscat -c ws://localhost:8765")
    
    # Run both
    try:
        await asyncio.gather(
            sim.run(),
            ws_server.start()
        )
    except KeyboardInterrupt:
        await sim.shutdown()
        await ws_server.shutdown()

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Entry point"""
    
    # Parse command-line arguments
    args = parse_arguments()
    
    # Log configuration preset being used
    logger.info("=" * 80)
    logger.info(f"Using configuration: '{args.config}'")
    if args.config != 'custom':
        logger.info(f"  This preset will override individual agent flags.")
    logger.info("=" * 80)
    
    # Apply configuration preset
    args = apply_config_preset(args)
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Run WebSocket simulation with configuration
    asyncio.run(run_websocket_simulation(args))

if __name__ == "__main__":
    main()