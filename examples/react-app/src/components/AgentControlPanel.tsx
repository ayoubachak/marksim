import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Plus, Trash2, Edit, Save, X } from 'lucide-react'
import type { AgentConfig } from '@/types'

interface AgentControlPanelProps {
  agentConfigs: AgentConfig[]
  onAddAgent: (type: string, config: Record<string, any>) => void
  onDeleteAgent: (agentId: string) => void
  onUpdateAgent: (agentId: string, config: Record<string, any>) => void
}

export function AgentControlPanel({ 
  agentConfigs, 
  onAddAgent, 
  onDeleteAgent, 
  onUpdateAgent 
}: AgentControlPanelProps) {
  const [showAddForm, setShowAddForm] = useState(false)
  const [newAgentType, setNewAgentType] = useState<'MarketMaker' | 'NoiseTrader' | 'InformedTrader'>('MarketMaker')
  const [editingAgent, setEditingAgent] = useState<string | null>(null)

  const handleAddAgent = () => {
    console.log('Adding agent:', newAgentType)
    const defaultConfig = getDefaultConfig(newAgentType)
    console.log('Default config:', defaultConfig)
    onAddAgent(newAgentType, defaultConfig)
    setShowAddForm(false)
    setNewAgentType('MarketMaker') // Reset to default
  }

  const getDefaultConfig = (type: string): Record<string, any> => {
    switch (type) {
      case 'MarketMaker':
        return { spread: 0.01, order_size: 1.0, max_position: 10.0 }
      case 'NoiseTrader':
        return { trade_probability: 0.1, max_size: 5.0 }
      case 'InformedTrader':
        return { bias_probability: 0.3, bias_strength: 0.02, order_size: 2.0 }
      default:
        return {}
    }
  }

  return (
    <div className="space-y-4">
      {/* Add Agent Button */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold">Agent Control Panel</h2>
          <p className="text-muted-foreground">Manage, create, and configure agents in real-time</p>
        </div>
        {!showAddForm && (
          <Button onClick={() => setShowAddForm(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            Add Agent
          </Button>
        )}
      </div>

      {/* Add Agent Form */}
      {showAddForm && (
        <Card>
          <CardHeader>
            <CardTitle>Create New Agent</CardTitle>
            <CardDescription>Select agent type and configure parameters</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Agent Type</label>
              <select
                value={newAgentType}
                onChange={(e) => setNewAgentType(e.target.value as any)}
                className="w-full p-2 rounded border bg-background"
              >
                <option value="MarketMaker">Market Maker</option>
                <option value="NoiseTrader">Noise Trader</option>
                <option value="InformedTrader">Informed Trader</option>
              </select>
            </div>
            <div className="flex gap-2">
              <Button 
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  console.log('Button clicked, calling handleAddAgent')
                  handleAddAgent()
                }} 
                className="gap-2"
              >
                <Save className="h-4 w-4" />
                Create Agent
              </Button>
              <Button variant="outline" onClick={() => setShowAddForm(false)} className="gap-2">
                <X className="h-4 w-4" />
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Agent List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agentConfigs.length === 0 ? (
          <div className="col-span-full text-center py-12 text-muted-foreground">
            <p className="text-lg mb-2">No agents configured</p>
            <p className="text-sm">Click "Add Agent" to create your first agent</p>
          </div>
        ) : (
          agentConfigs.map((agent, i) => {
            return (
              <AgentCard
                key={agent.agent_id || `agent-${i}`}
                agent={agent}
                onDelete={() => {
                  console.log('onDelete called with agent_id:', agent.agent_id)
                  onDeleteAgent(agent.agent_id)
                }}
                onUpdate={(config) => {
                  console.log('onUpdate called with agent_id:', agent.agent_id, 'config:', config)
                  onUpdateAgent(agent.agent_id, config)
                }}
                isEditing={editingAgent === agent.agent_id}
                onEdit={() => {
                  console.log('onEdit called, setting editingAgent to:', agent.agent_id)
                  setEditingAgent(agent.agent_id)
                }}
                onCancelEdit={() => {
                  console.log('onCancelEdit called')
                  setEditingAgent(null)
                }}
              />
            )
          })
        )}
      </div>
    </div>
  )
}

interface AgentCardProps {
  agent: AgentConfig
  onDelete: () => void
  onUpdate: (config: Record<string, any>) => void
  isEditing: boolean
  onEdit: () => void
  onCancelEdit: () => void
}

function AgentCard({ agent, onDelete, onUpdate, isEditing, onEdit, onCancelEdit }: AgentCardProps) {
  const [localConfig, setLocalConfig] = useState(agent)

  // Update localConfig when agent changes (e.g., from backend updates)
  useEffect(() => {
    setLocalConfig(agent)
  }, [agent])

  const handleSave = () => {
    console.log('Saving agent config:', localConfig)
    const updates: Record<string, any> = {}
    // Extract only the config parameters (exclude agent_id and agent_type)
    Object.entries(localConfig).forEach(([key, value]) => {
      if (key !== 'agent_id' && key !== 'agent_type') {
        updates[key] = value
      }
    })
    console.log('Sending updates:', updates)
    onUpdate(updates)
    onCancelEdit()
  }

  const updateParam = (key: string, value: string) => {
    const numValue = parseFloat(value)
    setLocalConfig(prev => ({
      ...prev,
      [key]: isNaN(numValue) ? value : numValue
    }))
  }

  return (
    <Card className="bg-secondary/50">
      <CardHeader className="pb-3">
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-base">{agent.agent_id}</CardTitle>
            <CardDescription className="text-xs uppercase tracking-wide mt-1">
              {agent.agent_type}
            </CardDescription>
          </div>
          <div className="flex gap-1">
            {!isEditing ? (
              <>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    console.log('Edit clicked')
                    onEdit()
                  }}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={onDelete}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </>
            ) : (
              <>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={handleSave}
                >
                  <Save className="h-4 w-4 text-green-600" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={onCancelEdit}
                >
                  <X className="h-4 w-4" />
                </Button>
              </>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {Object.entries(isEditing ? localConfig : agent).map(([key, value]) => {
          if (key === 'agent_id' || key === 'agent_type') return null
          
          if (isEditing && typeof value === 'number') {
            return (
              <div key={key} className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</span>
                <input
                  type="number"
                  step="0.0001"
                  value={value}
                  onChange={(e) => updateParam(key, e.target.value)}
                  className="w-24 p-1 rounded border bg-background font-mono text-xs"
                />
              </div>
            )
          }
          
          return (
            <div key={key} className="flex justify-between text-sm">
              <span className="text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="font-mono font-semibold">
                {typeof value === 'number' ? value.toFixed(4) : value || 'N/A'}
              </span>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

