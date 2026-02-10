/**
 * ContextMenu - Right-click context menu for nodes, edges, and canvas.
 */
import { useEffect, useRef } from 'react';

export interface ContextMenuAction {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  separator?: boolean;
}

export interface ContextMenuProps {
  x: number;
  y: number;
  actions: ContextMenuAction[];
  onClose: () => void;
}

export function ContextMenu({ x, y, actions, onClose }: ContextMenuProps) {
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

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        left: x,
        top: y,
        background: '#2A2A2A',
        border: '1px solid #555',
        borderRadius: 4,
        minWidth: 160,
        zIndex: 10000,
        boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
        padding: '4px 0',
      }}
    >
      {actions.map((action, i) => {
        if (action.separator) {
          return (
            <div
              key={i}
              style={{ height: 1, background: '#444', margin: '4px 0' }}
            />
          );
        }
        return (
          <button
            key={i}
            onClick={() => {
              action.onClick();
              onClose();
            }}
            disabled={action.disabled}
            style={{
              display: 'block',
              width: '100%',
              background: 'transparent',
              border: 'none',
              color: action.disabled ? '#666' : '#ccc',
              padding: '6px 12px',
              fontSize: 12,
              textAlign: 'left',
              cursor: action.disabled ? 'default' : 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!action.disabled) {
                (e.currentTarget as HTMLButtonElement).style.background = '#444';
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
            }}
          >
            {action.label}
          </button>
        );
      })}
    </div>
  );
}
