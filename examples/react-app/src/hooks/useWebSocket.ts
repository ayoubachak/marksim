import { useEffect, useRef, useState, useCallback } from 'react'
import type { WebSocketMessage } from '@/types'

export interface UseWebSocketReturn {
  isConnected: boolean
  error: Error | null
  connect: () => void
  disconnect: () => void
  send: (data: unknown) => void
  addMessageHandler: (handler: (message: WebSocketMessage) => void) => () => void
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Array<(message: WebSocketMessage) => void>>([])

  const addMessageHandler = useCallback((handler: (message: WebSocketMessage) => void) => {
    handlersRef.current.push(handler)
    return () => {
      const index = handlersRef.current.indexOf(handler)
      if (index > -1) {
        handlersRef.current.splice(index, 1)
      }
    }
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.warn('Already connected')
      return
    }

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        setError(null)
        console.log('WebSocket connected')
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage
          handlersRef.current.forEach(handler => {
            try {
              handler(message)
            } catch (err) {
              console.error('Error in message handler:', err)
            }
          })
        } catch (err) {
          console.error('Error parsing message:', err)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        console.log('WebSocket disconnected')
      }

      ws.onerror = () => {
        console.error('WebSocket error')
        setError(new Error('WebSocket error'))
        setIsConnected(false)
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error')
      setError(error)
      console.error('Failed to create WebSocket:', error)
    }
  }, [url])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket not connected')
    }
  }, [])

  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return { isConnected, error, connect, disconnect, send, addMessageHandler }
}

