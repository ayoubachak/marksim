"""
Real-time Dash dashboard for market simulation.
Non-blocking integration with asyncio simulation.
"""
import asyncio
from collections import deque
from typing import Dict, List
import logging

from dash import Dash, dcc, html, Input, Output
import plotly.graph_objs as go

from ..streaming.data_stream import BoundedMarketDataStream
from ..core.types import MarketData

logger = logging.getLogger(__name__)

class DashMarketVisualizer:
    """
    Real-time Dash dashboard consuming market stream.
    Runs in executor to avoid blocking asyncio loop.
    """
    
    def __init__(
        self,
        market_stream: BoundedMarketDataStream,
        max_points: int = 1000,
        update_interval_ms: int = 100
    ):
        self.market_stream = market_stream
        self.max_points = max_points
        self.update_interval_ms = update_interval_ms
        
        # Data buffers (thread-safe deques)
        self.timestamps: deque = deque(maxlen=max_points)
        self.prices: deque = deque(maxlen=max_points)
        self.bid_prices: deque = deque(maxlen=max_points)
        self.ask_prices: deque = deque(maxlen=max_points)
        self.volumes: deque = deque(maxlen=max_points)
        
        # Statistics
        self.total_updates = 0
        self.last_price = None
        
        # Create Dash app
        self.app = self._create_app()
        
        logger.info("Dash visualizer initialized")
    
    # ========================================================================
    # DATA CONSUMER
    # ========================================================================
    
    async def consume_stream(self):
        """Background task consuming market stream"""
        logger.info("Starting stream consumer")
        
        try:
            async for market_data in self.market_stream.subscribe():
                self._update_buffers(market_data)
                
        except asyncio.CancelledError:
            logger.info("Stream consumer cancelled")
        except Exception as e:
            logger.error(f"Stream consumer error: {e}", exc_info=True)
    
    def _update_buffers(self, market_data: MarketData):
        """Update data buffers (thread-safe)"""
        self.timestamps.append(market_data.timestamp / 1_000_000)  # Convert to seconds
        self.prices.append(
            float(market_data.last_price) if market_data.last_price else self.last_price
        )
        self.bid_prices.append(
            float(market_data.bid_price) if market_data.bid_price else None
        )
        self.ask_prices.append(
            float(market_data.ask_price) if market_data.ask_price else None
        )
        self.volumes.append(float(market_data.volume_24h))
        
        if market_data.last_price:
            self.last_price = float(market_data.last_price)
        
        self.total_updates += 1
    
    # ========================================================================
    # DASH APP
    # ========================================================================
    
    def _create_app(self) -> Dash:
        """Create Dash application"""
        app = Dash(__name__)
        
        app.layout = html.Div([
            html.H1("Market Simulation - Real-Time Dashboard", 
                   style={'textAlign': 'center', 'color': '#2c3e50'}),
            
            # Statistics row
            html.Div([
                html.Div([
                    html.H3("Last Price"),
                    html.Div(id='last-price', style={'fontSize': '24px', 'fontWeight': 'bold'})
                ], style={'width': '25%', 'display': 'inline-block', 'textAlign': 'center'}),
                
                html.Div([
                    html.H3("Spread"),
                    html.Div(id='spread', style={'fontSize': '24px', 'fontWeight': 'bold'})
                ], style={'width': '25%', 'display': 'inline-block', 'textAlign': 'center'}),
                
                html.Div([
                    html.H3("Updates"),
                    html.Div(id='updates', style={'fontSize': '24px', 'fontWeight': 'bold'})
                ], style={'width': '25%', 'display': 'inline-block', 'textAlign': 'center'}),
                
                html.Div([
                    html.H3("Volume 24h"),
                    html.Div(id='volume', style={'fontSize': '24px', 'fontWeight': 'bold'})
                ], style={'width': '25%', 'display': 'inline-block', 'textAlign': 'center'}),
            ], style={'marginBottom': '30px'}),
            
            # Price chart
            dcc.Graph(id='price-chart', style={'height': '400px'}),
            
            # Order book visualization
            html.Div([
                html.Div([
                    html.H3("Bid/Ask Spread"),
                    dcc.Graph(id='spread-chart', style={'height': '300px'})
                ], style={'width': '50%', 'display': 'inline-block'}),
                
                html.Div([
                    html.H3("Volume"),
                    dcc.Graph(id='volume-chart', style={'height': '300px'})
                ], style={'width': '50%', 'display': 'inline-block'}),
            ]),
            
            # Update interval
            dcc.Interval(
                id='interval-component',
                interval=self.update_interval_ms,
                n_intervals=0
            )
        ], style={'padding': '20px', 'fontFamily': 'Arial'})
        
        # Register callbacks
        self._register_callbacks(app)
        
        return app
    
    def _register_callbacks(self, app: Dash):
        """Register Dash callbacks"""
        
        @app.callback(
            [
                Output('price-chart', 'figure'),
                Output('spread-chart', 'figure'),
                Output('volume-chart', 'figure'),
                Output('last-price', 'children'),
                Output('spread', 'children'),
                Output('updates', 'children'),
                Output('volume', 'children')
            ],
            Input('interval-component', 'n_intervals')
        )
        def update_charts(n):
            # Price chart
            price_fig = go.Figure()
            
            if len(self.timestamps) > 0:
                price_fig.add_trace(go.Scatter(
                    x=list(self.timestamps),
                    y=list(self.prices),
                    mode='lines',
                    name='Last Price',
                    line=dict(color='#3498db', width=2)
                ))
            
            price_fig.update_layout(
                title='Price History',
                xaxis_title='Time (s)',
                yaxis_title='Price ($)',
                hovermode='x',
                template='plotly_white'
            )
            
            # Spread chart
            spread_fig = go.Figure()
            
            if len(self.timestamps) > 0:
                spread_fig.add_trace(go.Scatter(
                    x=list(self.timestamps),
                    y=list(self.bid_prices),
                    mode='lines',
                    name='Bid',
                    line=dict(color='#27ae60', width=2)
                ))
                
                spread_fig.add_trace(go.Scatter(
                    x=list(self.timestamps),
                    y=list(self.ask_prices),
                    mode='lines',
                    name='Ask',
                    line=dict(color='#e74c3c', width=2)
                ))
            
            spread_fig.update_layout(
                title='Bid/Ask Spread',
                xaxis_title='Time (s)',
                yaxis_title='Price ($)',
                hovermode='x',
                template='plotly_white'
            )
            
            # Volume chart
            volume_fig = go.Figure()
            
            if len(self.timestamps) > 0:
                volume_fig.add_trace(go.Bar(
                    x=list(self.timestamps),
                    y=list(self.volumes),
                    name='Volume',
                    marker_color='#9b59b6'
                ))
            
            volume_fig.update_layout(
                title='Volume',
                xaxis_title='Time (s)',
                yaxis_title='Volume',
                template='plotly_white'
            )
            
            # Statistics
            last_price_text = f"${self.last_price:.2f}" if self.last_price else "N/A"
            
            spread_value = None
            if len(self.bid_prices) > 0 and len(self.ask_prices) > 0:
                last_bid = list(self.bid_prices)[-1]
                last_ask = list(self.ask_prices)[-1]
                if last_bid and last_ask:
                    spread_value = last_ask - last_bid
            
            spread_text = f"${spread_value:.2f}" if spread_value else "N/A"
            updates_text = f"{self.total_updates:,}"
            volume_text = f"{list(self.volumes)[-1]:.2f}" if len(self.volumes) > 0 else "N/A"
            
            return (
                price_fig,
                spread_fig,
                volume_fig,
                last_price_text,
                spread_text,
                updates_text,
                volume_text
            )
    
    # ========================================================================
    # SERVER CONTROL
    # ========================================================================
    
    def run_server(self, host='127.0.0.1', port=8050, debug=False):
        """Run Dash server (blocking call)"""
        logger.info(f"Starting Dash server on {host}:{port}")
        self.app.run_server(host=host, port=port, debug=debug, use_reloader=False)
