"""
Bounded market data stream with backpressure.
Prevents slow consumers from blocking producers.
"""
import asyncio
from typing import AsyncIterator, Optional, Set, List
from dataclasses import dataclass, field
import logging
from collections import deque
from decimal import Decimal

from ..core.types import MarketData, Trade, Candle

logger = logging.getLogger(__name__)

@dataclass
class CandleData:
    """Candle data wrapper for streaming"""
    candle: Candle
    is_closed: bool
    timeframe: str
    sequence_id: int = 0  # Unique identifier to prevent duplicates
    
    @property
    def timestamp(self) -> int:
        return self.candle.timestamp
    
    @property
    def symbol(self) -> str:
        return "BTC/USD"
    
    @property
    def last_price(self) -> Decimal:
        return self.candle.close

@dataclass
class StreamStats:
    """Stream performance metrics"""
    messages_published: int = 0
    messages_dropped: int = 0
    active_subscribers: int = 0
    queue_size: int = 0

class BoundedMarketDataStream:
    """
    Non-blocking market data publisher with backpressure.
    
    Features:
    - Bounded queue (fixed memory)
    - Drop policy when full (never blocks)
    - Multiple independent subscribers
    - Metrics tracking
    """
    
    def __init__(
        self,
        maxsize: int = 1000,
        drop_timeout_ms: float = 1.0
    ):
        self.maxsize = maxsize
        self.drop_timeout = drop_timeout_ms / 1000.0
        
        # Main queue
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        
        # Stats
        self.stats = StreamStats()
        
        # Subscriber management
        self._subscribers: Set[asyncio.Queue] = set()
        self._subscriber_lock = asyncio.Lock()
    
    # ========================================================================
    # PUBLISHING
    # ========================================================================
    
    async def publish(self, data: MarketData) -> bool:
        """
        Publish market data (non-blocking).
        Returns False if message dropped due to backpressure.
        """
        try:
            # Try to put with timeout (non-blocking)
            await asyncio.wait_for(
                self._queue.put(data),
                timeout=self.drop_timeout
            )
            self.stats.messages_published += 1
            self.stats.queue_size = self._queue.qsize()
            return True
            
        except asyncio.TimeoutError:
            # Drop message if queue full
            self.stats.messages_dropped += 1
            
            if self.stats.messages_dropped % 100 == 0:
                logger.warning(
                    f"Stream backpressure: dropped {self.stats.messages_dropped} messages"
                )
            
            return False
    
    def publish_nowait(self, data: MarketData) -> bool:
        """Publish without waiting (returns False if full)"""
        try:
            self._queue.put_nowait(data)
            self.stats.messages_published += 1
            return True
        except asyncio.QueueFull:
            self.stats.messages_dropped += 1
            return False
    
    # ========================================================================
    # SUBSCRIBING
    # ========================================================================
    
    async def subscribe(self) -> AsyncIterator[MarketData]:
        """
        Subscribe to stream (creates independent queue).
        Each subscriber gets their own buffer.
        """
        subscriber_queue = asyncio.Queue(maxsize=self.maxsize)
        
        async with self._subscriber_lock:
            self._subscribers.add(subscriber_queue)
            self.stats.active_subscribers = len(self._subscribers)
        
        try:
            # Start forwarding messages
            forward_task = asyncio.create_task(
                self._forward_to_subscriber(subscriber_queue)
            )
            
            # Yield messages to subscriber
            while True:
                data = await subscriber_queue.get()
                if data is None:  # Shutdown signal
                    break
                yield data
                
        finally:
            forward_task.cancel()
            async with self._subscriber_lock:
                self._subscribers.discard(subscriber_queue)
                self.stats.active_subscribers = len(self._subscribers)
    
    async def _forward_to_subscriber(self, subscriber_queue: asyncio.Queue):
        """Forward main stream to subscriber queue"""
        while True:
            try:
                data = await self._queue.get()
                
                # Try to forward (with short timeout)
                try:
                    await asyncio.wait_for(
                        subscriber_queue.put(data),
                        timeout=0.001  # 1ms
                    )
                except asyncio.TimeoutError:
                    # Subscriber too slow, drop message
                    pass
                    
            except asyncio.CancelledError:
                # Send shutdown signal
                try:
                    subscriber_queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
                break
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def get_stats(self) -> StreamStats:
        """Get current statistics"""
        self.stats.queue_size = self._queue.qsize()
        return self.stats
    
    async def close(self):
        """Close stream and notify all subscribers"""
        async with self._subscriber_lock:
            for subscriber_queue in self._subscribers:
                try:
                    subscriber_queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
            self._subscribers.clear()

# ============================================================================
# SPECIALIZED STREAMS
# ============================================================================

class TradeStream(BoundedMarketDataStream):
    """Stream for trade executions only"""
    
    async def publish_trade(self, trade: Trade) -> bool:
        """Publish trade event"""
        data = MarketData(
            timestamp=trade.timestamp,
            symbol="BTC/USD",  # TODO: make configurable
            last_price=trade.price,
            trades=[trade]
        )
        return await self.publish(data)

class CandleStream:
    """
    Multi-timeframe candle stream with automatic aggregation.
    """
    
    def __init__(self, timeframes: List[str], maxsize: int = 100):
        self.timeframes = timeframes
        self._streams = {
            tf: BoundedMarketDataStream(maxsize=maxsize)
            for tf in timeframes
        }
        
        # Current candles being built
        self._current_candles: dict[str, Optional[Candle]] = {
            tf: None for tf in timeframes
        }
        
        # Sequence tracking for deduplication
        self._sequence_counters: dict[str, int] = {
            tf: 0 for tf in timeframes
        }
        
        # Throttling for sub-minute timeframes
        self._last_update_times: dict[str, int] = {
            tf: 0 for tf in timeframes
        }
        self._update_throttle_ms = {
            '1s': 100,   # Max 10 updates per second
            '3s': 200,   # Max 5 updates per second
            '5s': 300,   # Max 3.3 updates per second
            '10s': 500,  # Max 2 updates per second
            '15s': 750,  # Max 1.3 updates per second
            '30s': 1000, # Max 1 update per second
        }
    
    async def update_from_trade(self, trade: Trade):
        """Update all timeframe candles from trade"""
        logger.debug(f"Updating candles from trade: price={trade.price}, size={trade.size}, timestamp={trade.timestamp}")
        for timeframe in self.timeframes:
            await self._update_candle(timeframe, trade)
    
    async def _update_candle(self, timeframe: str, trade: Trade):
        """Update specific timeframe candle"""
        current = self._current_candles[timeframe]
        
        # Get precise candle start time aligned to boundaries
        candle_start = self._get_candle_start_time(trade.timestamp, timeframe)
        
        # Check if new candle needed
        if current is None or current.timestamp != candle_start:
            # Close previous candle (if exists)
            if current is not None:
                self._sequence_counters[timeframe] += 1
                candle_data = CandleData(
                    candle=current,
                    is_closed=True,
                    timeframe=timeframe,
                    sequence_id=self._sequence_counters[timeframe]
                )
                await self._streams[timeframe].publish(candle_data)
            
            # Start new candle
            new_candle = Candle(
                timestamp=candle_start,
                open=trade.price,
                high=trade.price,
                low=trade.price,
                close=trade.price,
                volume=trade.size,
                trade_count=1,
                timeframe=timeframe
            )
            self._current_candles[timeframe] = new_candle
            
            # Publish new candle immediately (like Binance)
            self._sequence_counters[timeframe] += 1
            candle_data = CandleData(
                candle=new_candle,
                is_closed=False,
                timeframe=timeframe,
                sequence_id=self._sequence_counters[timeframe]
            )
            await self._streams[timeframe].publish(candle_data)
        else:
            # Update existing candle
            candle = current
            updated_candle = Candle(
                timestamp=candle.timestamp,
                open=candle.open,
                high=max(candle.high, trade.price),
                low=min(candle.low, trade.price),
                close=trade.price,
                volume=candle.volume + trade.size,
                trade_count=candle.trade_count + 1,
                timeframe=timeframe
            )
            self._current_candles[timeframe] = updated_candle
            
            # Publish updated candle (live updates like Binance) with throttling
            if self._should_update_candle(timeframe, trade.timestamp):
                self._sequence_counters[timeframe] += 1
                candle_data = CandleData(
                    candle=updated_candle,
                    is_closed=False,
                    timeframe=timeframe,
                    sequence_id=self._sequence_counters[timeframe]
                )
                await self._streams[timeframe].publish(candle_data)
                self._last_update_times[timeframe] = trade.timestamp
    
    def _should_update_candle(self, timeframe: str, timestamp_us: int) -> bool:
        """Check if candle update should be throttled"""
        if timeframe not in self._update_throttle_ms:
            return True  # No throttling for minute+ timeframes
        
        throttle_ms = self._update_throttle_ms[timeframe]
        last_update = self._last_update_times[timeframe]
        
        # Convert microseconds to milliseconds for comparison
        time_since_last_ms = (timestamp_us - last_update) // 1000
        
        return time_since_last_ms >= throttle_ms
    
    def subscribe(self, timeframe: str) -> AsyncIterator[CandleData]:
        """Subscribe to specific timeframe"""
        if timeframe not in self._streams:
            raise ValueError(f"Unknown timeframe: {timeframe}")
        return self._streams[timeframe].subscribe()
    
    @staticmethod
    def _parse_timeframe(tf: str) -> int:
        """Parse timeframe string to seconds"""
        unit = tf[-1]
        value = int(tf[:-1])
        
        multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        return value * multipliers.get(unit, 60)
    
    @staticmethod
    def _get_candle_start_time(timestamp_us: int, timeframe: str) -> int:
        """
        Get precise candle start time aligned to actual time boundaries.
        
        For sub-minute timeframes, aligns to second boundaries.
        For minute+ timeframes, aligns to minute boundaries.
        
        Examples:
        - 1s: 12:34:56.789 -> 12:34:56.000
        - 5s: 12:34:56.789 -> 12:34:55.000 (aligned to 5s boundaries)
        - 1m: 12:34:56.789 -> 12:34:00.000
        """
        interval_seconds = CandleStream._parse_timeframe(timeframe)
        
        if timeframe.endswith('s'):
            # Sub-minute: align to second boundaries
            # Convert microseconds to seconds, floor, then back to microseconds
            seconds = timestamp_us // 1_000_000
            aligned_seconds = (seconds // interval_seconds) * interval_seconds
            return aligned_seconds * 1_000_000
        else:
            # Minute+: align to minute boundaries
            # Convert to minutes, floor, then back to microseconds
            minutes = timestamp_us // (60 * 1_000_000)
            aligned_minutes = (minutes // interval_seconds) * interval_seconds
            return aligned_minutes * 60 * 1_000_000