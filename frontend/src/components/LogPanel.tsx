/**
 * Log Panel - Resizable bottom panel showing execution logs.
 * Supports filtering by level, node, and search text.
 */
import { useState, useMemo, useRef, useEffect } from 'react';

export interface LogEntry {
  timestamp: number;
  level: string;
  node_id?: string;
  node_type?: string;
  message: string;
  event?: string;
}

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: '#9CA3AF',
  INFO: '#60A5FA',
  WARN: '#FBBF24',
  ERROR: '#EF4444',
  SYSTEM: '#A78BFA',
};

const LEVELS = ['ALL', 'DEBUG', 'INFO', 'WARN', 'ERROR'] as const;

export function LogPanel({
  logs,
  onClear,
  onHighlightNode,
  visible,
}: {
  logs: LogEntry[];
  onClear: () => void;
  onHighlightNode?: (nodeId: string) => void;
  visible: boolean;
}) {
  const [levelFilter, setLevelFilter] = useState<string>('ALL');
  const [nodeFilter, setNodeFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs.length, autoScroll]);

  // Unique node IDs for filter dropdown
  const nodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const log of logs) {
      if (log.node_id) ids.add(log.node_id);
    }
    return Array.from(ids).sort();
  }, [logs]);

  // Filtered logs
  const filtered = useMemo(() => {
    return logs.filter((log) => {
      if (levelFilter !== 'ALL' && log.level !== levelFilter) return false;
      if (nodeFilter && log.node_id !== nodeFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        const text = `${log.message} ${log.node_id ?? ''} ${log.node_type ?? ''}`.toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    });
  }, [logs, levelFilter, nodeFilter, search]);

  const exportLogs = () => {
    const text = filtered
      .map((l) => {
        const time = new Date(l.timestamp * 1000).toISOString().slice(11, 23);
        const source = l.node_type ? `[${l.node_type}:${l.node_id}]` : `[${l.event ?? 'system'}]`;
        return `${time} [${l.level}] ${source} ${l.message}`;
      })
      .join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pipestudio-logs-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!visible) return null;

  return (
    <div
      style={{
        height: 220,
        background: '#1A1A1A',
        borderTop: '1px solid #333',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: "'Consolas', 'Fira Code', monospace",
        fontSize: 11,
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '4px 8px',
          background: '#222',
          borderBottom: '1px solid #333',
          flexShrink: 0,
        }}
      >
        {/* Level filter tabs */}
        {LEVELS.map((level) => (
          <button
            key={level}
            onClick={() => setLevelFilter(level)}
            style={{
              background: levelFilter === level ? '#444' : 'transparent',
              border: '1px solid',
              borderColor: levelFilter === level ? '#666' : 'transparent',
              borderRadius: 3,
              color: level === 'ALL' ? '#ccc' : (LEVEL_COLORS[level] ?? '#ccc'),
              padding: '2px 8px',
              fontSize: 10,
              cursor: 'pointer',
              fontWeight: levelFilter === level ? 700 : 400,
            }}
          >
            {level}
          </button>
        ))}

        <span style={{ color: '#444' }}>|</span>

        {/* Node filter */}
        <select
          value={nodeFilter}
          onChange={(e) => setNodeFilter(e.target.value)}
          style={{
            background: '#333',
            border: '1px solid #555',
            borderRadius: 3,
            color: '#ccc',
            padding: '2px 4px',
            fontSize: 10,
            maxWidth: 140,
          }}
        >
          <option value="">All nodes</option>
          {nodeIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>

        {/* Search */}
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search..."
          style={{
            background: '#111',
            border: '1px solid #444',
            borderRadius: 3,
            color: '#ccc',
            padding: '2px 6px',
            fontSize: 10,
            width: 120,
            outline: 'none',
          }}
        />

        <span style={{ flex: 1 }} />

        {/* Count */}
        <span style={{ color: '#666', fontSize: 10 }}>
          {filtered.length}/{logs.length}
        </span>

        {/* Export */}
        <button onClick={exportLogs} title="Export logs" style={toolBtnStyle}>
          Export
        </button>

        {/* Clear */}
        <button onClick={onClear} title="Clear logs" style={toolBtnStyle}>
          Clear
        </button>
      </div>

      {/* Log entries */}
      <div
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
          setAutoScroll(atBottom);
        }}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '2px 0',
        }}
      >
        {filtered.map((log, i) => {
          const time = new Date(log.timestamp * 1000).toISOString().slice(11, 23);
          const source = log.node_type
            ? `[${log.node_type}:${log.node_id}]`
            : `[${log.event ?? 'system'}]`;

          return (
            <div
              key={i}
              onClick={() => log.node_id && onHighlightNode?.(log.node_id)}
              style={{
                padding: '1px 8px',
                display: 'flex',
                gap: 8,
                cursor: log.node_id ? 'pointer' : 'default',
                background: log.level === 'ERROR' ? '#2D1111' : 'transparent',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLDivElement).style.background =
                  log.level === 'ERROR' ? '#3D1515' : '#252525';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLDivElement).style.background =
                  log.level === 'ERROR' ? '#2D1111' : 'transparent';
              }}
            >
              <span style={{ color: '#555', flexShrink: 0 }}>{time}</span>
              <span style={{ color: LEVEL_COLORS[log.level] ?? '#999', flexShrink: 0, width: 40 }}>
                {log.level}
              </span>
              <span style={{ color: '#888', flexShrink: 0, minWidth: 150 }}>{source}</span>
              <span style={{ color: log.level === 'ERROR' ? '#F87171' : '#ccc' }}>
                {log.message}
              </span>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div style={{ padding: 16, color: '#555', textAlign: 'center' }}>
            {logs.length === 0 ? 'No logs yet. Execute a workflow to see logs.' : 'No matching logs.'}
          </div>
        )}
      </div>
    </div>
  );
}

const toolBtnStyle: React.CSSProperties = {
  background: '#333',
  border: '1px solid #555',
  borderRadius: 3,
  color: '#999',
  padding: '2px 8px',
  fontSize: 10,
  cursor: 'pointer',
};
