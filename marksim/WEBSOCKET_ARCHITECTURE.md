# WebSocket Streaming Architecture Demo

This demonstrates the **decoupled architecture** where Dash acts as a pure consumer of the WebSocket stream.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│           Market Simulation (Producer)              │
│  ┌─────────────────────────────────────┐           │
│  │     AsyncTimeEngine + Agents        │           │
│  └──────────────┬──────────────────────┘           │
│                 │                                    │
│     ┌───────────┴────────────┐                      │
│     ▼                        ▼                       │
│  ┌─────────┐           ┌──────────┐                │
│  │ Agents  │◄─────────►│OrderBook │                │
│  │ (async) │           │(lockfree)│                │
│  └─────────┘           └─────┬────┘                │
│                               │                      │
└───────────────────────────────┼──────────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │  BoundedMarketData  │
                    │      Stream          │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  WebSocket Server   │
                    │   (ws://8765)       │
                    └─────────┬───────────┘
                              │
                    ┌─────────┴───────────┐
                    ▼                     ▼
            ┌─────────────┐      ┌─────────────┐
            │ Dash Consumer│      │ Other Clients│
            │ (Port 8050) │      │ (Any Language)│
            └─────────────┘      └─────────────┘
```

## 🚀 Running the Demo

### 1. Start the WebSocket Simulation Server

```bash
python -m marksim.main
```

This starts:
- Market simulation (10x speed)
- WebSocket server on `ws://localhost:8765`
- Data archiver
- Memory monitor

### 2. Start the Dash Consumer (Separate Process)

```bash
python -m marksim.dash_consumer
```

This starts:
- Dash dashboard on `http://localhost:8050`
- WebSocket client connecting to `ws://localhost:8765`
- Real-time visualization of market data

### 3. Test with WebSocket Client

```bash
python -m marksim.test_websocket
```

This demonstrates:
- Raw WebSocket connection
- JSON message parsing
- Real-time data consumption

## 🔌 WebSocket Protocol

The WebSocket server streams JSON messages with this format:

```json
{
  "timestamp": 1703123456789000,
  "symbol": "BTC/USD",
  "last_price": 50000.50,
  "bid_price": 49999.00,
  "ask_price": 50001.00,
  "bid_size": 1.5,
  "ask_size": 2.0,
  "volume_24h": 1250.75,
  "trade_count": 3
}
```

## 🎯 Key Benefits Demonstrated

1. **Decoupled Architecture**: Dash is completely independent of the simulation
2. **Multiple Consumers**: Any number of clients can connect to the WebSocket
3. **Language Agnostic**: Consumers can be written in any language
4. **Real-time Streaming**: Low-latency data distribution
5. **Fault Tolerance**: If Dash crashes, simulation continues
6. **Scalability**: Add more consumers without affecting simulation performance

## 🔧 Custom Consumers

You can create custom consumers in any language:

### Python
```python
import asyncio
import websockets
import json

async def consumer():
    async with websockets.connect("ws://localhost:8765") as websocket:
        async for message in websocket:
            data = json.loads(message)
            print(f"Price: ${data['last_price']}")
```

### JavaScript
```javascript
const ws = new WebSocket('ws://localhost:8765');
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log(`Price: $${data.last_price}`);
};
```

### Go
```go
package main

import (
    "encoding/json"
    "github.com/gorilla/websocket"
)

func main() {
    conn, _, err := websocket.DefaultDialer.Dial("ws://localhost:8765", nil)
    if err != nil {
        log.Fatal(err)
    }
    defer conn.Close()
    
    for {
        _, message, err := conn.ReadMessage()
        if err != nil {
            log.Println(err)
            return
        }
        
        var data map[string]interface{}
        json.Unmarshal(message, &data)
        fmt.Printf("Price: $%.2f\n", data["last_price"])
    }
}
```

This architecture proves that the streaming system is **robust, scalable, and language-agnostic**! 🎉

