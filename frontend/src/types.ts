/**
 * TypeScript types for PipeStudio workflow builder.
 */

export interface PortSpec {
  name: string;
  type: string;  // 'ARRAY' | 'NUMBER' | 'STRING' | ...
  required: boolean;
  default?: unknown;
}

export interface PaletteNode {
  type: string;
  label: string;
  category: string;
  description: string;
  doc?: string;
  inputs: PortSpec[];
  outputs: PortSpec[];
}

/** Visual state for nodes on the canvas based on plugin availability. */
export type NodeVisualState = 'normal' | 'disabled' | 'broken' | 'muted';

/** Plugin info within a project (from GET /api/plugins). */
export interface PluginInfo {
  id: string;
  type: 'file' | 'folder';
  state: 'active' | 'inactive';
  node_types: string[];
}

/** Project info from hierarchical GET /api/plugins response. */
export interface ProjectInfo {
  project: string;
  manifest: {
    name: string;
    version: string;
    description: string;
    categories: Record<string, string>;
  };
  status: 'ok' | 'error';
  error: string | null;
  plugins: PluginInfo[];
}
