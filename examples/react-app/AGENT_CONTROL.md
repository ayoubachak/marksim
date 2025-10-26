# Agent Control Panel - Implementation Guide

## ✅ What's Implemented

### Frontend (React App)
- ✅ Agent Control Panel UI with add/delete/edit
- ✅ WebSocket integration for agent commands
- ✅ Live parameter editing for agents
- ✅ Real-time config display
- ✅ Agent creation with type selection
- ✅ Agent deletion
- ✅ Agent parameter updates

### Current Features

#### Agent Creation
- Select agent type (MarketMaker, NoiseTrader, InformedTrader)
- Automatic default config per type
- WebSocket message sent: `{ type: 'agent_command', action: 'create', agent_type, config }`

#### Agent Deletion
- Click trash icon to delete
- WebSocket message sent: `{ type: 'agent_command', action: 'delete', agent_id }`

#### Live Parameter Editing
- Click edit icon to modify parameters
- All numeric fields become editable inputs
- Save changes or cancel
- WebSocket message sent: `{ type: 'agent_command', action: 'update', agent_id, config }`

## 🔧 Backend Integration Required

The WebSocket server needs to handle these commands:

```python
# In marksim/streaming/websocket.py

async def handle_client_message(self, websocket, message):
    """Handle agent management commands from clients"""
    if message.get('type') == 'agent_command':
        action = message.get('action')
        
        if action == 'create':
            agent_type = message['agent_type']
            config = message['config']
            # Create new agent in simulation
            await self.simulation.add_agent(agent_type, config)
            
        elif action == 'delete':
            agent_id = message['agent_id']
            # Remove agent from simulation
            await self.simulation.remove_agent(agent_id)
            
        elif action == 'update':
            agent_id = message['agent_id']
            config = message['config']
            # Update agent parameters
            await self.simulation.update_agent(agent_id, config)
```

## 🎯 Next Steps

1. **Implement backend handlers** in `MarketSimulation`:
   - `add_agent(agent_type, config)` - Create new agent
   - `remove_agent(agent_id)` - Delete agent
   - `update_agent(agent_id, config)` - Update agent parameters

2. **Add message handling** in WebSocket server to process `agent_command` messages

3. **Emit confirmations** back to client when agent operations complete

4. **Update agent configs** stream to reflect changes immediately

## 📝 Message Format

### Create Agent
```json
{
  "type": "agent_command",
  "action": "create",
  "agent_type": "MarketMaker",
  "config": {
    "spread": 0.01,
    "order_size": 1.0,
    "max_position": 10.0
  }
}
```

### Delete Agent
```json
{
  "type": "agent_command",
  "action": "delete",
  "agent_id": "mm_0"
}
```

### Update Agent
```json
{
  "type": "agent_command",
  "action": "update",
  "agent_id": "mm_0",
  "config": {
    "spread": 0.02,
    "order_size": 2.0
  }
}
```

