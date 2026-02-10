/**
 * RerouteNode - A minimal pass-through node for organizing edge paths.
 * Has one input and one output. Visual: small circle.
 */
import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';

function RerouteNodeInner(_props: NodeProps) {
  return (
    <div
      style={{
        width: 16,
        height: 16,
        borderRadius: '50%',
        background: '#555',
        border: '2px solid #888',
        position: 'relative',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="in"
        style={{
          width: 8,
          height: 8,
          background: '#34D399',
          border: '1px solid #222',
          left: -5,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="out"
        style={{
          width: 8,
          height: 8,
          background: '#34D399',
          border: '1px solid #222',
          right: -5,
        }}
      />
    </div>
  );
}

export const RerouteNode = memo(RerouteNodeInner);
