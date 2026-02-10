/**
 * Loop Group Node — container that repeats child nodes N times.
 *
 * Redesigned for clarity:
 * - Header with loop icon, label, iteration count, and delete button
 * - Labeled input ports (left) and output ports (right) on a port strip
 * - Large dashed body area for child nodes
 * - Resizable via NodeResizer
 */

import { memo, useCallback } from 'react';
import { Handle, Position, NodeResizer, type NodeProps } from 'reactflow';
import type { PortSpec } from './types';
import { portColor } from './constants';

function LoopGroupNodeInner({ id, data, selected }: NodeProps) {
  const iterations = data.config?.iterations ?? 10;
  const status: string = data.status ?? 'idle';
  const inputs: PortSpec[] = (data.inputs ?? []).filter((p: PortSpec) => p.type !== 'NUMBER');
  const outputs: PortSpec[] = data.outputs ?? [];
  const configPorts: PortSpec[] = (data.inputs ?? []).filter((p: PortSpec) => p.type === 'NUMBER');

  const statusBorder =
    status === 'running'
      ? '#FBBF24'
      : status === 'completed'
        ? '#10B981'
        : status === 'error'
          ? '#EF4444'
          : null;

  const borderColor = statusBorder ?? (selected ? '#fff' : '#0E7490');

  const handleConfigChange = useCallback(
    (val: number) => {
      if (data.onConfigChange) {
        data.onConfigChange(id, 'iterations', val);
      }
    },
    [id, data],
  );

  const handleParamChange = useCallback(
    (name: string, val: number) => {
      if (data.onConfigChange) {
        data.onConfigChange(id, name, val);
      }
    },
    [id, data],
  );

  return (
    <div
      style={{
        background: 'rgba(14, 116, 144, 0.05)',
        border: `2px dashed ${borderColor}`,
        borderRadius: 12,
        width: '100%',
        height: '100%',
        minWidth: 400,
        minHeight: 250,
        position: 'relative',
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
        display: 'flex',
        flexDirection: 'column',
        boxShadow:
          status === 'running'
            ? `0 0 20px ${borderColor}44`
            : selected
              ? '0 0 12px rgba(14,116,144,0.4)'
              : '0 2px 12px rgba(0,0,0,0.3)',
      }}
    >
      <NodeResizer
        color={borderColor}
        isVisible={!!selected}
        minWidth={400}
        minHeight={250}
      />

      {/* Header */}
      <div
        style={{
          background: '#0E7490',
          padding: '6px 14px',
          borderRadius: '10px 10px 0 0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Loop icon */}
          <svg width="16" height="16" viewBox="0 0 16 16" style={{ flexShrink: 0 }}>
            <path
              d="M8 2C5.2 2 3 4.2 3 7H1l3 3.5L7 7H5c0-1.65 1.35-3 3-3s3 1.35 3 3-1.35 3-3 3v2c2.8 0 5-2.2 5-5S10.8 2 8 2z"
              fill="#fff"
            />
          </svg>
          {status === 'running' && (
            <svg
              width="14" height="14" viewBox="0 0 14 14"
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
          <span style={{ fontSize: 13, fontWeight: 600, color: '#fff', letterSpacing: 0.3 }}>
            {data.label ?? 'Loop Group'}
          </span>
        </div>

        {/* Iteration count + delete */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="number"
            value={iterations}
            min={1}
            onChange={(e) => handleConfigChange(parseInt(e.target.value) || 1)}
            className="nodrag"
            style={{
              width: 48,
              background: 'rgba(255,255,255,0.15)',
              border: '1px solid rgba(255,255,255,0.3)',
              borderRadius: 4,
              color: '#fff',
              padding: '2px 4px',
              fontSize: 12,
              textAlign: 'right',
              fontWeight: 600,
            }}
          />
          <span style={{ fontSize: 12, color: '#fff', fontWeight: 600 }}>iters</span>

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
              fontSize: 18,
              lineHeight: 1,
              display: 'flex',
              alignItems: 'center',
              marginLeft: 4,
            }}
            onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#fff'; }}
            onMouseLeave={(e) => { (e.target as HTMLElement).style.color = 'rgba(255,255,255,0.5)'; }}
            title="Delete loop group"
          >
            ×
          </button>
        </div>
      </div>

      {/* Port rows — each slot has input handle (left) and output handle (right) */}
      <div
        style={{
          padding: '6px 0',
          background: 'rgba(14, 116, 144, 0.12)',
          borderBottom: '1px dashed rgba(14, 116, 144, 0.3)',
          flexShrink: 0,
        }}
      >
        {inputs.map((port) => {
          const matchingOutput = outputs.find((o) => o.name === port.name);
          return (
            <div
              key={port.name}
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '2px 20px',
                fontSize: 11,
                color: '#9dd',
              }}
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
              <span style={{ opacity: 0.6, textAlign: 'center', flex: 1 }}>
                {port.name}
              </span>
              {matchingOutput && (
                <Handle
                  type="source"
                  position={Position.Right}
                  id={matchingOutput.name}
                  style={{
                    width: 10, height: 10,
                    background: portColor(matchingOutput.type),
                    border: '2px solid #444',
                    right: -5,
                  }}
                />
              )}
            </div>
          );
        })}
        {/* Config (NUMBER) ports with inline input */}
        {configPorts.map((port) => {
          const matchingOutput = outputs.find((o) => o.name === port.name);
          return (
            <div
              key={`cfg-${port.name}`}
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '2px 20px',
                fontSize: 11,
                color: '#9dd',
              }}
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
              <span style={{ opacity: 0.6 }}>{port.name}</span>
              <input
                type="number"
                value={String(data.config?.[port.name] ?? port.default ?? 0)}
                onChange={(e) => handleParamChange(port.name, parseFloat(e.target.value) || 0)}
                className="nodrag"
                style={{
                  width: 50,
                  background: '#111',
                  border: '1px solid #444',
                  borderRadius: 3,
                  color: '#eee',
                  padding: '1px 3px',
                  fontSize: 10,
                  textAlign: 'right',
                }}
              />
              {matchingOutput && (
                <Handle
                  type="source"
                  position={Position.Right}
                  id={matchingOutput.name}
                  style={{
                    width: 10, height: 10,
                    background: portColor(matchingOutput.type),
                    border: '2px solid #444',
                    right: -5,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Child node drop zone */}
      <div style={{ flex: 1, position: 'relative', minHeight: 120 }}>
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            color: 'rgba(14, 116, 144, 0.2)',
            fontSize: 13,
            fontWeight: 500,
            pointerEvents: 'none',
            textAlign: 'center',
            lineHeight: 1.6,
            whiteSpace: 'nowrap',
          }}
        >
          Drop child nodes here
        </div>
      </div>

      {/* Inline result display */}
      {data.result && typeof data.result === 'object' && (() => {
        const entries = Object.entries(data.result).filter(([, v]) => {
          if (v === null || v === undefined) return false;
          if (typeof v === 'object') return false;
          if (Array.isArray(v)) return false;
          return true;
        });
        if (entries.length === 0) return null;
        return (
          <div style={{
            borderTop: '1px dashed rgba(14, 116, 144, 0.3)',
            padding: '4px 10px',
            fontSize: 10,
            color: '#8f8',
            flexShrink: 0,
          }}>
            {entries.map(([k, v]) => (
              <div key={k}>
                <strong>{k}:</strong>{' '}
                {typeof v === 'number' ? (v as number).toFixed(4) : String(v)}
              </div>
            ))}
          </div>
        );
      })()}
    </div>
  );
}

export const LoopGroupNode = memo(LoopGroupNodeInner);
