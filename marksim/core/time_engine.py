"""
Async discrete event simulation engine with pause/resume and speed control.
Zero blocking operations.
"""
import asyncio
import heapq
from typing import Optional, List, Callable, Awaitable
from dataclasses import dataclass
import logging

from .types import Event

logger = logging.getLogger(__name__)

@dataclass
class TimeEngineStats:
    """Performance metrics"""
    events_processed: int = 0
    events_scheduled: int = 0
    events_dropped: int = 0
    current_time_us: int = 0
    queue_size: int = 0

class AsyncTimeEngine:
    """
    Non-blocking discrete event simulator with:
    - Pause/resume capability
    - Speed control (1x, 10x, 100x, unlimited)
    - Bounded queue with backpressure
    - Async event handlers
    """
    
    def __init__(
        self,
        start_time_us: int = 0,
        speed_multiplier: float = 1.0,
        max_queue_size: int = 100_000
    ):
        self.current_time_us = start_time_us
        self.speed_multiplier = speed_multiplier
        self.max_queue_size = max_queue_size
        
        # Priority queue: (timestamp, counter, event)
        self._event_queue: List[tuple[int, int, Event]] = []
        self._event_counter = 0  # For stable sorting
        
        # Control flags
        self._paused = asyncio.Event()
        self._paused.set()  # Start unpaused
        self._running = False
        
        # Event handlers: event_type -> list of async handlers
        self._handlers: dict[type, List[Callable[[Event], Awaitable[None]]]] = {}
        
        # Stats
        self.stats = TimeEngineStats()
        
    # ========================================================================
    # CONTROL METHODS
    # ========================================================================
    
    def pause(self):
        """Pause simulation"""
        self._paused.clear()
        logger.info("Simulation paused")
    
    def resume(self):
        """Resume simulation"""
        self._paused.set()
        logger.info("Simulation resumed")
    
    def set_speed(self, multiplier: float):
        """
        Set simulation speed.
        - 1.0 = real-time
        - 10.0 = 10x speed
        - 0.0 = unlimited (no delays)
        """
        self.speed_multiplier = multiplier
        logger.info(f"Speed set to {multiplier}x")
    
    # ========================================================================
    # EVENT SCHEDULING
    # ========================================================================
    
    def schedule_event(self, event: Event, delay_us: int = 0) -> bool:
        """
        Schedule event with optional delay.
        Returns False if queue full (backpressure).
        """
        if len(self._event_queue) >= self.max_queue_size:
            self.stats.events_dropped += 1
            if self.stats.events_dropped % 1000 == 0:
                logger.warning(
                    f"Event queue full! Dropped {self.stats.events_dropped} events"
                )
            return False
        
        timestamp = self.current_time_us + delay_us
        # Use counter for stable sort (FIFO for same timestamp/priority)
        heapq.heappush(
            self._event_queue,
            (timestamp, event.priority, self._event_counter, event)
        )
        self._event_counter += 1
        self.stats.events_scheduled += 1
        return True
    
    def schedule_recurring(
        self,
        event_factory: Callable[[int], Event],
        interval_us: int,
        count: Optional[int] = None
    ):
        """Schedule recurring events"""
        current_time = self.current_time_us
        scheduled = 0
        
        while count is None or scheduled < count:
            event_time = current_time + (scheduled * interval_us)
            event = event_factory(event_time)
            
            if not self.schedule_event(event, delay_us=0):
                break  # Queue full
            
            scheduled += 1
            if count and scheduled >= count:
                break
        
        logger.info(f"Scheduled {scheduled} recurring events")
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    def register_handler(
        self,
        event_type: type,
        handler: Callable[[Event], Awaitable[None]]
    ):
        """Register async event handler"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def _dispatch_event(self, event: Event):
        """Dispatch event to all registered handlers"""
        event_type = type(event)
        
        if event_type not in self._handlers:
            logger.debug(f"No handler for {event_type.__name__}")
            return
        
        handlers = self._handlers[event_type]
        
        # Run all handlers concurrently
        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Handler {handlers[i].__name__} failed: {result}",
                    exc_info=result
                )
    
    # ========================================================================
    # SIMULATION LOOP
    # ========================================================================
    
    async def run(self, until_time_us: Optional[int] = None):
        """
        Main simulation loop.
        Runs until queue empty or until_time_us reached.
        """
        self._running = True
        logger.info("Starting simulation")
        
        try:
            while self._running and self._event_queue:
                # Check pause
                await self._paused.wait()
                
                # Check time limit
                if until_time_us and self.current_time_us >= until_time_us:
                    logger.info(f"Reached time limit: {until_time_us}")
                    break
                
                # Get next event
                timestamp, priority, counter, event = heapq.heappop(self._event_queue)
                
                # Simulate time passage (if speed limited)
                if self.speed_multiplier > 0:
                    time_delta_us = timestamp - self.current_time_us
                    if time_delta_us > 0:
                        sleep_seconds = time_delta_us / 1_000_000 / self.speed_multiplier
                        await asyncio.sleep(sleep_seconds)
                
                # Advance time
                self.current_time_us = timestamp
                
                # Dispatch event
                await self._dispatch_event(event)
                
                # Update stats
                self.stats.events_processed += 1
                self.stats.current_time_us = self.current_time_us
                self.stats.queue_size = len(self._event_queue)
                
                # Yield control periodically
                if self.stats.events_processed % 100 == 0:
                    await asyncio.sleep(0)  # Yield to other tasks
                
        except asyncio.CancelledError:
            logger.info("Simulation cancelled")
            raise
        except Exception as e:
            logger.error(f"Simulation error: {e}", exc_info=True)
            raise
        finally:
            self._running = False
            logger.info(
                f"Simulation stopped. Processed {self.stats.events_processed} events"
            )
    
    def stop(self):
        """Stop simulation"""
        self._running = False
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def get_stats(self) -> TimeEngineStats:
        """Get current statistics"""
        self.stats.queue_size = len(self._event_queue)
        return self.stats
    
    def clear_queue(self):
        """Clear all pending events"""
        self._event_queue.clear()
        logger.info("Event queue cleared")