import { useEffect, useRef, useState } from 'react'

interface LogEntry {
  timestamp: string
  level: string
  message: string
  task_id?: string
  celery_task_id?: string
  module?: string
  function?: string
  line?: number
}

interface LogViewerProps {
  taskId?: string
  maxHeight?: string
}

export function LogViewer({ taskId, maxHeight = '500px' }: LogViewerProps) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const wsRef = useRef<WebSocket | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // 构建 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    let wsUrl = `${protocol}//${host}/api/ws/logs`
    
    if (taskId) {
      wsUrl += `?task_id=${encodeURIComponent(taskId)}`
    }

    // 创建 WebSocket 连接
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      console.log('✅ WebSocket 日志流已连接')
    }

    ws.onmessage = (event) => {
      try {
        const logEntry: LogEntry = JSON.parse(event.data)
        setLogs((prev) => [...prev, logEntry])
      } catch (error) {
        console.error('解析日志消息失败:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      setConnected(false)
    }

    ws.onclose = () => {
      setConnected(false)
      console.log('📡 WebSocket 日志流已断开')
    }

    // 清理函数
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [taskId])

  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const clearLogs = () => {
    setLogs([])
  }

  const getLevelColor = (level: string): string => {
    switch (level.toUpperCase()) {
      case 'ERROR':
        return '#c93641'
      case 'WARNING':
        return '#d97706'
      case 'INFO':
        return '#1f7ae0'
      case 'DEBUG':
        return '#6b7280'
      default:
        return '#48688c'
    }
  }

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp)
      const timeStr = date.toLocaleTimeString('zh-CN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
      const ms = String(date.getMilliseconds()).padStart(3, '0')
      return `${timeStr}.${ms}`
    } catch {
      return timestamp
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* 控制栏 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: connected ? '#0f8a5c' : '#c93641',
            }}
          />
          <span style={{ fontSize: '13px', color: '#48688c' }}>
            {connected ? '已连接' : '未连接'}
          </span>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#48688c' }}>
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          自动滚动
        </label>

        <button
          onClick={clearLogs}
          style={{
            padding: '4px 12px',
            fontSize: '13px',
            border: '1px solid #d4e1f1',
            borderRadius: '6px',
            background: '#ffffff',
            color: '#173a63',
            cursor: 'pointer',
          }}
        >
          清空日志
        </button>

        <span style={{ fontSize: '13px', color: '#48688c', marginLeft: 'auto' }}>
          共 {logs.length} 条日志
        </span>
      </div>

      {/* 日志容器 */}
      <div
        ref={containerRef}
        style={{
          maxHeight,
          overflowY: 'auto',
          border: '1px solid #d4e1f1',
          borderRadius: '12px',
          background: '#0e1524',
          padding: '12px',
          fontFamily: 'Consolas, Monaco, "Courier New", monospace',
          fontSize: '12px',
          lineHeight: '1.6',
        }}
      >
        {logs.length === 0 ? (
          <div style={{ color: '#6b7280', textAlign: 'center', padding: '40px 0' }}>
            等待日志...
          </div>
        ) : (
          logs.map((log, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                gap: '8px',
                marginBottom: '4px',
                color: '#e5e7eb',
              }}
            >
              <span style={{ color: '#6b7280', flexShrink: 0 }}>
                {formatTimestamp(log.timestamp)}
              </span>
              <span
                style={{
                  color: getLevelColor(log.level),
                  fontWeight: 600,
                  minWidth: '60px',
                  flexShrink: 0,
                }}
              >
                {log.level}
              </span>
              {log.task_id && (
                <span style={{ color: '#9ca3af', flexShrink: 0 }}>
                  [{log.task_id.slice(0, 8)}]
                </span>
              )}
              <span style={{ color: '#e5e7eb', wordBreak: 'break-word' }}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
