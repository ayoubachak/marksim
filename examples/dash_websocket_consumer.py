"""
Example: Dash WebSocket Consumer
Demonstrates decoupled architecture - Dash consumes from WebSocket stream.
"""
import asyncio
import logging
from pathlib import Path
import sys

# Add parent directory to path to import marksim
sys.path.append(str(Path(__file__).parent.parent))

from marksim.visualization.websocket_consumer import DashWebSocketConsumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_dash_websocket_consumer():
    """
    Run Dash dashboard as a pure WebSocket consumer.
    This demonstrates the decoupled architecture.
    """
    
    logger.info("=" * 80)
    logger.info("DASH WEBSOCKET CONSUMER EXAMPLE")
    logger.info("=" * 80)
    
    # Create WebSocket consumer
    dash_consumer = DashWebSocketConsumer(
        websocket_url='ws://localhost:8765',
        max_points=1000,
        update_interval_ms=100
    )
    
    # Connect to WebSocket
    connected = await dash_consumer.connect_to_websocket()
    if not connected:
        logger.error("Failed to connect to WebSocket. Make sure the simulation is running.")
        logger.error("Run: python -m marksim.main")
        return
    
    logger.info("✅ Connected to WebSocket stream")
    logger.info("🌐 Starting Dash dashboard on http://localhost:8050")
    logger.info("📊 Dashboard will consume market data from WebSocket")
    logger.info("\nPress Ctrl+C to stop\n")
    
    try:
        # Run WebSocket consumer and Dash server concurrently
        await asyncio.gather(
            # WebSocket consumer (background task)
            dash_consumer.consume_websocket_stream(),
            
            # Dash server (in executor because it's Flask-based)
            asyncio.get_event_loop().run_in_executor(
                None,
                dash_consumer.run_server,
                '127.0.0.1',
                8050,
                False
            )
        )
        
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Disconnecting from WebSocket...")
        await dash_consumer.disconnect()
        logger.info("Dash WebSocket consumer shutdown complete")

def main():
    """Entry point"""
    asyncio.run(run_dash_websocket_consumer())

if __name__ == "__main__":
    main()


