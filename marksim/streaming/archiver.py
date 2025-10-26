"""
Automated memory management and data archiving.
Prevents unbounded memory growth.
"""
import asyncio
from collections import deque
from typing import Deque, Optional
import logging
from pathlib import Path
import json
from datetime import datetime

from .data_stream import BoundedMarketDataStream
from ..core.types import MarketData, Trade

logger = logging.getLogger(__name__)

class RollingDataStore:
    """
    Fixed-size rolling window data store.
    Old data automatically evicted.
    """
    
    def __init__(self, window_size: int = 10000):
        self.window_size = window_size
        
        # Rolling windows
        self.market_data: Deque[MarketData] = deque(maxlen=window_size)
        self.trades: Deque[Trade] = deque(maxlen=window_size)
        
        # Stats
        self.total_market_data = 0
        self.total_trades = 0
        self.evicted_market_data = 0
        self.evicted_trades = 0
    
    def add_market_data(self, data: MarketData):
        """Add market data (auto-evicts oldest)"""
        if len(self.market_data) >= self.window_size:
            self.evicted_market_data += 1
        
        self.market_data.append(data)
        self.total_market_data += 1
    
    def add_trade(self, trade: Trade):
        """Add trade (auto-evicts oldest)"""
        if len(self.trades) >= self.window_size:
            self.evicted_trades += 1
        
        self.trades.append(trade)
        self.total_trades += 1
    
    def get_recent_market_data(self, count: int = 100):
        """Get most recent market data"""
        return list(self.market_data)[-count:]
    
    def get_recent_trades(self, count: int = 100):
        """Get most recent trades"""
        return list(self.trades)[-count:]
    
    def get_stats(self) -> dict:
        """Get statistics"""
        return {
            'window_size': self.window_size,
            'market_data_count': len(self.market_data),
            'trades_count': len(self.trades),
            'total_market_data': self.total_market_data,
            'total_trades': self.total_trades,
            'evicted_market_data': self.evicted_market_data,
            'evicted_trades': self.evicted_trades
        }

class DataArchiver:
    """
    Periodic archiver that writes old data to disk.
    Prevents memory exhaustion in long-running simulations.
    """
    
    def __init__(
        self,
        rolling_store: RollingDataStore,
        archive_dir: Path = Path("./archive"),
        archive_interval_seconds: int = 60,
        compress: bool = True
    ):
        self.rolling_store = rolling_store
        self.archive_dir = archive_dir
        self.archive_interval = archive_interval_seconds
        self.compress = compress
        
        # Create archive directory
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats
        self.archives_created = 0
        self.total_archived_data = 0
        
        logger.info(f"Data archiver initialized (dir: {archive_dir})")
    
    async def start(self):
        """Start periodic archiving"""
        logger.info("Starting data archiver")
        
        try:
            while True:
                await asyncio.sleep(self.archive_interval)
                await self._archive_old_data()
                
        except asyncio.CancelledError:
            logger.info("Data archiver stopped")
    
    async def _archive_old_data(self):
        """Archive old data to disk"""
        try:
            # Get data to archive (oldest 50%)
            market_data_count = len(self.rolling_store.market_data)
            trades_count = len(self.rolling_store.trades)
            
            if market_data_count < 100 and trades_count < 100:
                return  # Not enough data to archive
            
            # Extract data
            archive_market_data = list(self.rolling_store.market_data)[:market_data_count // 2]
            archive_trades = list(self.rolling_store.trades)[:trades_count // 2]
            
            # Write to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.archive_dir / f"archive_{timestamp}.json"
            
            archive_data = {
                'timestamp': timestamp,
                'market_data': [self._serialize_market_data(md) for md in archive_market_data],
                'trades': [self._serialize_trade(t) for t in archive_trades]
            }
            
            with open(filename, 'w') as f:
                json.dump(archive_data, f, indent=2 if not self.compress else None)
            
            # Update stats
            self.archives_created += 1
            self.total_archived_data += len(archive_market_data) + len(archive_trades)
            
            logger.info(
                f"Archived {len(archive_market_data)} market data, "
                f"{len(archive_trades)} trades to {filename}"
            )
            
        except Exception as e:
            logger.error(f"Archiving error: {e}", exc_info=True)
    
    def _serialize_market_data(self, md: MarketData) -> dict:
        """Serialize market data to dict"""
        return {
            'timestamp': md.timestamp,
            'symbol': md.symbol,
            'last_price': float(md.last_price) if md.last_price else None,
            'bid_price': float(md.bid_price) if md.bid_price else None,
            'ask_price': float(md.ask_price) if md.ask_price else None,
            'volume_24h': float(md.volume_24h)
        }
    
    def _serialize_trade(self, trade: Trade) -> dict:
        """Serialize trade to dict"""
        return {
            'trade_id': trade.trade_id,
            'timestamp': trade.timestamp,
            'price': float(trade.price),
            'size': float(trade.size),
            'buy_order_id': trade.buy_order_id,
            'sell_order_id': trade.sell_order_id,
            'aggressor_side': trade.aggressor_side.value
        }
    
    def get_stats(self) -> dict:
        """Get archiver statistics"""
        return {
            'archives_created': self.archives_created,
            'total_archived_data': self.total_archived_data,
            'archive_dir': str(self.archive_dir),
            'rolling_store': self.rolling_store.get_stats()
        }

class MemoryMonitor:
    """
    Monitor memory usage and alert on high usage.
    """
    
    def __init__(self, check_interval_seconds: int = 10, warning_threshold_mb: float = 500):
        self.check_interval = check_interval_seconds
        self.warning_threshold = warning_threshold_mb * 1024 * 1024  # Convert to bytes
        
        self.peak_memory = 0
        self.warnings_issued = 0
    
    async def start(self):
        """Start memory monitoring"""
        logger.info("Starting memory monitor")
        
        try:
            import psutil
            process = psutil.Process()
            
            while True:
                await asyncio.sleep(self.check_interval)
                
                memory_info = process.memory_info()
                current_memory = memory_info.rss  # Resident Set Size
                
                self.peak_memory = max(self.peak_memory, current_memory)
                
                if current_memory > self.warning_threshold:
                    self.warnings_issued += 1
                    logger.warning(
                        f"High memory usage: {current_memory / 1024 / 1024:.2f} MB "
                        f"(threshold: {self.warning_threshold / 1024 / 1024:.2f} MB)"
                    )
                
                logger.debug(
                    f"Memory usage: {current_memory / 1024 / 1024:.2f} MB "
                    f"(peak: {self.peak_memory / 1024 / 1024:.2f} MB)"
                )
                
        except ImportError:
            logger.warning("psutil not available, memory monitoring disabled")
        except asyncio.CancelledError:
            logger.info("Memory monitor stopped")
    
    def get_stats(self) -> dict:
        """Get memory statistics"""
        return {
            'peak_memory_mb': self.peak_memory / 1024 / 1024,
            'warnings_issued': self.warnings_issued,
            'warning_threshold_mb': self.warning_threshold / 1024 / 1024
        }
