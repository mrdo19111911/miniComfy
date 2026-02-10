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
