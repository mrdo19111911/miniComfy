/**
 * HelpPanel - Modal overlay showing keyboard shortcuts and help information.
 * Closes on Escape key or clicking the close button / dark overlay.
 */
import { useEffect } from 'react';

export interface HelpPanelProps {
  visible: boolean;
  onClose: () => void;
  version: string;
}

interface ShortcutEntry {
  keys: string;
  description: string;
}

const SHORTCUTS: ShortcutEntry[] = [
  { keys: 'Ctrl + S', description: 'Save workflow' },
  { keys: 'Ctrl + O', description: 'Open workflow' },
  { keys: 'Ctrl + Z', description: 'Undo' },
  { keys: 'Ctrl + Shift + Z', description: 'Redo' },
  { keys: 'Delete', description: 'Remove selected node' },
  { keys: 'Right-click', description: 'Context menu' },
  { keys: 'Escape', description: 'Close panels' },
];

export function HelpPanel({ visible, onClose, version }: HelpPanelProps) {
  // Close on Escape key
  useEffect(() => {
    if (!visible) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [visible, onClose]);

  if (!visible) return null;

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div
        style={modalStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={headerStyle}>
          <span style={titleStyle}>Help</span>
          <button
            onClick={onClose}
            style={closeBtnStyle}
            title="Close (Escape)"
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = '#555';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
            }}
          >
            ✕
          </button>
        </div>

        {/* Keyboard Shortcuts section */}
        <div style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Keyboard Shortcuts</h3>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Shortcut</th>
                <th style={thStyle}>Action</th>
              </tr>
            </thead>
            <tbody>
              {SHORTCUTS.map((shortcut) => (
                <tr key={shortcut.keys}>
                  <td style={tdStyle}>
                    <kbd style={kbdStyle}>{shortcut.keys}</kbd>
                  </td>
                  <td style={{ ...tdStyle, color: '#ccc' }}>
                    {shortcut.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Divider */}
        <div style={dividerStyle} />

        {/* About section */}
        <div style={sectionStyle}>
          <h3 style={sectionTitleStyle}>About PipeStudio</h3>
          <p style={aboutTextStyle}>
            PipeStudio is a visual workflow builder for constructing and executing
            data processing pipelines. Drag nodes from the palette, connect them
            with edges, configure parameters, and execute workflows against the
            backend engine.
          </p>
          <div style={versionRowStyle}>
            <span style={{ color: '#666' }}>Version</span>
            <span style={{ color: '#aaa', fontFamily: "'Consolas', 'Fira Code', monospace" }}>
              {version}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- Styles ---- */

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0, 0, 0, 0.6)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 10000,
};

const modalStyle: React.CSSProperties = {
  background: '#2A2A2A',
  border: '1px solid #555',
  borderRadius: 8,
  maxWidth: 500,
  width: '90%',
  maxHeight: '80vh',
  overflowY: 'auto',
  boxShadow: '0 8px 32px rgba(0,0,0,0.7)',
  fontFamily: "'Segoe UI', system-ui, sans-serif",
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px 16px',
  borderBottom: '1px solid #444',
};

const titleStyle: React.CSSProperties = {
  color: '#eee',
  fontWeight: 700,
  fontSize: 16,
};

const closeBtnStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#999',
  fontSize: 16,
  cursor: 'pointer',
  padding: '4px 8px',
  borderRadius: 4,
  lineHeight: 1,
};

const sectionStyle: React.CSSProperties = {
  padding: '12px 16px',
};

const sectionTitleStyle: React.CSSProperties = {
  color: '#ddd',
  fontSize: 13,
  fontWeight: 600,
  margin: '0 0 10px 0',
};

const dividerStyle: React.CSSProperties = {
  height: 1,
  background: '#444',
  margin: '0 16px',
};

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 12,
};

const thStyle: React.CSSProperties = {
  color: '#888',
  fontSize: 10,
  fontWeight: 600,
  textAlign: 'left',
  padding: '4px 8px',
  borderBottom: '1px solid #444',
  textTransform: 'uppercase',
  letterSpacing: 0.5,
};

const tdStyle: React.CSSProperties = {
  padding: '6px 8px',
  borderBottom: '1px solid #333',
  verticalAlign: 'middle',
  fontSize: 12,
};

const kbdStyle: React.CSSProperties = {
  display: 'inline-block',
  background: '#333',
  border: '1px solid #555',
  borderRadius: 3,
  padding: '2px 6px',
  fontFamily: "'Consolas', 'Fira Code', monospace",
  fontSize: 11,
  color: '#ddd',
  whiteSpace: 'nowrap',
};

const aboutTextStyle: React.CSSProperties = {
  color: '#aaa',
  fontSize: 12,
  lineHeight: 1.6,
  margin: '0 0 12px 0',
};

const versionRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '6px 8px',
  background: '#222',
  borderRadius: 4,
  fontSize: 11,
};
