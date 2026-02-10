/**
 * Loop End Node (ComfyUI style) — marks end of a loop pair.
 * Must set pair_id to match the corresponding LoopStartNode.
 */

import { memo, useCallback } from 'react';
import { Handle, Position, useNodes, type NodeProps } from 'reactflow';
import type { PortSpec } from './types';
import { portColor } from './constants';

function LoopEndNodeInner({ id, data, selected }: NodeProps) {
  const status: string = data.status ?? 'idle';
  const inputs: PortSpec[] = data.inputs ?? [];
  const outputs: PortSpec[] = data.outputs ?? [];
  const pairId: string = data.config?.pair_id ?? '';

  // Get all loop_start nodes on canvas for the dropdown
  const allNodes = useNodes();
  const loopStarts = allNodes.filter((n) => (n.data as any)?.nodeType === 'loop_start');

  const statusBorder =
    status === 'running' ? '#FBBF24'
      : status === 'completed' ? '#10B981'
        : status === 'error' ? '#EF4444' : null;

  const borderColor = statusBorder ?? (selected ? '#fff' : '#0E7490');

  const handlePairChange = useCallback(
    (val: string) => {
      if (data.onConfigChange) data.onConfigChange(id, 'pair_id', val);
    },
    [id, data],
  );

  return (
    <div
      style={{
        background: '#2A2A2A',
        border: `2px solid ${borderColor}`,
        borderRadius: 8,
        minWidth: 170,
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
        boxShadow: status === 'running' ? `0 0 16px ${borderColor}88`
          : selected ? '0 0 12px rgba(14,116,144,0.6)' : '0 2px 8px rgba(0,0,0,0.4)',
      }}
    >
      {/* Header */}
      <div
        style={{
          background: '#0E7490',
          padding: '6px 12px',
          borderRadius: '6px 6px 0 0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* Loop end icon */}
          <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
            <path d="M7 13C10 13 12 10.5 12 8H13.5l-2.5-3L8.5 8H10c0 1.65-1.35 3-3 3s-3-1.35-3-3" stroke="#fff" strokeWidth="1.5" fill="none" strokeLinecap="round" />
            <circle cx="4" cy="8" r="1.5" fill="#fff" />
          </svg>
          {status === 'running' && (
            <svg width="12" height="12" viewBox="0 0 14 14" style={{ animation: 'spin 0.8s linear infinite', flexShrink: 0 }}>
              <circle cx="7" cy="7" r="5" stroke="#FBBF24" strokeWidth="2" fill="none" strokeDasharray="20" strokeDashoffset="10" strokeLinecap="round" />
            </svg>
          )}
          {status === 'completed' && (
            <svg width="12" height="12" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
              <circle cx="7" cy="7" r="6" fill="#10B981" />
              <polyline points="4,7.5 6,9.5 10,4.5" stroke="#fff" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
          <span style={{ fontSize: 13, fontWeight: 600, color: '#fff', letterSpacing: 0.3 }}>
            {data.label ?? 'Loop End'}
          </span>
        </div>

        <button
          className="nodrag"
          onClick={(e) => { e.stopPropagation(); if (data.onDelete) data.onDelete(id); }}
          style={{
            background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.5)',
            cursor: 'pointer', padding: '0 2px', fontSize: 16, lineHeight: 1,
            display: 'flex', alignItems: 'center',
          }}
          onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#fff'; }}
          onMouseLeave={(e) => { (e.target as HTMLElement).style.color = 'rgba(255,255,255,0.5)'; }}
          title="Delete node"
        >×</button>
      </div>

      {/* Pair selector */}
      <div style={{
        padding: '4px 10px', fontSize: 11, color: '#bbb', borderBottom: '1px solid #333',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6,
      }}>
        <span>pair</span>
        <select
          className="nodrag"
          value={pairId}
          onChange={(e) => handlePairChange(e.target.value)}
          style={{
            background: '#111', border: '1px solid #444', borderRadius: 3,
            color: '#eee', padding: '2px 4px', fontSize: 10, flex: 1, maxWidth: 120,
          }}
        >
          <option value="">-- select --</option>
          {loopStarts.map((n) => (
            <option key={n.id} value={n.id}>{(n.data as any)?.label ?? n.id}</option>
          ))}
        </select>
      </div>

      {/* Data ports */}
      <div style={{ padding: '6px 0' }}>
        {inputs.map((port) => (
          <div key={`in-${port.name}`} style={{ position: 'relative', padding: '3px 12px 3px 20px', fontSize: 11, color: '#9dd' }}>
            <Handle type="target" position={Position.Left} id={port.name}
              style={{ width: 10, height: 10, background: portColor(port.type), border: '2px solid #444', left: -5 }} />
            <span style={{ opacity: 0.6 }}>{port.name}</span>
          </div>
        ))}
        {outputs.map((port) => (
          <div key={`out-${port.name}`} style={{ position: 'relative', padding: '3px 20px 3px 12px', fontSize: 11, color: '#9dd', textAlign: 'right' }}>
            <Handle type="source" position={Position.Right} id={port.name}
              style={{ width: 10, height: 10, background: portColor(port.type), border: '2px solid #444', right: -5 }} />
            <span>{port.name}</span>
          </div>
        ))}
      </div>

      {/* Inline result */}
      {data.result && typeof data.result === 'object' && (() => {
        const entries = Object.entries(data.result).filter(([, v]) =>
          v !== null && v !== undefined && typeof v !== 'object' && !Array.isArray(v));
        if (entries.length === 0) return null;
        return (
          <div style={{ borderTop: '1px solid #3a3a3a', padding: '4px 10px', fontSize: 10, color: '#8f8' }}>
            {entries.map(([k, v]) => (
              <div key={k}><strong>{k}:</strong> {typeof v === 'number' ? (v as number).toFixed(4) : String(v)}</div>
            ))}
          </div>
        );
      })()}
    </div>
  );
}

export const LoopEndNode = memo(LoopEndNodeInner);
