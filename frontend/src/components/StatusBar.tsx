/**
 * StatusBar - Thin bottom bar showing system status information.
 * Displays connection state, plugin count, node/edge counts, memory usage, and version.
 */

export interface StatusBarProps {
  connected: boolean;
  pluginCount: number;
  memoryMb: number;
  version: string;
  nodeCount: number;
  edgeCount: number;
}

export function StatusBar({
  connected,
  pluginCount,
  memoryMb,
  version,
  nodeCount,
  edgeCount,
}: StatusBarProps) {
  return (
    <div style={barStyle}>
      {/* Left side: connection + plugins */}
      <div style={sectionStyle}>
        <span
          style={{
            color: connected ? '#10B981' : '#EF4444',
            fontSize: 10,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}
          title={connected ? 'Backend connected' : 'Backend disconnected'}
        >
          <span style={{ fontSize: 8 }}>{connected ? '\u25CF' : '\u25CF'}</span>
          {connected ? 'Connected' : 'Disconnected'}
        </span>

        <span style={separatorStyle}>|</span>

        <span style={labelStyle} title="Loaded plugins">
          {pluginCount} plugin{pluginCount !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Right side: node/edge count, memory, version */}
      <div style={sectionStyle}>
        <span style={labelStyle} title="Nodes on canvas">
          Nodes: {nodeCount}
        </span>

        <span style={separatorStyle}>|</span>

        <span style={labelStyle} title="Edges on canvas">
          Edges: {edgeCount}
        </span>

        <span style={separatorStyle}>|</span>

        <span style={labelStyle} title="Memory usage">
          Mem: {memoryMb.toFixed(1)} MB
        </span>

        <span style={separatorStyle}>|</span>

        <span style={labelStyle} title="PipeStudio version">
          v{version}
        </span>
      </div>
    </div>
  );
}

const barStyle: React.CSSProperties = {
  height: 24,
  background: '#181818',
  borderTop: '1px solid #333',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '0 12px',
  fontFamily: "'Consolas', 'Fira Code', monospace",
  fontSize: 10,
  flexShrink: 0,
  boxSizing: 'border-box',
};

const sectionStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
};

const separatorStyle: React.CSSProperties = {
  color: '#444',
  fontSize: 10,
  userSelect: 'none',
};

const labelStyle: React.CSSProperties = {
  color: '#888',
  fontSize: 10,
};
