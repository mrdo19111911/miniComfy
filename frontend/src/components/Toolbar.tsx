/**
 * Toolbar - Top bar with workflow actions, save/load, examples dropdown.
 */
import { useState, useEffect, useRef } from 'react';
import { API_BASE } from '../constants';

interface ExampleEntry {
  filename: string;
  name: string;
}

export interface ToolbarProps {
  onExecute: () => void;
  onClear: () => void;
  onSave: () => void;
  onLoad: () => void;
  onLoadExample: (filename: string) => void;
  onToggleLog: () => void;
  onToggleValidation: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onOpenPlugins: () => void;
  onOpenHelp: () => void;
  canUndo: boolean;
  canRedo: boolean;
  executing: boolean;
  logPanelVisible: boolean;
  validationVisible: boolean;
  validationErrors: number;
  logCount: number;
  executionResult: string | null;
}

export function Toolbar({
  onExecute,
  onClear,
  onSave,
  onLoad,
  onLoadExample,
  onToggleLog,
  onToggleValidation,
  onUndo,
  onRedo,
  onOpenPlugins,
  onOpenHelp,
  canUndo,
  canRedo,
  executing,
  logPanelVisible,
  validationVisible,
  validationErrors,
  logCount,
  executionResult,
}: ToolbarProps) {
  const [examples, setExamples] = useState<ExampleEntry[]>([]);
  const [showExamples, setShowExamples] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch examples list on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/workflow/examples`)
      .then((r) => r.json())
      .then(setExamples)
      .catch(() => {});
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    if (!showExamples) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as HTMLElement)) {
        setShowExamples(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showExamples]);

  return (
    <div
      style={{
        background: '#1E1E1E',
        borderBottom: '1px solid #333',
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        flexShrink: 0,
      }}
    >
      <span style={{ color: '#eee', fontWeight: 700, fontSize: 15, marginRight: 16 }}>
        PipeStudio
      </span>

      {/* File operations */}
      <button onClick={onSave} title="Save workflow (Ctrl+S)" style={btnStyle}>
        Save
      </button>
      <button onClick={onLoad} title="Open workflow (Ctrl+O)" style={btnStyle}>
        Open
      </button>

      {/* Examples dropdown */}
      <div ref={dropdownRef} style={{ position: 'relative' }}>
        <button
          onClick={() => setShowExamples((v) => !v)}
          style={{
            ...btnStyle,
            background: showExamples ? '#444' : '#333',
          }}
          title="Load an example workflow"
        >
          Examples {showExamples ? '▴' : '▾'}
        </button>
        {showExamples && examples.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              marginTop: 4,
              background: '#2A2A2A',
              border: '1px solid #555',
              borderRadius: 4,
              minWidth: 200,
              zIndex: 1000,
              boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
            }}
          >
            {examples.map((ex) => (
              <button
                key={ex.filename}
                onClick={() => {
                  onLoadExample(ex.filename);
                  setShowExamples(false);
                }}
                style={{
                  display: 'block',
                  width: '100%',
                  background: 'transparent',
                  border: 'none',
                  color: '#ccc',
                  padding: '8px 12px',
                  fontSize: 12,
                  textAlign: 'left',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = '#444';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                }}
              >
                {ex.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <span style={{ color: '#444', fontSize: 14 }}>|</span>

      {/* Undo/Redo */}
      <button
        onClick={onUndo}
        disabled={!canUndo}
        title="Undo (Ctrl+Z)"
        style={{ ...btnStyle, opacity: canUndo ? 1 : 0.4 }}
      >
        Undo
      </button>
      <button
        onClick={onRedo}
        disabled={!canRedo}
        title="Redo (Ctrl+Shift+Z)"
        style={{ ...btnStyle, opacity: canRedo ? 1 : 0.4 }}
      >
        Redo
      </button>

      <span style={{ color: '#444', fontSize: 14 }}>|</span>

      {/* Execution */}
      <button onClick={onExecute} disabled={executing} style={btnStyle}>
        {executing ? 'Running...' : 'Execute'}
      </button>
      <button onClick={onClear} title="Clear canvas" style={btnStyle}>
        Clear
      </button>

      {/* Log toggle */}
      <button
        onClick={onToggleLog}
        style={{
          ...btnStyle,
          background: logPanelVisible ? '#444' : '#333',
          color: logPanelVisible ? '#eee' : '#ccc',
        }}
      >
        Log {logCount > 0 ? `(${logCount})` : ''}
      </button>

      {/* Validation toggle */}
      <button
        onClick={onToggleValidation}
        style={{
          ...btnStyle,
          background: validationVisible ? '#444' : '#333',
          color: validationErrors > 0 ? '#EF4444' : validationVisible ? '#eee' : '#ccc',
        }}
        title="Toggle validation panel"
      >
        Validate {validationErrors > 0 ? `(${validationErrors})` : ''}
      </button>

      <span style={{ color: '#444', fontSize: 14 }}>|</span>

      {/* Plugins */}
      <button onClick={onOpenPlugins} style={btnStyle} title="Plugin Manager">
        Plugins
      </button>

      {/* Help */}
      <button onClick={onOpenHelp} style={btnStyle} title="Help (F1)">
        Help
      </button>

      {/* Execution result */}
      {executionResult && (
        <span
          style={{
            fontSize: 12,
            color: executionResult.startsWith('Error') ? '#EF4444' : '#10B981',
            marginLeft: 4,
          }}
        >
          {executionResult}
        </span>
      )}

      <span style={{ flex: 1 }} />

      <span style={{ fontSize: 10, color: '#666' }}>
        F1 Help · Ctrl+S Save · Right-click Menu
      </span>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  background: '#333',
  border: '1px solid #555',
  borderRadius: 4,
  color: '#ccc',
  padding: '6px 14px',
  fontSize: 12,
  cursor: 'pointer',
};
