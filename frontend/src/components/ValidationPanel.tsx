/**
 * ValidationPanel - Bottom panel showing workflow validation issues.
 * Displays errors, warnings, and info messages with clickable node references.
 */
import { useMemo } from 'react';

export interface ValidationIssue {
  level: 'error' | 'warning' | 'info';
  node_id: string | null;
  message: string;
}

export interface ValidationPanelProps {
  issues: ValidationIssue[];
  onValidate: () => void;
  onHighlightNode?: (nodeId: string) => void;
  visible: boolean;
}

const LEVEL_CONFIG: Record<
  ValidationIssue['level'],
  { icon: string; color: string; bgHover: string }
> = {
  error: { icon: '\u25CF', color: '#EF4444', bgHover: '#3D1515' },
  warning: { icon: '\u25B2', color: '#FBBF24', bgHover: '#3D3215' },
  info: { icon: '\u25CF', color: '#60A5FA', bgHover: '#15253D' },
};

export function ValidationPanel({
  issues,
  onValidate,
  onHighlightNode,
  visible,
}: ValidationPanelProps) {
  const counts = useMemo(() => {
    let errors = 0;
    let warnings = 0;
    let infos = 0;
    for (const issue of issues) {
      if (issue.level === 'error') errors++;
      else if (issue.level === 'warning') warnings++;
      else infos++;
    }
    return { errors, warnings, infos };
  }, [issues]);

  if (!visible) return null;

  return (
    <div
      style={{
        height: 200,
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
          background: '#222',
          borderBottom: '1px solid #333',
          flexShrink: 0,
        }}
      >
        <span style={{ color: '#ccc', fontWeight: 700, fontSize: 11 }}>
          Validation
        </span>

        {/* Counts */}
        {counts.errors > 0 && (
          <span style={{ color: '#EF4444', fontSize: 10 }}>
            {counts.errors} error{counts.errors !== 1 ? 's' : ''}
          </span>
        )}
        {counts.warnings > 0 && (
          <span style={{ color: '#FBBF24', fontSize: 10 }}>
            {counts.warnings} warning{counts.warnings !== 1 ? 's' : ''}
          </span>
        )}
        {counts.errors === 0 && counts.warnings === 0 && issues.length > 0 && (
          <span style={{ color: '#10B981', fontSize: 10 }}>
            No issues found
          </span>
        )}
        {issues.length === 0 && (
          <span style={{ color: '#666', fontSize: 10 }}>
            Click Validate to check workflow
          </span>
        )}

        <span style={{ flex: 1 }} />

        {/* Validate button */}
        <button onClick={onValidate} style={toolBtnStyle}>
          Validate
        </button>
      </div>

      {/* Issue list */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '2px 0',
        }}
      >
        {issues.map((issue, i) => {
          const config = LEVEL_CONFIG[issue.level];
          return (
            <div
              key={i}
              style={{
                padding: '3px 8px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: issue.node_id ? 'pointer' : 'default',
                background:
                  issue.level === 'error' ? '#2D1111' : 'transparent',
              }}
              onClick={() => {
                if (issue.node_id) onHighlightNode?.(issue.node_id);
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLDivElement).style.background =
                  issue.node_id ? config.bgHover : (
                    issue.level === 'error' ? '#2D1111' : 'transparent'
                  );
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLDivElement).style.background =
                  issue.level === 'error' ? '#2D1111' : 'transparent';
              }}
            >
              {/* Level icon */}
              <span
                style={{
                  color: config.color,
                  fontSize: issue.level === 'warning' ? 9 : 10,
                  flexShrink: 0,
                  width: 14,
                  textAlign: 'center',
                }}
              >
                {config.icon}
              </span>

              {/* Node ID */}
              {issue.node_id && (
                <span
                  style={{
                    color: '#60A5FA',
                    textDecoration: 'underline',
                    flexShrink: 0,
                    minWidth: 80,
                    fontSize: 10,
                  }}
                >
                  {issue.node_id}
                </span>
              )}
              {!issue.node_id && (
                <span
                  style={{
                    color: '#666',
                    flexShrink: 0,
                    minWidth: 80,
                    fontSize: 10,
                  }}
                >
                  workflow
                </span>
              )}

              {/* Message */}
              <span
                style={{
                  color:
                    issue.level === 'error'
                      ? '#F87171'
                      : issue.level === 'warning'
                        ? '#FDE68A'
                        : '#ccc',
                }}
              >
                {issue.message}
              </span>
            </div>
          );
        })}

        {issues.length === 0 && (
          <div style={{ padding: 16, color: '#555', textAlign: 'center' }}>
            No validation results yet. Click "Validate" to check your workflow.
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
