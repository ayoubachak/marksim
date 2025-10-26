"""
REST API for batch simulation control.
"""
from flask import Flask, request, jsonify
from typing import List, Dict
import asyncio
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Store current simulation
current_simulation = None


@app.route('/api/simulation/configure', methods=['POST'])
def configure_simulation():
    """Configure simulation agents"""
    data = request.json
    
    agent_configs = data.get('agents', [])
    duration = data.get('duration_seconds', 60)
    initial_price = data.get('initial_price', 50000)
    
    logger.info(f"Configuring simulation: {len(agent_configs)} agent types")
    
    # Create agents based on config
    agents = []
    from marksim.agents import (
        MarketMakerAgent, NoiseTraderAgent, 
        InformedTraderAgent, TakerAgent
    )
    
    agent_id_counter = 0
    
    for agent_config in agent_configs:
        agent_type = agent_config['type']
        count = agent_config.get('count', 1)
        params = agent_config.get('params', {})
        
        for i in range(count):
            agent_id = f"{agent_type.lower()}_{agent_id_counter}"
            
            if agent_type == 'MarketMaker':
                agent = MarketMakerAgent(
                    agent_id=agent_id,
                    spread=Decimal(str(params.get('spread', 0.01))),
                    order_size=Decimal(str(params.get('order_size', 1.0))),
                    max_position=Decimal(str(params.get('max_position', 10.0)))
                )
            elif agent_type == 'NoiseTrader':
                agent = NoiseTraderAgent(
                    agent_id=agent_id,
                    trade_probability=params.get('trade_probability', 0.1),
                    max_size=Decimal(str(params.get('max_size', 5.0)))
                )
            elif agent_type == 'InformedTrader':
                agent = InformedTraderAgent(
                    agent_id=agent_id,
                    bias_probability=params.get('bias_probability', 0.3),
                    bias_strength=params.get('bias_strength', 0.02),
                    order_size=Decimal(str(params.get('order_size', 2.0)))
                )
            elif agent_type == 'Taker':
                agent = TakerAgent(
                    agent_id=agent_id,
                    trade_probability=params.get('trade_probability', 0.15),
                    price_deviation=params.get('price_deviation', 0.01),
                    min_size=Decimal(str(params.get('min_size', 0.5))),
                    max_size=Decimal(str(params.get('max_size', 3.0)))
                )
            else:
                return jsonify({'error': f'Unknown agent type: {agent_type}'}), 400
            
            agents.append(agent)
            agent_id_counter += 1
    
    return jsonify({
        'success': True,
        'agent_count': len(agents)
    })


@app.route('/api/simulation/run', methods=['POST'])
def run_simulation():
    """Run batch simulation and return results"""
    try:
        from marksim.simulation.batch_simulator import BatchSimulator
        
        data = request.json
        duration = data.get('duration_seconds', 60)
        initial_price = Decimal(str(data.get('initial_price', 50000)))
        
        # Get agents from configuration
        agent_configs = data.get('agents', [])
        
        # Create agents
        agents = []
        # ... (same agent creation logic as above)
        
        # Run simulation
        simulator = BatchSimulator(agents, initial_price, duration)
        result = asyncio.run(simulator.run())
        
        # Return results
        return jsonify({
            'trades': result.trades,
            'order_book_states': result.order_book_states,
            'agent_stats': result.agent_stats,
            'final_price': float(result.final_price),
            'total_trades': result.total_trades
        })
        
    except Exception as e:
        logger.error(f"Simulation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/simulation/status', methods=['GET'])
def get_status():
    """Get simulation status"""
    return jsonify({
        'running': current_simulation is not None
    })


if __name__ == '__main__':
    app.run(port=5000)

