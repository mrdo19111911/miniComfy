/**
 * Node catalog, category colors, and helper functions.
 * Supports dynamic loading from API with static fallback.
 */

import type { PaletteNode } from './types';

export const API_BASE = 'http://localhost:8500';

// ---------------------------------------------------------------------------
// Category colors (defaults, can be overridden by plugin manifest)
// ---------------------------------------------------------------------------

export const CATEGORY_COLORS: Record<string, string> = {
  INPUT: '#2563EB',
  DESTROY: '#DC2626',
  REPAIR: '#D97706',
  EVALUATION: '#0891B2',
  CONTROL: '#0E7490',
  COMPUTE: '#7C3AED',
  SOLVER: '#D97706',
  UTILITY: '#6B7280',
};

export const categoryColor = (cat: string): string =>
  CATEGORY_COLORS[cat] ?? '#6B7280';

// ---------------------------------------------------------------------------
// Port handle colors
// ---------------------------------------------------------------------------

export function portColor(type: string): string {
  switch (type) {
    case 'ARRAY':
      return '#34D399';
    case 'NUMBER':
      return '#FBBF24';
    case 'STRING':
      return '#A78BFA';
    default:
      return '#9CA3AF';
  }
}

// ---------------------------------------------------------------------------
// Static node palette (fallback if API unreachable)
// ---------------------------------------------------------------------------

export const PALETTE_NODES: PaletteNode[] = [
  {
    type: 'generate_array',
    label: 'Generate Array',
    category: 'INPUT',
    description: 'Create a random integer array',
    inputs: [{ name: 'size', type: 'NUMBER', required: false, default: 1000 }],
    outputs: [{ name: 'array', type: 'ARRAY', required: true }],
  },
  {
    type: 'shuffle_segment',
    label: 'Shuffle Segment',
    category: 'DESTROY',
    description: 'Randomly shuffle a segment of the array',
    inputs: [{ name: 'array', type: 'ARRAY', required: true }],
    outputs: [{ name: 'array', type: 'ARRAY', required: true }],
  },
  {
    type: 'reverse_segment',
    label: 'Reverse Segment',
    category: 'DESTROY',
    description: 'Reverse a random segment of the array',
    inputs: [{ name: 'array', type: 'ARRAY', required: true }],
    outputs: [{ name: 'array', type: 'ARRAY', required: true }],
  },
  {
    type: 'partial_sort',
    label: 'Partial Sort',
    category: 'REPAIR',
    description: 'Sort within a sliding window',
    inputs: [
      { name: 'array', type: 'ARRAY', required: true },
      { name: 'window', type: 'NUMBER', required: false, default: 50 },
    ],
    outputs: [{ name: 'array', type: 'ARRAY', required: true }],
  },
  {
    type: 'bubble_pass',
    label: 'Bubble Pass',
    category: 'REPAIR',
    description: 'One pass of bubble sort (adjacent swaps)',
    inputs: [{ name: 'array', type: 'ARRAY', required: true }],
    outputs: [{ name: 'array', type: 'ARRAY', required: true }],
  },
  {
    type: 'measure_disorder',
    label: 'Measure Disorder',
    category: 'EVALUATION',
    description: 'Count how disordered the array is',
    inputs: [{ name: 'array', type: 'ARRAY', required: true }],
    outputs: [
      { name: 'array', type: 'ARRAY', required: true },
      { name: 'score', type: 'NUMBER', required: true },
    ],
  },
  {
    type: 'loop_group',
    label: 'Loop Group (Legacy)',
    category: 'CONTROL',
    description: 'Loop child nodes N times. Drag nodes inside.',
    inputs: [
      { name: 'array', type: 'ARRAY', required: true },
      { name: 'iterations', type: 'NUMBER', required: false, default: 10 },
    ],
    outputs: [{ name: 'array', type: 'ARRAY', required: true }],
  },
  {
    type: 'loop_start',
    label: 'Loop Start',
    category: 'CONTROL',
    description: 'Start of a loop. Pair with Loop End.',
    inputs: [
      { name: 'in_1', type: 'ARRAY', required: true },
      { name: 'in_2', type: 'ARRAY', required: false },
      { name: 'in_3', type: 'ARRAY', required: false },
      { name: 'iterations', type: 'NUMBER', required: false, default: 10 },
    ],
    outputs: [
      { name: 'out_1', type: 'ARRAY', required: true },
      { name: 'out_2', type: 'ARRAY', required: true },
      { name: 'out_3', type: 'ARRAY', required: true },
    ],
  },
  {
    type: 'loop_end',
    label: 'Loop End',
    category: 'CONTROL',
    description: 'End of a loop. Pair with Loop Start.',
    inputs: [
      { name: 'in_1', type: 'ARRAY', required: false },
      { name: 'in_2', type: 'ARRAY', required: false },
      { name: 'in_3', type: 'ARRAY', required: false },
    ],
    outputs: [
      { name: 'out_1', type: 'ARRAY', required: true },
      { name: 'out_2', type: 'ARRAY', required: true },
      { name: 'out_3', type: 'ARRAY', required: true },
    ],
  },
  {
    type: 'loop_node',
    label: 'Loop',
    category: 'CONTROL',
    description: 'Loop with back-edge feedback (n8n style).',
    inputs: [
      { name: 'init_1', type: 'ARRAY', required: true },
      { name: 'init_2', type: 'ARRAY', required: false },
      { name: 'init_3', type: 'ARRAY', required: false },
      { name: 'feedback_1', type: 'ARRAY', required: false },
      { name: 'feedback_2', type: 'ARRAY', required: false },
      { name: 'feedback_3', type: 'ARRAY', required: false },
      { name: 'iterations', type: 'NUMBER', required: false, default: 10 },
    ],
    outputs: [
      { name: 'loop_1', type: 'ARRAY', required: true },
      { name: 'loop_2', type: 'ARRAY', required: true },
      { name: 'loop_3', type: 'ARRAY', required: true },
      { name: 'done_1', type: 'ARRAY', required: true },
      { name: 'done_2', type: 'ARRAY', required: true },
      { name: 'done_3', type: 'ARRAY', required: true },
    ],
  },
];

// ---------------------------------------------------------------------------
// Group nodes by category
// ---------------------------------------------------------------------------

export function groupByCategory(nodes: PaletteNode[]): Record<string, PaletteNode[]> {
  const grouped: Record<string, PaletteNode[]> = {};
  for (const node of nodes) {
    if (!grouped[node.category]) grouped[node.category] = [];
    grouped[node.category].push(node);
  }
  return grouped;
}

export const groupedPalette: Record<string, PaletteNode[]> = groupByCategory(PALETTE_NODES);

// ---------------------------------------------------------------------------
// Fetch node registry from API (converts API format to PaletteNode[])
// ---------------------------------------------------------------------------

export async function fetchNodeRegistry(): Promise<PaletteNode[]> {
  try {
    const res = await fetch(`${API_BASE}/api/workflow/nodes`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const registry: Record<string, any> = await res.json();
    return Object.values(registry).map((spec: any) => ({
      type: spec.type,
      label: spec.label,
      category: spec.category,
      description: spec.description || '',
      doc: spec.doc || '',
      inputs: spec.inputs || [],
      outputs: spec.outputs || [],
    }));
  } catch (err) {
    console.warn('Failed to fetch node registry, using fallback:', err);
    return PALETTE_NODES;
  }
}
