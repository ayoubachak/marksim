import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Activity } from 'lucide-react'
import { formatDecimal } from '@/lib/utils'
import type { AgentConfig } from '@/types'

interface AgentConfigViewProps {
  agentConfigs: AgentConfig[]
}

export function AgentConfigView({ agentConfigs }: AgentConfigViewProps) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Agent Configurations
          </CardTitle>
          <CardDescription>Monitor and control agent parameters in real-time</CardDescription>
        </CardHeader>
        <CardContent>
          {agentConfigs.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No agents connected. Start the simulation server.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agentConfigs.map((agent, i) => (
                <Card key={i} className="bg-secondary/50">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">{agent.agent_id}</CardTitle>
                    <CardDescription className="text-xs uppercase tracking-wide">
                      {agent.agent_type}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {Object.entries(agent).map(([key, value]) => {
                      if (key === 'agent_id' || key === 'agent_type') return null
                      return (
                        <div key={key} className="flex justify-between text-sm border-b last:border-0 pb-2">
                          <span className="text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</span>
                          <span className="font-mono font-semibold">
                            {typeof value === 'number' ? formatDecimal(value) : value || 'N/A'}
                          </span>
                        </div>
                      )
                    })}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

