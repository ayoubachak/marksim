"""
Pure asyncio WebSocket server (no threading).
Each client gets independent buffered stream.
"""
import asyncio
import json
import websockets
from typing import Set, Dict, Optional
import logging

from .data_stream import BoundedMarketDataStream, CandleData
from ..core.types import MarketData, Order

logger = logging.getLogger(__name__)

class AsyncWebSocketServer:
    """
    WebSocket server for streaming market data.
    
    Architecture:
    - Each client gets independent bridge tasks for all streams
    - Market data and all timeframe candles are sent concurrently
    - Client-side filtering handles timeframe selection
    - No subscription management needed (sends everything by default)
    
    Stream Flow:
    1. Simulation publishes to shared market_stream and candle_stream
    2. This server subscribes to those streams
    3. Each client connection creates bridge tasks that forward messages
    4. Messages are serialized and sent directly to WebSocket
    """
    
    def __init__(
        self,
        market_stream: BoundedMarketDataStream,
        candle_stream: Optional['CandleStream'] = None,
        simulation: Optional['MarketSimulation'] = None,
        host: str = 'localhost',
        port: int = 8765,
        client_buffer_size: int = 100
    ):
        self.market_stream = market_stream
        self.candle_stream = candle_stream
        self.simulation = simulation
        self.host = host
        self.port = port
        self.client_buffer_size = client_buffer_size
        
        # Client management
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.client_tasks: Dict[websockets.WebSocketServerProtocol, asyncio.Task] = {}
        
        # Stats
        self.total_connections = 0
        self.messages_sent = 0
        
        logger.info(f"WebSocket server initialized on {host}:{port}")
    
    # ========================================================================
    # CONNECTION HANDLER
    # ========================================================================
    
    async def handler(self, websocket):
        """Handle individual client connection"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"Client connected: {client_id}")
        
        self.clients.add(websocket)
        self.total_connections += 1
        
        # Start message handler for client commands
        message_task = asyncio.create_task(
            self._handle_client_messages(websocket, client_id)
        )
        
        # Start bridging all streams to this client
        bridge_tasks = []
        
        # Bridge market data (always active)
        market_task = asyncio.create_task(
            self._bridge_market_stream(websocket, client_id)
        )
        bridge_tasks.append(market_task)
        
        # Bridge candle streams for all timeframes (always active)
        # Note: Client-side filtering by timeframe is handled in HTML client
        if self.candle_stream:
            for timeframe in self.candle_stream.timeframes:
                candle_task = asyncio.create_task(
                    self._bridge_candle_stream(websocket, timeframe, client_id)
                )
                bridge_tasks.append(candle_task)
        
        # Bridge orderbook updates if simulation is available
        if self.simulation:
            orderbook_task = asyncio.create_task(
                self._bridge_orderbook_stream(websocket, client_id)
            )
            bridge_tasks.append(orderbook_task)
            
            # Bridge agent configurations
            config_task = asyncio.create_task(
                self._bridge_agent_config_stream(websocket, client_id)
            )
            bridge_tasks.append(config_task)
        
        try:
            # Wait for bridge tasks to complete
            await asyncio.gather(message_task, *bridge_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info(f"Client handler cancelled: {client_id}")
        except Exception as e:
            logger.error(f"Client error {client_id}: {e}", exc_info=True)
        finally:
            # Cleanup
            message_task.cancel()
            for task in bridge_tasks:
                task.cancel()
            
            self.clients.discard(websocket)
            if websocket in self.client_tasks:
                del self.client_tasks[websocket]
            
            logger.info(f"Client cleaned up: {client_id}")
    
    async def _handle_client_messages(self, websocket, client_id: str):
        """Handle incoming messages from client"""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._process_client_command(websocket, data, client_id)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from client {client_id}")
                except Exception as e:
                    logger.error(f"Error processing message from {client_id}: {e}", exc_info=True)
        except websockets.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except asyncio.CancelledError:
            logger.info(f"Message handler cancelled for {client_id}")
    
    async def _process_client_command(self, websocket, data: dict, client_id: str):
        """Process agent management commands"""
        if data.get('type') == 'agent_command' and self.simulation:
            action = data.get('action')
            
            if action == 'create':
                agent_type = data.get('agent_type')
                config = data.get('config', {})
                agent_id = self.simulation.add_agent(agent_type, config)
                
                # Send confirmation
                await websocket.send(json.dumps({
                    'type': 'agent_response',
                    'action': 'created',
                    'agent_id': agent_id,
                    'success': True
                }))
                
                # Send updated agent configs
                await self._send_agent_configs_update(websocket)
                
            elif action == 'delete':
                agent_id = data.get('agent_id')
                success = self.simulation.remove_agent(agent_id)
                
                await websocket.send(json.dumps({
                    'type': 'agent_response',
                    'action': 'deleted',
                    'agent_id': agent_id,
                    'success': success
                }))
                
                # Send updated agent configs if successful
                if success:
                    await self._send_agent_configs_update(websocket)
                
            elif action == 'update':
                agent_id = data.get('agent_id')
                config = data.get('config', {})
                success = self.simulation.update_agent(agent_id, config)
                
                await websocket.send(json.dumps({
                    'type': 'agent_response',
                    'action': 'updated',
                    'agent_id': agent_id,
                    'success': success
                }))
                
                # Send updated agent configs if successful
                if success:
                    await self._send_agent_configs_update(websocket)
    
    async def _bridge_market_stream(self, websocket, client_id: str):
        """Bridge market data stream directly to WebSocket client"""
        try:
            logger.info(f"Starting market data bridge for client {client_id}")
            async for market_data in self.market_stream.subscribe():
                try:
                    message = self._serialize_market_data(market_data)
                    await websocket.send(message)
                    self.messages_sent += 1
                except websockets.ConnectionClosed:
                    logger.info(f"Client {client_id} disconnected during market data bridge")
                    break
                    
        except asyncio.CancelledError:
            logger.debug(f"Market data bridge cancelled for client {client_id}")
        except Exception as e:
            logger.error(f"Market data bridge error for client {client_id}: {e}", exc_info=True)
    
    async def _bridge_candle_stream(self, websocket, timeframe: str, client_id: str):
        """Bridge candle stream for specific timeframe"""
        try:
            logger.debug(f"Starting candle bridge for {timeframe} to client {client_id}")
            async for candle_data in self.candle_stream.subscribe(timeframe):
                # Handle proper CandleData model
                if isinstance(candle_data, CandleData):
                    logger.debug(f"Processing CandleData for {timeframe}: closed={candle_data.is_closed}, seq={candle_data.sequence_id}")
                    # Serialize candle data in Binance format
                    candle_message = self._serialize_candle_data(candle_data)
                    
                    try:
                        await websocket.send(candle_message)
                        self.messages_sent += 1
                        logger.debug(f"Published candle data for {timeframe} to client {client_id}")
                    except websockets.ConnectionClosed:
                        logger.info(f"Client {client_id} disconnected during candle bridge")
                        break
                else:
                    logger.warning(f"Received non-CandleData object: type={type(candle_data)}, value={candle_data}")
                    
        except asyncio.CancelledError:
            logger.info(f"Candle bridge cancelled for {timeframe} client {client_id}")
        except Exception as e:
            logger.error(f"Candle bridge error for {timeframe} client {client_id}: {e}", exc_info=True)
    
    async def _bridge_orderbook_stream(self, websocket, client_id: str):
        """Bridge order book updates to client"""
        try:
            logger.debug(f"Starting orderbook bridge for client {client_id}")
            last_version = -1
            
            while True:
                await asyncio.sleep(0.1)  # Update every 100ms
                
                if not self.simulation:
                    continue
                
                order_book = self.simulation.order_book
                if order_book and order_book._snapshot.version != last_version:
                    last_version = order_book._snapshot.version
                    
                    # Get depth snapshot
                    depth = order_book.get_depth(levels=10)
                    
                    # Serialize and send
                    message = json.dumps({
                        'type': 'orderbook',
                        'bids': depth['bids'],
                        'asks': depth['asks'],
                        'spread': depth['spread'],
                        'mid_price': depth['mid_price'],
                        'timestamp': self.simulation.time_engine.current_time_us // 1000
                    })
                    
                    try:
                        await websocket.send(message)
                    except websockets.ConnectionClosed:
                        logger.info(f"Client {client_id} disconnected during orderbook bridge")
                        break
                        
        except asyncio.CancelledError:
            logger.info(f"Orderbook bridge cancelled for client {client_id}")
        except Exception as e:
            logger.error(f"Orderbook bridge error for client {client_id}: {e}", exc_info=True)
    
    async def _bridge_agent_config_stream(self, websocket, client_id: str):
        """Bridge agent configurations to client"""
        try:
            logger.debug(f"Starting agent config bridge for client {client_id}")
            
            # Send initial agent configurations
            if self.simulation:
                configs = self.simulation.agent_pool.get_all_configs()
                message = json.dumps({
                    'type': 'agent_configs',
                    'configs': configs
                })
                await websocket.send(message)
                logger.debug(f"Sent initial agent configs ({len(configs)} agents) to {client_id}")
                
        except asyncio.CancelledError:
            logger.info(f"Agent config bridge cancelled for client {client_id}")
        except Exception as e:
            logger.error(f"Agent config bridge error for client {client_id}: {e}", exc_info=True)
    
    async def _send_agent_configs_update(self, websocket):
        """Send current agent configs to specific client"""
        if not self.simulation:
            return
            
        try:
            configs = self.simulation.agent_pool.get_all_configs()
            message = json.dumps({
                'type': 'agent_configs',
                'configs': configs
            })
            await websocket.send(message)
            logger.debug(f"Sent agent configs update ({len(configs)} agents)")
        except Exception as e:
            logger.error(f"Error sending agent configs update: {e}", exc_info=True)
    
    # ========================================================================
    # SERIALIZATION
    # ========================================================================
    
    def _serialize_market_data(self, market_data: MarketData) -> str:
        """Serialize market data to JSON"""
        return json.dumps({
            'type': 'market_data',
            'timestamp': market_data.timestamp,
            'symbol': market_data.symbol,
            'last_price': float(market_data.last_price) if market_data.last_price else None,
            'bid_price': float(market_data.bid_price) if market_data.bid_price else None,
            'ask_price': float(market_data.ask_price) if market_data.ask_price else None,
            'bid_size': float(market_data.bid_size) if market_data.bid_size else None,
            'ask_size': float(market_data.ask_size) if market_data.ask_size else None,
            'volume_24h': float(market_data.volume_24h),
            'trade_count': len(market_data.trades)
        })
    
    def _serialize_candle_data(self, candle_data) -> str:
        """Serialize candle data to JSON (Binance-style)"""
        candle = candle_data.candle
        timeframe = candle_data.timeframe
        is_closed = candle_data.is_closed
        sequence_id = candle_data.sequence_id
        
        # Convert Decimals to float for JSON serialization
        volume = float(candle.volume)
        close = float(candle.close)
        
        # Convert microseconds to milliseconds for timestamps
        timestamp_ms = candle.timestamp // 1000
        timeframe_ms = self._get_timeframe_ms(timeframe)
        
        return json.dumps({
            'e': 'kline',  # Event type (like Binance)
            'E': timestamp_ms,  # Event time (milliseconds)
            's': 'BTC/USD',  # Symbol
            'k': {
                't': timestamp_ms,  # Kline start time (milliseconds)
                'T': timestamp_ms + timeframe_ms,  # Kline close time (milliseconds)
                's': 'BTC/USD',  # Symbol
                'i': timeframe,  # Interval
                'f': sequence_id,  # First trade ID (using sequence ID)
                'L': sequence_id,  # Last trade ID (using sequence ID)
                'o': float(candle.open),  # Open price
                'c': close,  # Close price
                'h': float(candle.high),  # High price
                'l': float(candle.low),  # Low price
                'v': volume,  # Volume
                'n': candle.trade_count,  # Number of trades
                'x': is_closed,  # Is this kline closed? (like Binance)
                'q': volume * close,  # Quote asset volume
                'V': volume * 0.5,  # Taker buy base asset volume (more realistic estimate)
                'Q': volume * close * 0.5,  # Taker buy quote asset volume (more realistic estimate)
                'B': '0'  # Ignore
            }
        })
    
    def _get_timeframe_ms(self, timeframe: str) -> int:
        """Convert timeframe to milliseconds"""
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        
        multipliers = {'s': 1000, 'm': 60*1000, 'h': 3600*1000, 'd': 86400*1000}
        return value * multipliers.get(unit, 60*1000)
    
    # ========================================================================
    # SERVER CONTROL
    # ========================================================================
    
    async def start(self):
        """Start WebSocket server"""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        
        async with websockets.serve(self.handler, self.host, self.port):
            logger.info("WebSocket server running")
            await asyncio.Future()  # Run forever
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down WebSocket server...")
        
        # Cancel all client tasks
        for task in self.client_tasks.values():
            task.cancel()
        
        # Close all connections
        close_tasks = [ws.close() for ws in self.clients]
        await asyncio.gather(*close_tasks, return_exceptions=True)
        
        self.clients.clear()
        self.client_tasks.clear()
        
        logger.info("WebSocket server shutdown complete")
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_stats(self) -> dict:
        """Get server statistics"""
        return {
            'active_clients': len(self.clients),
            'total_connections': self.total_connections,
            'messages_sent': self.messages_sent,
            'stream_stats': self.market_stream.get_stats().__dict__
        }
    
    async def broadcast_message(self, message: str):
        """Broadcast custom message to all clients"""
        if not self.clients:
            return
        
        tasks = [ws.send(message) for ws in self.clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Broadcast error to client: {result}")
