/**
 * Loop Node (n8n style) — single node with back-edge feedback.
 *
 * Ports layout:
 *   Left side (inputs):     init_1, init_2, init_3, iterations  |  feedback_1, feedback_2, feedback_3
 *   Right side (outputs):   loop_1, loop_2, loop_3              |  done_1, done_2, done_3
 *
 * Feedback ports (orange) receive back-edges from the processing chain.
 * Done ports emit final values after all iterations.
 */

import { memo, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import type { PortSpec } from './types';
import { portColor } from './constants';

const FEEDBACK_COLOR = '#F59E0B'; // Orange for feedback ports

function LoopN8nNodeInner({ id, data, selected }: NodeProps) {
  const iterations = data.config?.iterations ?? 10;
  const status: string = data.status ?? 'idle';
  const allInputs: PortSpec[] = data.inputs ?? [];
  const allOutputs: PortSpec[] = data.outputs ?? [];

  // Split ports into groups
  const initPorts = allInputs.filter((p: PortSpec) => p.name.startsWith('init_'));
  const feedbackPorts = allInputs.filter((p: PortSpec) => p.name.startsWith('feedback_'));
  const configPorts = allInputs.filter((p: PortSpec) => p.type === 'NUMBER');
  const loopPorts = allOutputs.filter((p: PortSpec) => p.name.startsWith('loop_'));
  const donePorts = allOutputs.filter((p: PortSpec) => p.name.startsWith('done_'));

  const statusBorder =
    status === 'running' ? '#FBBF24'
      : status === 'completed' ? '#10B981'
        : status === 'error' ? '#EF4444' : null;

  const borderColor = statusBorder ?? (selected ? '#fff' : '#0E7490');

  const handleConfigChange = useCallback(
    (name: string, val: number) => {
      if (data.onConfigChange) data.onConfigChange(id, name, val);
    },
    [id, data],
  );

  return (
    <div
      style={{
        background: '#2A2A2A',
        border: `2px solid ${borderColor}`,
        borderRadius: 8,
        minWidth: 200,
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
          {/* Loop icon */}
          <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
            <path
              d="M7 2C4.5 2 2.5 4 2.5 6.5H1l2.5 3L6 6.5H4c0-1.65 1.35-3 3-3s3 1.35 3 3-1.35 3-3 3v1.5c2.5 0 4.5-2 4.5-4.5S9.5 2 7 2z"
              fill="#fff"
            />
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
            {data.label ?? 'Loop'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <input
            type="number" value={iterations} min={1}
            onChange={(e) => handleConfigChange('iterations', parseInt(e.target.value) || 1)}
            className="nodrag"
            style={{
              width: 44, background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.3)',
              borderRadius: 4, color: '#fff', padding: '2px 4px', fontSize: 11, textAlign: 'right', fontWeight: 600,
            }}
          />
          <span style={{ fontSize: 11, color: '#fff', fontWeight: 600 }}>iters</span>

          <button
            className="nodrag"
            onClick={(e) => { e.stopPropagation(); if (data.onDelete) data.onDelete(id); }}
            style={{
              background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.5)',
              cursor: 'pointer', padding: '0 2px', fontSize: 16, lineHeight: 1,
              display: 'flex', alignItems: 'center', marginLeft: 2,
            }}
            onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#fff'; }}
            onMouseLeave={(e) => { (e.target as HTMLElement).style.color = 'rgba(255,255,255,0.5)'; }}
            title="Delete node"
          >×</button>
        </div>
      </div>

      {/* Init inputs + Loop outputs */}
      <div style={{ padding: '4px 0', borderBottom: '1px dashed #444' }}>
        <div style={{ padding: '0 10px 2px', fontSize: 9, color: '#888', fontWeight: 600, letterSpacing: 0.5 }}>
          INITIAL / LOOP BODY
        </div>
        {initPorts.map((port, i) => {
          const loopOut = loopPorts[i];
          return (
            <div key={port.name} style={{
              position: 'relative', display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', padding: '2px 20px', fontSize: 11,
            }}>
              <Handle type="target" position={Position.Left} id={port.name}
                style={{ width: 10, height: 10, background: portColor(port.type), border: '2px solid #444', left: -5 }} />
              <span style={{ color: '#9dd', opacity: port.required ? 1 : 0.6 }}>
                {port.name}{!port.required && ' (opt)'}
              </span>
              <span style={{ color: '#9dd', fontSize: 10, opacity: 0.8 }}>
                {loopOut?.name ?? ''}
              </span>
              {loopOut && (
                <Handle type="source" position={Position.Right} id={loopOut.name}
                  style={{ width: 10, height: 10, background: portColor(loopOut.type), border: '2px solid #444', right: -5 }} />
              )}
            </div>
          );
        })}
      </div>

      {/* Feedback inputs + Done outputs */}
      <div style={{ padding: '4px 0' }}>
        <div style={{ padding: '0 10px 2px', fontSize: 9, color: FEEDBACK_COLOR, fontWeight: 600, letterSpacing: 0.5 }}>
          FEEDBACK / DONE
        </div>
        {feedbackPorts.map((port, i) => {
          const doneOut = donePorts[i];
          return (
            <div key={port.name} style={{
              position: 'relative', display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', padding: '2px 20px', fontSize: 11,
            }}>
              <Handle type="target" position={Position.Left} id={port.name}
                style={{
                  width: 10, height: 10, background: FEEDBACK_COLOR,
                  border: `2px dashed #444`, left: -5,
                }} />
              <span style={{ color: FEEDBACK_COLOR, opacity: 0.8 }}>{port.name}</span>
              <span style={{ color: '#9dd', fontSize: 10, opacity: 0.8 }}>
                {doneOut?.name ?? ''}
              </span>
              {doneOut && (
                <Handle type="source" position={Position.Right} id={doneOut.name}
                  style={{ width: 10, height: 10, background: portColor(doneOut.type), border: '2px solid #444', right: -5 }} />
              )}
            </div>
          );
        })}
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

export const LoopN8nNode = memo(LoopN8nNodeInner);
