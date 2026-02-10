/**
 * ErrorTracePanel - Side panel showing execution error details.
 * Displays error message, stack trace, failed node info, and auto-suggestions.
 */
import { useMemo } from 'react';

export interface ErrorTraceInfo {
  node_id: string;
  node_type: string;
  message: string;
  stack_trace: string;
}

export interface ErrorTracePanelProps {
  error: ErrorTraceInfo | null;
  visible: boolean;
  onClose: () => void;
  onHighlightNode?: (nodeId: string) => void;
}

/**
 * Common fix suggestions based on error message patterns.
 */
function getSuggestions(error: ErrorTraceInfo): string[] {
  const msg = error.message.toLowerCase();
  const suggestions: string[] = [];

  if (msg.includes('key') || msg.includes('missing') || msg.includes('required')) {
    suggestions.push('Check that all required input connections are present.');
  }
  if (msg.includes('type') || msg.includes('cannot convert') || msg.includes('cast')) {
    suggestions.push('Verify that input data types match the expected port types.');
  }
  if (msg.includes('index') || msg.includes('range') || msg.includes('bound')) {
    suggestions.push('Check that input arrays are not empty and indices are within range.');
  }
  if (msg.includes('none') || msg.includes('null') || msg.includes('undefined')) {
    suggestions.push('Ensure upstream nodes are producing valid (non-null) output.');
  }
  if (msg.includes('connection') || msg.includes('timeout') || msg.includes('network')) {
    suggestions.push('Check network connectivity and retry the execution.');
  }
  if (msg.includes('import') || msg.includes('module') || msg.includes('not found')) {
    suggestions.push('Ensure the required plugin is installed and registered.');
  }
  if (msg.includes('shape') || msg.includes('dimension') || msg.includes('size')) {
    suggestions.push('Verify that input array shapes/dimensions are compatible.');
  }
  if (msg.includes('permission') || msg.includes('access') || msg.includes('denied')) {
    suggestions.push('Check file/resource permissions.');
  }

  // Always suggest these generic fixes
  suggestions.push('Check input connections to this node.');
  suggestions.push('Verify data types from upstream nodes.');

  // Deduplicate
  return [...new Set(suggestions)];
}

export function ErrorTracePanel({
  error,
  visible,
  onClose,
  onHighlightNode,
}: ErrorTracePanelProps) {
  const suggestions = useMemo(() => {
    if (!error) return [];
    return getSuggestions(error);
  }, [error]);

  if (!visible || !error) return null;

  return (
    <div
      style={{
        height: 280,
        background: '#1A1A1A',
        borderTop: '1px solid #333',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: "'Consolas', 'Fira Code', monospace",
        fontSize: 11,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '4px 8px',
          background: '#2D1111',
          borderBottom: '1px solid #442222',
          flexShrink: 0,
        }}
      >
        {/* Error icon */}
        <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
          <circle cx="7" cy="7" r="6" fill="#EF4444" />
          <line x1="4.5" y1="4.5" x2="9.5" y2="9.5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="9.5" y1="4.5" x2="4.5" y2="9.5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
        </svg>

        <span style={{ color: '#F87171', fontWeight: 700, fontSize: 11 }}>
          Error Trace
        </span>

        {/* Node link */}
        <span
          onClick={() => onHighlightNode?.(error.node_id)}
          style={{
            color: '#60A5FA',
            textDecoration: 'underline',
            cursor: 'pointer',
            fontSize: 10,
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLSpanElement).style.color = '#93C5FD';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLSpanElement).style.color = '#60A5FA';
          }}
          title="Click to highlight this node on the canvas"
        >
          {error.node_type}:{error.node_id}
        </span>

        <span style={{ flex: 1 }} />

        {/* Close button */}
        <button
          onClick={onClose}
          style={{
            background: '#333',
            border: '1px solid #555',
            borderRadius: 3,
            color: '#999',
            padding: '2px 8px',
            fontSize: 10,
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = '#eee';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = '#999';
          }}
        >
          Close
        </button>
      </div>

      {/* Content area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 0,
        }}
      >
        {/* Error message */}
        <div
          style={{
            padding: '8px 10px',
            borderBottom: '1px solid #333',
          }}
        >
          <div style={{ color: '#888', fontSize: 9, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Error Message
          </div>
          <div style={{ color: '#F87171', fontSize: 12, lineHeight: 1.5, wordBreak: 'break-word' }}>
            {error.message}
          </div>
        </div>

        {/* Stack trace */}
        <div
          style={{
            padding: '8px 10px',
            borderBottom: '1px solid #333',
          }}
        >
          <div style={{ color: '#888', fontSize: 9, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Stack Trace
          </div>
          <pre
            style={{
              margin: 0,
              color: '#999',
              fontSize: 10,
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              maxHeight: 120,
              overflowY: 'auto',
              background: '#111',
              borderRadius: 4,
              padding: '6px 8px',
              border: '1px solid #333',
            }}
          >
            {error.stack_trace}
          </pre>
        </div>

        {/* Auto-suggestions */}
        <div
          style={{
            padding: '8px 10px',
          }}
        >
          <div style={{ color: '#888', fontSize: 9, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Suggested Fixes
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {suggestions.map((suggestion, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 6,
                  padding: '3px 6px',
                  background: '#1E2A1E',
                  borderRadius: 3,
                  border: '1px solid #2D442D',
                }}
              >
                <span style={{ color: '#10B981', flexShrink: 0, fontSize: 10, lineHeight: '16px' }}>
                  {'\u2192'}
                </span>
                <span style={{ color: '#A7F3D0', fontSize: 10, lineHeight: '16px' }}>
                  {suggestion}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
