"""
Market Simulation - Batch Mode and WebSocket Modes
"""
import asyncio
import logging
import argparse
from decimal import Decimal
from pathlib import Path

from .simulation import MarketSimulation

from .agents import MarketMakerAgent, NoiseTraderAgent, InformedTraderAgent, TakerAgent
from .streaming.data_stream import BoundedMarketDataStream, CandleStream

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_agents_from_config(agent_configs):
    """
    Create agents from configuration dict.
    Used by API and command line.
    """
    agents = []
    agent_id_counter = 0
    
    for config in agent_configs:
        agent_type = config['type']
        count = config.get('count', 1)
        params = config.get('params', {})
        
        for i in range(count):
            agent_id = f"{agent_type.lower()}_{agent_id_counter}"
            
            if agent_type == 'MarketMaker':
                agent = MarketMakerAgent(
                    agent_id=agent_id,
                    spread=Decimal(str(params.get('spread', 0.01))),
                    order_size=Decimal(str(params.get('order_size', 1.0))),
                    max_position=Decimal(str(params.get('max_position', 10.0)))
                )
            elif agent_type == 'NoiseTrader':
                agent = NoiseTraderAgent(
                    agent_id=agent_id,
                    trade_probability=params.get('trade_probability', 0.1),
                    max_size=Decimal(str(params.get('max_size', 5.0)))
                )
            elif agent_type == 'InformedTrader':
                agent = InformedTraderAgent(
                    agent_id=agent_id,
                    bias_probability=params.get('bias_probability', 0.3),
                    bias_strength=params.get('bias_strength', 0.02),
                    order_size=Decimal(str(params.get('order_size', 2.0)))
                )
            elif agent_type == 'Taker':
                agent = TakerAgent(
                    agent_id=agent_id,
                    trade_probability=params.get('trade_probability', 0.15),
                    price_deviation=params.get('price_deviation', 0.01),
                    min_size=Decimal(str(params.get('min_size', 0.5))),
                    max_size=Decimal(str(params.get('max_size', 3.0)))
                )
            else:
                raise ValueError(f"Unknown agent type: {agent_type}")
            
            agents.append(agent)
            agent_id_counter += 1
    
    return agents

def run_batch_simulation(args):
    """
    Run batch simulation without WebSocket.
    Just compute and exit.
    """
    from .batch_sim import BatchSimulator
    
    logger.info("Running batch simulation (no WebSocket)")
    logger.info(f"Config: {args.config}")
    logger.info(f"Agents: {args.market_makers} MM, {args.noise_traders} Noise, {args.informed_traders} Informed, {args.takers} Takers")
    
    # Create agents
    agents = create_agents_from_args(args)
    
    # Create and run simulator
    simulator = BatchSimulator(
        agents=agents,
        initial_price=Decimal(str(args.initial_price)),
        duration_seconds=args.duration,
        speed_multiplier=args.speed_multiplier
    )
    
    # Run simulation
    result = asyncio.run(simulator.run())
    
    logger.info(f"Batch simulation complete: {result.total_trades} trades")
    logger.info(f"Final price: ${result.final_price}")
    
    # Print results
    print(f"\n{'='*80}")
    print("BATCH SIMULATION RESULTS")
    print(f"{'='*80}")
    print(f"Total trades: {result.total_trades}")
    print(f"Final price: ${result.final_price}")
    print(f"Agent count: {len(result.agent_stats)}")
    
    # TODO: Save results to file or return for API
    
def run_websocket_simulation(args):
    """
    Run simulation with WebSocket server (original behavior).
    """
    from .streaming.websocket import AsyncWebSocketServer
    from .streaming.archiver import RollingDataStore, DataArchiver, MemoryMonitor
    
    logger.info("Running WebSocket simulation")
    
    # Create agents
    agents = create_agents_from_args(args)
    
    # Create streams
    market_stream = BoundedMarketDataStream()
    
    # Define all supported timeframes
    timeframes = [
        '1s', '3s', '5s', '10s', '15s', '30s',
        '1m', '3m', '5m', '15m', '30m',
        '1h', '2h', '4h', '6h', '8h', '12h',
        '1d', '3d', '1w', '1M'
    ]
    
    # Create candle stream with all timeframes
    candle_stream = CandleStream(timeframes=timeframes, maxsize=100)
    
    rolling_store = RollingDataStore(window_size=5000)
    
    # Determine batching preference
    enable_batching = None
    if args.disable_batching:
        enable_batching = False
    elif args.use_batching:
        enable_batching = True
    else:
        total_agents = args.market_makers + args.noise_traders + args.informed_traders + args.takers
        enable_batching = total_agents >= 100
    
    # Create simulation
    simulation = MarketSimulation(
        agents=agents,
        enable_batching=enable_batching,
        initial_price=Decimal(str(args.initial_price)),
        agent_wakeup_interval_us=args.wakeup_interval,
        output_stream=market_stream,
        candle_stream=candle_stream,
        speed_multiplier=args.speed_multiplier
    )
    
    # Create WebSocket server
    websocket_server = AsyncWebSocketServer(
        market_stream=market_stream,
        candle_stream=candle_stream,
        simulation=simulation,
        host=args.host,
        port=args.port
    )
    
    logger.info(f"WebSocket server starting on {args.host}:{args.port}")
    
    # Create a main async function that runs both simulation and server
    async def run_simulation_with_server():
        """Run simulation and WebSocket server concurrently"""
        # Start the simulation in the background
        simulation_task = asyncio.create_task(simulation.run())
        
        # Start the WebSocket server
        await websocket_server.start()
    
    # Run
    asyncio.run(run_simulation_with_server())

def create_agents_from_args(args):
    """Create agents from command-line arguments"""
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
    
    # Takers
    for i in range(args.takers):
        agents.append(TakerAgent(
            agent_id=f"taker_{i}",
            trade_probability=args.taker_probability,
            price_deviation=args.taker_price_deviation,
            min_size=Decimal(str(args.taker_min_size)),
            max_size=Decimal(str(args.taker_max_size))
        ))
    
    logger.info(f"Created {len(agents)} agents")
    return agents

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Market Simulation - Batch or WebSocket Mode",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Mode selection
    parser.add_argument(
        '--mode',
        choices=['batch', 'websocket', 'api'],
        default='batch',
        help='Simulation mode: batch (compute), websocket (live streaming), or api (fastapi server)'
    )
    
    parser.add_argument(
        '--config',
        choices=['default', 'krafer', 'balanced', 'custom'],
        default='default',
        help='Pre-configured agent setup'
    )
    
    # Agent counts
    parser.add_argument('--market-makers', type=int, default=5)
    parser.add_argument('--noise-traders', type=int, default=10)
    parser.add_argument('--informed-traders', type=int, default=3)
    parser.add_argument('--takers', type=int, default=0)
    
    # Agent params
    parser.add_argument('--mm-spread', type=float, default=0.005)
    parser.add_argument('--mm-order-size', type=float, default=0.5)
    parser.add_argument('--mm-max-position', type=float, default=10.0)
    parser.add_argument('--noise-probability', type=float, default=0.05)
    parser.add_argument('--noise-max-size', type=float, default=2.0)
    parser.add_argument('--informed-bias-prob', type=float, default=0.3)
    parser.add_argument('--informed-bias-strength', type=float, default=0.02)
    parser.add_argument('--informed-order-size', type=float, default=1.5)
    parser.add_argument('--taker-probability', type=float, default=0.15)
    parser.add_argument('--taker-price-deviation', type=float, default=0.01)
    parser.add_argument('--taker-min-size', type=float, default=0.5)
    parser.add_argument('--taker-max-size', type=float, default=3.0)
    
    # Simulation params
    parser.add_argument('--initial-price', type=float, default=50000.0)
    parser.add_argument('--duration', type=int, default=60)
    parser.add_argument('--speed-multiplier', type=float, default=1000.0)
    parser.add_argument('--wakeup-interval', type=int, default=100000)
    
    # WebSocket params
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=8765)
    
    # API params
    parser.add_argument('--api-port', type=int, default=5000, help='API server port')
    
    # Performance
    parser.add_argument('--use-batching', action='store_true')
    parser.add_argument('--disable-batching', action='store_true')
    
    return parser.parse_args()

def apply_config_preset(args):
    """Apply config preset"""
    if args.config == 'default':
        args.market_makers = 2
        args.noise_traders = 5
        args.informed_traders = 2
        args.takers = 0
    elif args.config == 'krafer':
        args.market_makers = 2
        args.noise_traders = 1000
        args.informed_traders = 0
        args.takers = 0
        args.noise_probability = 0.01
        args.noise_max_size = 2.0
    elif args.config == 'balanced':
        args.market_makers = 0
        args.noise_traders = 0
        args.informed_traders = 2
        args.takers = 15
        args.taker_probability = 0.15
    return args

def run_api_server(args):
    """
    Run FastAPI server for batch simulations.
    """
    import uvicorn
    from .api.server import app
    
    logger.info(f"Starting API server on {args.host}:{args.api_port}")
    logger.info(f"API docs available at http://{args.host}:{args.api_port}/docs")
    
    uvicorn.run(app, host=args.host, port=args.api_port)

def main():
    """Entry point"""
    args = parse_arguments()
    args = apply_config_preset(args)
    
    logger.info(f"Running in {args.mode} mode")
    
    if args.mode == 'batch':
        run_batch_simulation(args)
    elif args.mode == 'websocket':
        run_websocket_simulation(args)
    elif args.mode == 'api':
        run_api_server(args)
    else:
        logger.error(f"Unknown mode: {args.mode}")

if __name__ == "__main__":
    main()
