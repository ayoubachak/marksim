"""
Pure functional matching engine.
All functions are stateless - take order book, return new book + trades.
"""
from typing import Tuple, List, Optional
from decimal import Decimal
import uuid
import logging

from .types import (
    Order, Trade, MatchResult, Side, OrderType, 
    OrderStatus, TimeInForce
)
from .order_book import ImmutableOrderBook

logger = logging.getLogger(__name__)

class MatchingEngine:
    """
    Stateless matching engine.
    All methods are pure functions.
    """
    
    @staticmethod
    def match_order(
        order: Order,
        book: ImmutableOrderBook,
        timestamp: int
    ) -> Tuple[ImmutableOrderBook, MatchResult]:
        """
        Match order against book.
        Returns (new_book, match_result).
        """
        # Validate order
        if order.size <= 0:
            return book, MatchResult(
                order=order,
                rejected=True,
                rejection_reason="Invalid size"
            )
        
        # Route to appropriate handler
        if order.order_type == OrderType.MARKET:
            return MatchingEngine._match_market_order(order, book, timestamp)
        elif order.order_type == OrderType.LIMIT:
            return MatchingEngine._match_limit_order(order, book, timestamp)
        else:
            return book, MatchResult(
                order=order,
                rejected=True,
                rejection_reason=f"Unsupported order type: {order.order_type}"
            )
    
    # ========================================================================
    # MARKET ORDER MATCHING
    # ========================================================================
    
    @staticmethod
    def _match_market_order(
        order: Order,
        book: ImmutableOrderBook,
        timestamp: int
    ) -> Tuple[ImmutableOrderBook, MatchResult]:
        """Match market order (aggressive)"""
        
        # Get opposite side levels
        if order.side == Side.BUY:
            levels = book._snapshot.asks  # Buy matches against asks
            best_price = book.best_ask
        else:
            levels = book._snapshot.bids  # Sell matches against bids
            best_price = book.best_bid
        
        # Check liquidity
        if not levels or best_price is None:
            return book, MatchResult(
                order=order,
                rejected=True,
                rejection_reason="No liquidity"
            )
        
        # Execute matches
        trades = []
        remaining_size = order.size
        new_book = book
        
        # Iterate through price levels
        level_prices = list(levels.keys()) if order.side == Side.BUY else list(reversed(levels.keys()))
        
        for price in level_prices:
            if remaining_size <= 0:
                break
            
            level = new_book._snapshot.asks.get(price) if order.side == Side.BUY else new_book._snapshot.bids.get(price)
            if not level:
                continue
            
            # Match against orders at this level
            for passive_order in level.orders:
                if remaining_size <= 0:
                    break
                
                # Calculate match size
                match_size = min(remaining_size, passive_order.size - passive_order.filled_size)
                
                # Create trade
                trade = Trade(
                    trade_id=str(uuid.uuid4()),
                    timestamp=timestamp,
                    price=price,
                    size=match_size,
                    buy_order_id=order.order_id if order.side == Side.BUY else passive_order.order_id,
                    sell_order_id=passive_order.order_id if order.side == Side.SELL else order.order_id,
                    aggressor_side=order.side
                )
                trades.append(trade)
                
                # Update remaining size
                remaining_size -= match_size
                
                # Update passive order
                passive_filled = passive_order.filled_size + match_size
                passive_status = (
                    OrderStatus.FILLED if passive_filled >= passive_order.size
                    else OrderStatus.PARTIALLY_FILLED
                )
                
                new_book = new_book.update_order(
                    passive_order.order_id,
                    filled_size=passive_filled,
                    status=passive_status
                )
                
                # Record trade
                new_book = new_book.record_trade(trade)
        
        # Create result
        filled_size = order.size - remaining_size
        
        # Check Time In Force
        if order.time_in_force == TimeInForce.FOK and remaining_size > 0:
            # Fill or Kill - reject if not fully filled
            return book, MatchResult(
                order=order,
                rejected=True,
                rejection_reason="FOK not fully filled"
            )
        
        # Update aggressor order
        updated_order = Order(
            **{
                **order.__dict__,
                'filled_size': filled_size,
                'status': OrderStatus.FILLED if remaining_size == 0 else OrderStatus.PARTIALLY_FILLED
            }
        )
        
        # IOC: cancel remaining
        if order.time_in_force == TimeInForce.IOC:
            remaining_order = None
        else:
            remaining_order = Order(
                **{**order.__dict__, 'size': remaining_size}
            ) if remaining_size > 0 else None
        
        return new_book, MatchResult(
            order=updated_order,
            trades=trades,
            remaining_order=remaining_order
        )
    
    # ========================================================================
    # LIMIT ORDER MATCHING
    # ========================================================================
    
    @staticmethod
    def _match_limit_order(
        order: Order,
        book: ImmutableOrderBook,
        timestamp: int
    ) -> Tuple[ImmutableOrderBook, MatchResult]:
        """Match limit order (can be passive or aggressive)"""
        
        if order.price is None:
            return book, MatchResult(
                order=order,
                rejected=True,
                rejection_reason="Limit order must have price"
            )
        
        # Check if order crosses spread (aggressive)
        crosses_spread = False
        if order.side == Side.BUY:
            best_ask = book.best_ask
            crosses_spread = best_ask is not None and order.price >= best_ask
        else:
            best_bid = book.best_bid
            crosses_spread = best_bid is not None and order.price <= best_bid
        
        # If crosses, match aggressively first
        trades = []
        remaining_size = order.size
        new_book = book
        
        if crosses_spread:
            # Get matchable levels
            if order.side == Side.BUY:
                levels = [(p, l) for p, l in book._snapshot.asks.items() if p <= order.price]
            else:
                levels = [(p, l) for p, l in book._snapshot.bids.items() if p >= order.price]
                levels.reverse()
            
            # Match against crossable levels
            for price, level in levels:
                if remaining_size <= 0:
                    break
                
                for passive_order in level.orders:
                    if remaining_size <= 0:
                        break
                    
                    match_size = min(remaining_size, passive_order.size - passive_order.filled_size)
                    
                    # Create trade
                    trade = Trade(
                        trade_id=str(uuid.uuid4()),
                        timestamp=timestamp,
                        price=price,  # Match at passive order price
                        size=match_size,
                        buy_order_id=order.order_id if order.side == Side.BUY else passive_order.order_id,
                        sell_order_id=passive_order.order_id if order.side == Side.SELL else order.order_id,
                        aggressor_side=order.side
                    )
                    trades.append(trade)
                    remaining_size -= match_size
                    
                    # Update passive order
                    passive_filled = passive_order.filled_size + match_size
                    passive_status = (
                        OrderStatus.FILLED if passive_filled >= passive_order.size
                        else OrderStatus.PARTIALLY_FILLED
                    )
                    new_book = new_book.update_order(
                        passive_order.order_id,
                        filled_size=passive_filled,
                        status=passive_status
                    )
                    new_book = new_book.record_trade(trade)
        
        # Calculate fill status
        filled_size = order.size - remaining_size
        
        # Check Time In Force
        if order.time_in_force == TimeInForce.FOK and remaining_size > 0:
            return book, MatchResult(
                order=order,
                rejected=True,
                rejection_reason="FOK not fully filled"
            )
        
        if order.time_in_force == TimeInForce.IOC:
            # IOC: don't post remaining
            updated_order = Order(
                **{
                    **order.__dict__,
                    'filled_size': filled_size,
                    'status': OrderStatus.FILLED if remaining_size == 0 else OrderStatus.CANCELLED
                }
            )
            return new_book, MatchResult(
                order=updated_order,
                trades=trades,
                remaining_order=None
            )
        
        # Post remaining size to book
        if remaining_size > 0:
            remaining_order = Order(
                **{
                    **order.__dict__,
                    'size': remaining_size,
                    'filled_size': filled_size,
                    'status': OrderStatus.PARTIALLY_FILLED if filled_size > 0 else OrderStatus.OPEN
                }
            )
            new_book = new_book.add_order(remaining_order)
        else:
            remaining_order = None
        
        # Create updated order for result
        updated_order = Order(
            **{
                **order.__dict__,
                'filled_size': filled_size,
                'status': OrderStatus.FILLED if remaining_size == 0 else OrderStatus.PARTIALLY_FILLED
            }
        )
        
        return new_book, MatchResult(
            order=updated_order,
            trades=trades,
            remaining_order=remaining_order
        )
    
    # ========================================================================
    # CANCELLATION
    # ========================================================================
    
    @staticmethod
    def cancel_order(
        order_id: str,
        book: ImmutableOrderBook
    ) -> Tuple[ImmutableOrderBook, Optional[Order]]:
        """
        Cancel order by ID.
        Returns (new_book, cancelled_order).
        """
        new_book, cancelled = book.remove_order(order_id)
        
        if cancelled:
            cancelled = Order(
                **{**cancelled.__dict__, 'status': OrderStatus.CANCELLED}
            )
            logger.info(f"Cancelled order {order_id}")
        
        return new_book, cancelled