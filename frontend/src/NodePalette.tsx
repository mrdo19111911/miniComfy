/**
 * Sidebar palette with draggable node items grouped by category.
 * Accepts dynamic node list from API or falls back to static.
 */

import { useState, useMemo } from 'react';
import { categoryColor, groupByCategory, groupedPalette } from './constants';
import type { PaletteNode } from './types';

export function NodePalette({
  collapsed,
  onToggle,
  nodeList,
}: {
  collapsed: boolean;
  onToggle: () => void;
  nodeList?: PaletteNode[];
}) {
  const [search, setSearch] = useState('');

  const grouped = useMemo(
    () => (nodeList ? groupByCategory(nodeList) : groupedPalette),
    [nodeList],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return grouped;
    const result: Record<string, PaletteNode[]> = {};
    for (const [cat, nodes] of Object.entries(grouped)) {
      const matched = nodes.filter(
        (n) =>
          n.label.toLowerCase().includes(q) ||
          n.description.toLowerCase().includes(q),
      );
      if (matched.length > 0) result[cat] = matched;
    }
    return result;
  }, [search, grouped]);

  const onDragStart = (e: React.DragEvent, node: PaletteNode) => {
    e.dataTransfer.setData(
      'application/reactflow',
      JSON.stringify({
        type: node.type,
        label: node.label,
        color: categoryColor(node.category),
        category: node.category,
        inputs: node.inputs,
        outputs: node.outputs,
        doc: node.doc,
      }),
    );
    e.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      style={{
        width: collapsed ? 40 : 240,
        height: '100%',
        background: '#1E1E1E',
        borderRight: '1px solid #333',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: 'width 0.2s ease',
        flexShrink: 0,
      }}
    >
      <button
        onClick={onToggle}
        style={{
          background: '#2A2A2A',
          border: 'none',
          borderBottom: '1px solid #333',
          color: '#ccc',
          padding: 10,
          cursor: 'pointer',
          fontSize: 14,
          textAlign: 'center',
        }}
      >
        {collapsed ? '\u25B6' : '\u25C0 Node Palette'}
      </button>

      {!collapsed && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes..."
            style={{
              width: '100%',
              background: '#111',
              border: '1px solid #444',
              borderRadius: 4,
              color: '#ccc',
              padding: '6px 8px',
              fontSize: 11,
              outline: 'none',
              boxSizing: 'border-box',
              marginBottom: 8,
            }}
          />

          {Object.entries(filtered).map(([cat, nodes]) => (
            <div key={cat} style={{ marginBottom: 16 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  marginBottom: 6,
                  padding: '0 4px',
                }}
              >
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: categoryColor(cat),
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: '#888',
                    textTransform: 'uppercase',
                    letterSpacing: 0.8,
                  }}
                >
                  {cat}
                </span>
              </div>

              {nodes.map((node) => (
                <div
                  key={node.type}
                  draggable
                  onDragStart={(e) => onDragStart(e, node)}
                  title={node.doc || node.description}
                  style={{
                    background: '#2A2A2A',
                    border: `1px solid ${categoryColor(node.category)}44`,
                    borderLeft: `3px solid ${categoryColor(node.category)}`,
                    borderRadius: 4,
                    padding: '8px 10px',
                    marginBottom: 4,
                    cursor: 'grab',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLDivElement).style.background = '#333';
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLDivElement).style.background = '#2A2A2A';
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#ddd', marginBottom: 2 }}>
                    {node.label}
                  </div>
                  <div style={{ fontSize: 10, color: '#777', lineHeight: 1.3 }}>
                    {node.description}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
