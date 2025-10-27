"""
Pure WebSocket consumer for Dash visualization.
Demonstrates decoupled architecture - Dash consumes from WebSocket stream.
"""
import asyncio
import json
import websockets
from collections import deque
from typing import Dict, List
import logging

from dash import Dash, dcc, html, Input, Output
import plotly.graph_objs as go

logger = logging.getLogger(__name__)

class DashWebSocketConsumer:
    """
    Dash dashboard that consumes market data from WebSocket.
    This demonstrates the decoupled architecture - Dash is just a consumer.
    """
    
    def __init__(
        self,
        websocket_url: str = 'ws://localhost:8765',
        max_points: int = 1000,
        update_interval_ms: int = 100
    ):
        self.websocket_url = websocket_url
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
        self.connection_status = "Disconnected"
        
        # WebSocket connection
        self.websocket = None
        self.connected = False
        
        # Create Dash app
        self.app = self._create_app()
        
        logger.info(f"Dash WebSocket consumer initialized (URL: {websocket_url})")
    
    # ========================================================================
    # WEBSOCKET CONSUMER
    # ========================================================================
    
    async def connect_to_websocket(self):
        """Connect to WebSocket server"""
        try:
            logger.info(f"Connecting to WebSocket: {self.websocket_url}")
            self.websocket = await websockets.connect(self.websocket_url)
            self.connected = True
            self.connection_status = "Connected"
            logger.info("✅ WebSocket connected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.connection_status = f"Error: {e}"
            return False
    
    async def consume_websocket_stream(self):
        """Consume market data from WebSocket stream"""
        if not self.websocket:
            logger.error("WebSocket not connected")
            return
        
        try:
            logger.info("Starting WebSocket stream consumption")
            
            async for message in self.websocket:
                try:
                    # Parse JSON message
                    data = json.loads(message)
                    self._update_buffers_from_websocket(data)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse WebSocket message: {e}")
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    
        except websockets.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.connected = False
            self.connection_status = "Disconnected"
        except Exception as e:
            logger.error(f"WebSocket consumption error: {e}", exc_info=True)
            self.connected = False
            self.connection_status = f"Error: {e}"
    
    def _update_buffers_from_websocket(self, data: dict):
        """Update data buffers from WebSocket data"""
        # Extract timestamp (convert from microseconds to seconds)
        timestamp = data.get('timestamp', 0) / 1_000_000
        
        self.timestamps.append(timestamp)
        
        # Extract price data
        last_price = data.get('last_price')
        if last_price is not None:
            self.prices.append(last_price)
            self.last_price = last_price
        else:
            self.prices.append(self.last_price)
        
        # Extract bid/ask data
        self.bid_prices.append(data.get('bid_price'))
        self.ask_prices.append(data.get('ask_price'))
        
        # Extract volume
        self.volumes.append(data.get('volume_24h', 0))
        
        self.total_updates += 1
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            self.connection_status = "Disconnected"
            logger.info("WebSocket disconnected")
    
    # ========================================================================
    # DASH APP
    # ========================================================================
    
    def _create_app(self) -> Dash:
        """Create Dash application"""
        app = Dash(__name__)
        
        app.layout = html.Div([
            html.H1("Market Simulation - WebSocket Consumer Dashboard", 
                   style={'textAlign': 'center', 'color': '#2c3e50'}),
            
            # Connection status
            html.Div([
                html.H3("Connection Status"),
                html.Div(id='connection-status', style={'fontSize': '18px', 'fontWeight': 'bold', 'color': '#e74c3c'})
            ], style={'textAlign': 'center', 'marginBottom': '20px'}),
            
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
                Output('volume', 'children'),
                Output('connection-status', 'children')
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
                title='Price History (from WebSocket)',
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
                title='Bid/Ask Spread (from WebSocket)',
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
                title='Volume (from WebSocket)',
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
            
            # Connection status with color
            status_color = "#27ae60" if self.connected else "#e74c3c"
            status_text = f"🟢 {self.connection_status}" if self.connected else f"🔴 {self.connection_status}"
            
            return (
                price_fig,
                spread_fig,
                volume_fig,
                last_price_text,
                spread_text,
                updates_text,
                volume_text,
                status_text
            )
    
    # ========================================================================
    # SERVER CONTROL
    # ========================================================================
    
    def run_server(self, host='127.0.0.1', port=8050, debug=False):
        """Run Dash server (blocking call)"""
        logger.info(f"Starting Dash WebSocket consumer server on {host}:{port}")
        self.app.run_server(host=host, port=port, debug=debug, use_reloader=False)


