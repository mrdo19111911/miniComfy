/**
 * NodeDocTooltip - Floating tooltip that appears on hover over palette items
 * or node headers, showing node documentation, port info, and type badges.
 */

export interface PortInput {
  name: string;
  type: string;
  required: boolean;
  default: any;
}

export interface PortOutput {
  name: string;
  type: string;
}

export interface NodeSpec {
  label: string;
  type: string;
  category: string;
  description: string;
  doc: string;
  inputs: PortInput[];
  outputs: PortOutput[];
}

export interface NodeDocTooltipProps {
  spec: NodeSpec | null;
  x: number;
  y: number;
  visible: boolean;
}

/** Color mapping for port type badges */
function typeColor(type: string): string {
  switch (type.toLowerCase()) {
    case 'string':
      return '#10B981';
    case 'number':
    case 'int':
    case 'float':
      return '#3B82F6';
    case 'boolean':
    case 'bool':
      return '#F59E0B';
    case 'array':
    case 'list':
      return '#8B5CF6';
    case 'object':
    case 'dict':
      return '#EC4899';
    case 'file':
    case 'path':
      return '#F97316';
    default:
      return '#6B7280';
  }
}

/** Color mapping for category badges */
function categoryColor(category: string): string {
  switch (category.toLowerCase()) {
    case 'input':
      return '#10B981';
    case 'output':
      return '#3B82F6';
    case 'transform':
      return '#8B5CF6';
    case 'analysis':
      return '#F59E0B';
    case 'visualization':
    case 'viz':
      return '#EC4899';
    case 'solver':
      return '#EF4444';
    case 'compute':
      return '#7C3AED';
    default:
      return '#6B7280';
  }
}

export function NodeDocTooltip({ spec, x, y, visible }: NodeDocTooltipProps) {
  if (!visible || !spec) return null;

  return (
    <div style={{ ...tooltipStyle, left: x, top: y }}>
      {/* Header: label + category badge */}
      <div style={headerStyle}>
        <span style={labelStyle}>{spec.label}</span>
        <span
          style={{
            ...badgeStyle,
            background: categoryColor(spec.category),
          }}
        >
          {spec.category}
        </span>
      </div>

      {/* Type */}
      <div style={typeLineStyle}>
        <span style={{ color: '#666' }}>Type:</span>{' '}
        <code style={codeStyle}>{spec.type}</code>
      </div>

      {/* Description */}
      {spec.description && (
        <p style={descriptionStyle}>{spec.description}</p>
      )}

      {/* Doc text */}
      {spec.doc && (
        <div style={docStyle}>{spec.doc}</div>
      )}

      {/* Inputs table */}
      {spec.inputs.length > 0 && (
        <div style={sectionContainerStyle}>
          <div style={sectionTitleStyle}>Inputs</div>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Name</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Req</th>
                <th style={thStyle}>Default</th>
              </tr>
            </thead>
            <tbody>
              {spec.inputs.map((inp) => (
                <tr key={inp.name}>
                  <td style={tdStyle}>
                    <code style={portNameStyle}>{inp.name}</code>
                  </td>
                  <td style={tdStyle}>
                    <span
                      style={{
                        ...typeBadgeStyle,
                        background: typeColor(inp.type) + '22',
                        color: typeColor(inp.type),
                        borderColor: typeColor(inp.type) + '44',
                      }}
                    >
                      {inp.type}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <span
                      style={{
                        color: inp.required ? '#EF4444' : '#666',
                        fontSize: 10,
                      }}
                    >
                      {inp.required ? 'yes' : 'no'}
                    </span>
                  </td>
                  <td style={tdStyle}>
                    <span style={defaultValStyle}>
                      {inp.default !== undefined && inp.default !== null
                        ? String(inp.default)
                        : '\u2014'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Outputs table */}
      {spec.outputs.length > 0 && (
        <div style={sectionContainerStyle}>
          <div style={sectionTitleStyle}>Outputs</div>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Name</th>
                <th style={thStyle}>Type</th>
              </tr>
            </thead>
            <tbody>
              {spec.outputs.map((out) => (
                <tr key={out.name}>
                  <td style={tdStyle}>
                    <code style={portNameStyle}>{out.name}</code>
                  </td>
                  <td style={tdStyle}>
                    <span
                      style={{
                        ...typeBadgeStyle,
                        background: typeColor(out.type) + '22',
                        color: typeColor(out.type),
                        borderColor: typeColor(out.type) + '44',
                      }}
                    >
                      {out.type}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ---- Styles ---- */

const tooltipStyle: React.CSSProperties = {
  position: 'fixed',
  background: '#2A2A2A',
  border: '1px solid #555',
  borderRadius: 6,
  zIndex: 9999,
  maxWidth: 340,
  maxHeight: 400,
  overflowY: 'auto',
  padding: '10px 12px',
  boxShadow: '0 6px 20px rgba(0,0,0,0.6)',
  fontFamily: "'Segoe UI', system-ui, sans-serif",
  fontSize: 11,
  color: '#ccc',
  pointerEvents: 'none',
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  marginBottom: 6,
};

const labelStyle: React.CSSProperties = {
  color: '#eee',
  fontWeight: 700,
  fontSize: 13,
};

const badgeStyle: React.CSSProperties = {
  color: '#fff',
  fontSize: 9,
  padding: '1px 6px',
  borderRadius: 3,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.5,
};

const typeLineStyle: React.CSSProperties = {
  fontSize: 10,
  color: '#999',
  marginBottom: 6,
};

const codeStyle: React.CSSProperties = {
  fontFamily: "'Consolas', 'Fira Code', monospace",
  color: '#aaa',
  fontSize: 10,
};

const descriptionStyle: React.CSSProperties = {
  color: '#bbb',
  fontSize: 11,
  lineHeight: 1.4,
  margin: '0 0 6px 0',
};

const docStyle: React.CSSProperties = {
  color: '#999',
  fontSize: 10,
  lineHeight: 1.4,
  marginBottom: 8,
  padding: '4px 6px',
  background: '#222',
  borderRadius: 3,
  border: '1px solid #333',
  whiteSpace: 'pre-wrap',
};

const sectionContainerStyle: React.CSSProperties = {
  marginBottom: 6,
};

const sectionTitleStyle: React.CSSProperties = {
  color: '#888',
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  marginBottom: 3,
};

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 10,
};

const thStyle: React.CSSProperties = {
  color: '#666',
  fontSize: 9,
  fontWeight: 600,
  textAlign: 'left',
  padding: '2px 4px',
  borderBottom: '1px solid #333',
  textTransform: 'uppercase',
  letterSpacing: 0.3,
};

const tdStyle: React.CSSProperties = {
  padding: '2px 4px',
  borderBottom: '1px solid #2A2A2A',
  verticalAlign: 'middle',
};

const portNameStyle: React.CSSProperties = {
  fontFamily: "'Consolas', 'Fira Code', monospace",
  color: '#ccc',
  fontSize: 10,
};

const typeBadgeStyle: React.CSSProperties = {
  fontSize: 9,
  padding: '1px 5px',
  borderRadius: 3,
  border: '1px solid',
  fontFamily: "'Consolas', 'Fira Code', monospace",
  fontWeight: 500,
};

const defaultValStyle: React.CSSProperties = {
  color: '#777',
  fontFamily: "'Consolas', 'Fira Code', monospace",
  fontSize: 9,
};
