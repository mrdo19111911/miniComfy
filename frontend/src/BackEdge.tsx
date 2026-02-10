/**
 * BackEdge — custom ReactFlow edge for n8n-style feedback connections.
 * Renders as a dashed orange line with an arrow, visually distinct from normal edges.
 */

import { type EdgeProps, getBezierPath, EdgeLabelRenderer } from 'reactflow';

const BACK_EDGE_COLOR = '#F59E0B';

export function BackEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <path
        id={id}
        style={{
          ...style,
          stroke: BACK_EDGE_COLOR,
          strokeWidth: 2,
          strokeDasharray: '8 4',
          fill: 'none',
        }}
        className="react-flow__edge-path"
        d={edgePath}
        markerEnd={markerEnd}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            fontSize: 9,
            color: BACK_EDGE_COLOR,
            background: 'rgba(0,0,0,0.6)',
            padding: '1px 4px',
            borderRadius: 3,
            fontWeight: 600,
            pointerEvents: 'none',
          }}
          className="nodrag nopan"
        >
          feedback
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
