/**
 * Standard workflow node component for ReactFlow.
 * Handles all non-loop-group node types.
 */

import { memo, useCallback } from 'react';
import { Handle, Position, NodeResizer, type NodeProps } from 'reactflow';
import DOMPurify from 'dompurify';
import type { PortSpec, NodeVisualState } from './types';
import { portColor, NODE_STATE_STYLES } from './constants';

// ---------------------------------------------------------------------------
// Config widget: inline number input for NUMBER-type ports
// ---------------------------------------------------------------------------

function ConfigWidget({
  portName,
  value,
  defaultValue,
  onChange,
}: {
  portName: string;
  value: unknown;
  defaultValue: unknown;
  onChange: (name: string, val: number) => void;
}) {
  const current = value ?? defaultValue ?? 0;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '4px 10px',
        fontSize: 11,
        color: '#bbb',
        borderBottom: '1px solid #333',
      }}
    >
      <span>{portName}</span>
      <input
        type="number"
        value={String(current)}
        onChange={(e) => onChange(portName, parseFloat(e.target.value) || 0)}
        className="nodrag"
        style={{
          width: 60,
          background: '#111',
          border: '1px solid #444',
          borderRadius: 3,
          color: '#eee',
          padding: '2px 4px',
          fontSize: 11,
          textAlign: 'right',
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main node component
// ---------------------------------------------------------------------------

function WorkflowNodeInner({ id, data, selected }: NodeProps) {
  const color: string = data.color ?? '#6B7280';
  const inputs: PortSpec[] = data.inputs ?? [];
  const outputs: PortSpec[] = data.outputs ?? [];
  const status: string = data.status ?? 'idle';
  const muted: boolean = !!data.muted;
  const visualState: NodeVisualState = data.visualState ?? (muted ? 'muted' : 'normal');

  // Plugin lifecycle state styles
  const stateStyle = (visualState === 'disabled' || visualState === 'broken')
    ? NODE_STATE_STYLES[visualState]
    : null;

  // Separate config (NUMBER) ports from data (ARRAY) ports
  const configPorts = inputs.filter((p) => p.type === 'NUMBER');
  const dataPorts = inputs.filter((p) => p.type !== 'NUMBER');

  // Check if result contains visual content (SVG or multiline text) → enable resize
  const hasVisualResult = data.result && typeof data.result === 'object' &&
    Object.values(data.result).some((v) => {
      if (typeof v === 'string') {
        return v.trimStart().startsWith('<svg') || v.includes('\n');
      }
      return false;
    });

  const hasBreakpoint: boolean = status === 'breakpoint';

  const statusBorder =
    status === 'running'
      ? '#FBBF24'
      : status === 'completed'
        ? '#10B981'
        : status === 'error'
          ? '#EF4444'
          : status === 'breakpoint'
            ? '#EF4444'
            : status === 'blocked'
              ? '#F59E0B'
              : null;

  const borderColor = stateStyle
    ? stateStyle.borderColor
    : muted ? '#666' : (statusBorder ?? (selected ? '#fff' : color));

  const handleConfigChange = useCallback(
    (name: string, val: number) => {
      if (data.onConfigChange) {
        data.onConfigChange(id, name, val);
      }
    },
    [id, data.onConfigChange],
  );

  return (
    <div
      style={{
        background: '#2A2A2A',
        border: `2px ${stateStyle?.borderStyle ?? 'solid'} ${borderColor}`,
        borderRadius: 8,
        minWidth: configPorts.length > 0 ? 200 : 160,
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
        opacity: stateStyle?.opacity ?? (muted ? 0.5 : 1),
        position: 'relative',
        ...(hasVisualResult ? { width: '100%', height: '100%', display: 'flex', flexDirection: 'column' as const } : {}),
        boxShadow:
          status === 'running'
            ? `0 0 16px ${borderColor}88`
            : status === 'breakpoint'
              ? `0 0 16px #EF444488`
              : status === 'blocked'
                ? `0 0 12px #F59E0B66`
                : selected
                  ? `0 0 12px ${color}88`
                  : '0 2px 8px rgba(0,0,0,0.4)',
      }}
      title={
        visualState === 'disabled'
          ? `Plugin inactive. Activate to use this node.`
          : visualState === 'broken'
            ? `Plugin not installed. Install to use this node.`
            : undefined
      }
    >
      {/* Resize handle — only for nodes with visual results (SVG, multiline text) */}
      {hasVisualResult && (
        <NodeResizer
          color={borderColor}
          isVisible={!!selected}
          minWidth={200}
          minHeight={150}
        />
      )}
      {/* Breakpoint badge - red circle in top-right corner */}
      {hasBreakpoint && (
        <div
          style={{
            position: 'absolute',
            top: -5,
            right: -5,
            width: 12,
            height: 12,
            borderRadius: '50%',
            background: '#EF4444',
            border: '2px solid #1A1A1A',
            zIndex: 10,
          }}
          title="Breakpoint set"
        />
      )}
      {/* Header */}
      <div
        style={{
          background: stateStyle?.headerColor ?? (muted ? '#555' : color),
          padding: '6px 12px',
          borderRadius: '6px 6px 0 0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {status === 'running' && (
            <svg
              width="14"
              height="14"
              viewBox="0 0 14 14"
              style={{ animation: 'spin 0.8s linear infinite', flexShrink: 0 }}
            >
              <circle
                cx="7" cy="7" r="5"
                stroke="#FBBF24" strokeWidth="2"
                fill="none" strokeDasharray="20" strokeDashoffset="10"
                strokeLinecap="round"
              />
            </svg>
          )}
          {status === 'completed' && (
            <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
              <circle cx="7" cy="7" r="6" fill="#10B981" />
              <polyline
                points="4,7.5 6,9.5 10,4.5"
                stroke="#fff" strokeWidth="1.5" fill="none"
                strokeLinecap="round" strokeLinejoin="round"
              />
            </svg>
          )}
          {status === 'error' && (
            <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
              <circle cx="7" cy="7" r="6" fill="#EF4444" />
              <line x1="4.5" y1="4.5" x2="9.5" y2="9.5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="9.5" y1="4.5" x2="4.5" y2="9.5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          )}
          {status === 'breakpoint' && (
            <span style={{ fontSize: 12, flexShrink: 0, color: '#EF4444', lineHeight: 1 }} title="Breakpoint">
              {'\u23F9'}
            </span>
          )}
          {status === 'blocked' && (
            <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
              <circle cx="7" cy="7" r="6" fill="#F59E0B" />
              <rect x="4" y="5.5" width="6" height="3" rx="0.5" fill="#fff" />
            </svg>
          )}
          {visualState === 'broken' && status === 'idle' && (
            <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
              <polygon points="7,1 13,12 1,12" fill="#EF4444" stroke="#7F1D1D" strokeWidth="0.5" />
              <text x="7" y="10.5" textAnchor="middle" fill="#fff" fontSize="8" fontWeight="bold">!</text>
            </svg>
          )}
          {visualState === 'disabled' && status === 'idle' && (
            <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
              <circle cx="7" cy="7" r="6" fill="none" stroke="#888" strokeWidth="1.5" />
              <line x1="3" y1="7" x2="11" y2="7" stroke="#888" strokeWidth="1.5" />
            </svg>
          )}
          <span style={{ fontSize: 13, fontWeight: 600, color: '#fff', letterSpacing: 0.3 }}>
            {data.label}
          </span>
          {muted && !stateStyle && (
            <span style={{
              fontSize: 9,
              background: 'rgba(0,0,0,0.4)',
              color: '#fbbf24',
              padding: '1px 4px',
              borderRadius: 3,
              fontWeight: 700,
            }}>
              MUTED
            </span>
          )}
          {stateStyle && (
            <span style={{
              fontSize: 9,
              background: stateStyle.badgeBg,
              color: stateStyle.badgeColor,
              padding: '1px 4px',
              borderRadius: 3,
              fontWeight: 700,
            }}>
              {stateStyle.badgeText}
            </span>
          )}
        </div>

        {/* Delete button */}
        <button
          className="nodrag"
          onClick={(e) => {
            e.stopPropagation();
            if (data.onDelete) data.onDelete(id);
          }}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'rgba(255,255,255,0.5)',
            cursor: 'pointer',
            padding: '0 2px',
            fontSize: 16,
            lineHeight: 1,
            display: 'flex',
            alignItems: 'center',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#fff'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.5)'; }}
          title="Delete node"
        >
          ×
        </button>
      </div>

      {/* Config widgets */}
      {configPorts.map((port) => (
        <ConfigWidget
          key={port.name}
          portName={port.name}
          value={data.config?.[port.name]}
          defaultValue={port.default}
          onChange={handleConfigChange}
        />
      ))}

      {/* Body with data port handles */}
      <div style={{ padding: '8px 0' }}>
        {dataPorts.map((port) => (
          <div
            key={`in-${port.name}`}
            style={{ position: 'relative', padding: '3px 12px 3px 20px', fontSize: 11, color: '#bbb' }}
          >
            <Handle
              type="target"
              position={Position.Left}
              id={port.name}
              style={{
                width: 10, height: 10,
                background: portColor(port.type),
                border: '2px solid #444',
                left: -5,
              }}
            />
            <span style={{ opacity: port.required ? 1 : 0.6 }}>
              {port.name}{!port.required && ' (opt)'}
            </span>
          </div>
        ))}
        {outputs.map((port) => (
          <div
            key={`out-${port.name}`}
            style={{ position: 'relative', padding: '3px 20px 3px 12px', fontSize: 11, color: '#bbb', textAlign: 'right' }}
          >
            <Handle
              type="source"
              position={Position.Right}
              id={port.name}
              style={{
                width: 10, height: 10,
                background: portColor(port.type),
                border: '2px solid #444',
                right: -5,
              }}
            />
            <span>{port.name}</span>
          </div>
        ))}
      </div>

      {/* Inline result display — only show scalars and SVG, hide arrays/objects */}
      {data.result && typeof data.result === 'object' && (() => {
        const entries = Object.entries(data.result).filter(([, v]) => {
          if (v === null || v === undefined) return false;
          if (typeof v === 'object' && !Array.isArray(v)) return false;
          if (Array.isArray(v)) return false;
          return true;
        });
        if (entries.length === 0) return null;
        return (
          <div style={{ borderTop: '1px solid #3a3a3a', padding: '6px 10px', fontSize: 10, color: '#8f8', flex: hasVisualResult ? 1 : undefined, overflow: 'hidden' }}>
            {entries.map(([k, v]) => {
              const s = typeof v === 'string' ? v : '';
              if (s.trimStart().startsWith('<svg')) {
                return (
                  <div key={k} style={{ marginTop: 4, width: '100%' }}
                    dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(s, { USE_PROFILES: { svg: true } }) }} />
                );
              }
              if (typeof v === 'string' && v.includes('\n')) {
                return (
                  <pre key={k} style={{ margin: '4px 0', whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontFamily: 'monospace', fontSize: 10, color: '#8f8', maxHeight: hasVisualResult ? 'none' : 200, overflow: 'auto' }}>
                    {v}
                  </pre>
                );
              }
              return (
                <div key={k}>
                  <strong>{k}:</strong>{' '}
                  {typeof v === 'number' ? v.toFixed(4) : String(v)}
                </div>
              );
            })}
          </div>
        );
      })()}
    </div>
  );
}

export const WorkflowNode = memo(WorkflowNodeInner);
