import { useEffect, useRef } from 'react'
import { init, dispose } from 'klinecharts'
import type { KlineChart } from 'klinecharts'

interface KlineChartProps {
  candleData: Array<{
    timestamp: number
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
  currentCandle?: {
    timestamp: number
    open: number
    high: number
    low: number
    close: number
    volume: number
  }
}

export function KlineChart({ candleData, currentCandle }: KlineChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<KlineChart | null>(null)

  useEffect(() => {
    if (!chartRef.current) return

    // Initialize chart
    chartInstance.current = init(chartRef.current)
    
    if (chartInstance.current) {
      // Set chart styles
      chartInstance.current.setStyles({
        candle: {
          type: 'candle_solid',
          bar: {
            upColor: '#26a69a',
            downColor: '#ef5350',
            noChangeColor: '#888888'
          }
        },
        yAxis: {
          type: 'normal'
        },
        crosshair: {
          show: true
        }
      })
    }

    return () => {
      if (chartInstance.current) {
        dispose(chartInstance.current)
        chartInstance.current = null
      }
    }
  }, [])

  // Update chart when data changes
  useEffect(() => {
    if (!chartInstance.current) return

    // Combine closed candles with current forming candle
    const allCandles = [...candleData]
    if (currentCandle) {
      allCandles.push(currentCandle)
    }

    if (allCandles.length > 0) {
      chartInstance.current.applyNewData(allCandles)
    }
  }, [candleData, currentCandle])

  return <div ref={chartRef} className="w-full h-full" />
}

