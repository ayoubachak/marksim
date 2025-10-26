"""
Lock-free immutable order book using copy-on-write.
All operations return new book state - no mutations.
"""
from sortedcontainers import SortedDict
from typing import Optional, List, Tuple, Dict
from decimal import Decimal
from dataclasses import dataclass, field
import uuid

from .types import Order, Trade, Side, OrderStatus

@dataclass(frozen=True)
class PriceLevel:
    """Orders at a specific price level"""
    price: Decimal
    orders: Tuple[Order, ...]  # Immutable tuple
    total_size: Decimal
    
    def add_order(self, order: Order) -> 'PriceLevel':
        """Return new level with order added"""
        return PriceLevel(
            price=self.price,
            orders=self.orders + (order,),
            total_size=self.total_size + order.size
        )
    
    def remove_order(self, order_id: str) -> Tuple['PriceLevel', Optional[Order]]:
        """Return new level with order removed"""
        new_orders = tuple(o for o in self.orders if o.order_id != order_id)
        removed = next((o for o in self.orders if o.order_id == order_id), None)
        
        if not new_orders:
            return None, removed  # Level exhausted
        
        new_total = sum(o.size for o in new_orders)
        return PriceLevel(self.price, new_orders, new_total), removed

@dataclass(frozen=True)
class OrderBookSnapshot:
    """Immutable order book state"""
    bids: SortedDict  # price -> PriceLevel (descending)
    asks: SortedDict  # price -> PriceLevel (ascending)
    orders: Dict[str, Order]  # order_id -> Order
    version: int
    last_trade_price: Optional[Decimal] = None
    
    def copy(self) -> 'OrderBookSnapshot':
        """Create shallow copy for modifications"""
        return OrderBookSnapshot(
            bids=SortedDict(self.bids),
            asks=SortedDict(self.asks),
            orders=dict(self.orders),
            version=self.version + 1,
            last_trade_price=self.last_trade_price
        )
    
    def with_trade_price(self, price: Decimal) -> 'OrderBookSnapshot':
        """Create new snapshot with updated trade price"""
        return OrderBookSnapshot(
            bids=self.bids,
            asks=self.asks,
            orders=self.orders,
            version=self.version + 1,
            last_trade_price=price
        )

class ImmutableOrderBook:
    """
    Lock-free order book using structural sharing.
    All methods are pure functions returning new state.
    """
    
    def __init__(self, snapshot: Optional[OrderBookSnapshot] = None):
        if snapshot is None:
            snapshot = OrderBookSnapshot(
                bids=SortedDict(),
                asks=SortedDict(),
                orders={},
                version=0
            )
        self._snapshot = snapshot
    
    # ========================================================================
    # QUERY METHODS (Read-only, thread-safe)
    # ========================================================================
    
    @property
    def best_bid(self) -> Optional[Decimal]:
        """Get best bid price"""
        return self._snapshot.bids.keys()[-1] if self._snapshot.bids else None
    
    @property
    def best_ask(self) -> Optional[Decimal]:
        """Get best ask price"""
        return self._snapshot.asks.keys()[0] if self._snapshot.asks else None
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Get bid-ask spread"""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None
    
    @property
    def mid_price(self) -> Optional[Decimal]:
        """Get mid price"""
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return self._snapshot.orders.get(order_id)
    
    def get_depth(self, levels: int = 10) -> Dict:
        """Get order book depth"""
        bids = list(self._snapshot.bids.items())[-levels:]
        asks = list(self._snapshot.asks.items())[:levels]
        
        return {
            'bids': [(float(p), float(lvl.total_size)) for p, lvl in reversed(bids)],
            'asks': [(float(p), float(lvl.total_size)) for p, lvl in asks],
            'spread': float(self.spread) if self.spread else None,
            'mid_price': float(self.mid_price) if self.mid_price else None
        }
    
    # ========================================================================
    # MUTATION METHODS (Return new book state)
    # ========================================================================
    
    def add_order(self, order: Order) -> 'ImmutableOrderBook':
        """Add order to book - returns NEW book"""
        # Validate
        if order.status not in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
            raise ValueError(f"Cannot add order with status {order.status}")
        
        # Create new snapshot
        new_snapshot = self._snapshot.copy()
        
        # Add to orders map
        new_order = Order(
            **{**order.__dict__, 'status': OrderStatus.OPEN}
        )
        new_snapshot.orders[order.order_id] = new_order
        
        # Add to price level
        price_levels = new_snapshot.bids if order.side == Side.BUY else new_snapshot.asks
        
        if order.price in price_levels:
            level = price_levels[order.price]
            price_levels[order.price] = level.add_order(new_order)
        else:
            price_levels[order.price] = PriceLevel(
                price=order.price,
                orders=(new_order,),
                total_size=new_order.size
            )
        
        return ImmutableOrderBook(new_snapshot)
    
    def remove_order(self, order_id: str) -> Tuple['ImmutableOrderBook', Optional[Order]]:
        """Remove order from book - returns (NEW book, removed order)"""
        order = self._snapshot.orders.get(order_id)
        if not order:
            return self, None  # No change
        
        # Create new snapshot
        new_snapshot = self._snapshot.copy()
        
        # Remove from orders map
        del new_snapshot.orders[order_id]
        
        # Remove from price level
        price_levels = new_snapshot.bids if order.side == Side.BUY else new_snapshot.asks
        
        if order.price in price_levels:
            new_level, removed = price_levels[order.price].remove_order(order_id)
            if new_level is None:
                del price_levels[order.price]  # Level exhausted
            else:
                price_levels[order.price] = new_level
        
        return ImmutableOrderBook(new_snapshot), order
    
    def update_order(
        self,
        order_id: str,
        filled_size: Decimal,
        status: OrderStatus
    ) -> 'ImmutableOrderBook':
        """Update order status - returns NEW book"""
        order = self._snapshot.orders.get(order_id)
        if not order:
            return self  # No change
        
        # Remove old order
        new_book, _ = self.remove_order(order_id)
        
        # If still open, add updated order
        if status == OrderStatus.OPEN or status == OrderStatus.PARTIALLY_FILLED:
            remaining_size = order.size - filled_size
            if remaining_size > 0:  # Only add if there's remaining size
                updated_order = Order(
                    **{
                        **order.__dict__,
                        'filled_size': filled_size,
                        'status': status,
                        'size': remaining_size
                    }
                )
                return new_book.add_order(updated_order)
        
        return new_book
    
    def record_trade(self, trade: Trade) -> 'ImmutableOrderBook':
        """Record trade execution - returns NEW book"""
        new_snapshot = self._snapshot.with_trade_price(trade.price)
        return ImmutableOrderBook(new_snapshot)
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def get_snapshot(self) -> OrderBookSnapshot:
        """Get current snapshot (for serialization)"""
        return self._snapshot
    
    def __repr__(self):
        return (
            f"OrderBook(version={self._snapshot.version}, "
            f"bids={len(self._snapshot.bids)}, "
            f"asks={len(self._snapshot.asks)}, "
            f"orders={len(self._snapshot.orders)})"
        )