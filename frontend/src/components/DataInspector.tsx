/**
 * DataInspector - Floating popup that shows data details when clicking an edge.
 * Displays port name, data type, and a preview of the data value.
 */
import { useEffect, useRef } from 'react';

export interface DataInspectorProps {
  x: number;
  y: number;
  data: Record<string, unknown>;
  edgeLabel: string;
  onClose: () => void;
}

/**
 * Format a single value for display. Handles array summaries
 * ({_type: "array", length, first_10, ...}) and scalar values.
 */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return String(value);
  }

  if (typeof value === 'object' && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;

    // Array summary format from backend
    if (obj._type === 'array') {
      const len = typeof obj.length === 'number' ? obj.length : '?';
      const first10 = Array.isArray(obj.first_10) ? obj.first_10 : [];
      const preview = first10.map(String).join(', ');
      const suffix = (typeof obj.length === 'number' && obj.length > 10)
        ? ', ...'
        : '';
      return `Array(${len}) [${preview}${suffix}]`;
    }

    // Generic object - show JSON truncated
    const json = JSON.stringify(obj);
    if (json.length > 120) {
      return json.slice(0, 117) + '...';
    }
    return json;
  }

  if (Array.isArray(value)) {
    const preview = value.slice(0, 10).map(String).join(', ');
    const suffix = value.length > 10 ? ', ...' : '';
    return `Array(${value.length}) [${preview}${suffix}]`;
  }

  return String(value);
}

/**
 * Infer the display type of a value.
 */
function inferType(value: unknown): string {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return 'array';
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    if (obj._type === 'array') return 'array';
    return 'object';
  }
  return typeof value;
}

export function DataInspector({ x, y, data, edgeLabel, onClose }: DataInspectorProps) {
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as HTMLElement)) {
        onClose();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [onClose]);

  const entries = Object.entries(data);

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        left: x,
        top: y,
        background: '#2A2A2A',
        border: '1px solid #555',
        borderRadius: 6,
        minWidth: 240,
        maxWidth: 420,
        zIndex: 10000,
        boxShadow: '0 6px 20px rgba(0,0,0,0.6)',
        fontFamily: "'Consolas', 'Fira Code', monospace",
        fontSize: 11,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px',
          borderBottom: '1px solid #444',
          background: '#252525',
          borderRadius: '6px 6px 0 0',
        }}
      >
        <span style={{ color: '#ccc', fontWeight: 700, fontSize: 11 }}>
          {edgeLabel || 'Edge Data'}
        </span>
        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#888',
            fontSize: 14,
            cursor: 'pointer',
            padding: '0 2px',
            lineHeight: 1,
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = '#eee';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = '#888';
          }}
        >
          {'\u00D7'}
        </button>
      </div>

      {/* Data entries */}
      <div style={{ padding: '6px 0', maxHeight: 300, overflowY: 'auto' }}>
        {entries.length === 0 && (
          <div style={{ padding: '8px 10px', color: '#666' }}>
            No data available.
          </div>
        )}
        {entries.map(([key, value]) => {
          const typeLabel = inferType(value);
          return (
            <div
              key={key}
              style={{
                padding: '4px 10px',
                borderBottom: '1px solid #333',
              }}
            >
              {/* Port name and type */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  marginBottom: 2,
                }}
              >
                <span style={{ color: '#60A5FA', fontWeight: 600 }}>
                  {key}
                </span>
                <span
                  style={{
                    color: '#888',
                    fontSize: 9,
                    background: '#333',
                    borderRadius: 3,
                    padding: '1px 5px',
                  }}
                >
                  {typeLabel}
                </span>
              </div>

              {/* Value preview */}
              <div
                style={{
                  color: '#ccc',
                  wordBreak: 'break-all',
                  whiteSpace: 'pre-wrap',
                  fontSize: 10,
                  lineHeight: 1.4,
                  maxHeight: 80,
                  overflowY: 'auto',
                }}
              >
                {formatValue(value)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
