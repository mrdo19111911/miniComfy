/**
 * WorkflowCanvas - ReactFlow canvas with drag-and-drop, loop group support,
 * WebSocket streaming, save/load, undo/redo, context menu, and log panel.
 */

import { useCallback, useState, useRef, useEffect } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Connection,
  addEdge,
  updateEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type OnConnect,
  type ReactFlowInstance,
  type NodeTypes,
} from 'reactflow';
import 'reactflow/dist/style.css';
import '@reactflow/node-resizer/dist/style.css';

import { categoryColor, API_BASE, fetchNodeRegistry } from './constants';
import { WorkflowNode } from './WorkflowNode';
import { LoopGroupNode } from './LoopGroupNode';
import { LoopStartNode } from './LoopStartNode';
import { LoopEndNode } from './LoopEndNode';
import { LoopN8nNode } from './LoopN8nNode';
import { RerouteNode } from './RerouteNode';
import { BackEdge } from './BackEdge';
import { NodePalette } from './NodePalette';
import { useWebSocket } from './hooks/useWebSocket';
import { useUndoRedo } from './hooks/useUndoRedo';
import { LogPanel, type LogEntry } from './components/LogPanel';
import { Toolbar } from './components/Toolbar';
import { ContextMenu, type ContextMenuAction } from './components/ContextMenu';
import { ValidationPanel, type ValidationIssue } from './components/ValidationPanel';
import { DataInspector } from './components/DataInspector';
import { ErrorTracePanel, type ErrorTraceInfo } from './components/ErrorTracePanel';
import { PluginManager } from './components/PluginManager';
import { StatusBar } from './components/StatusBar';
import { HelpPanel } from './components/HelpPanel';
import type { PaletteNode } from './types';

// ---------------------------------------------------------------------------
// Node type registry
// ---------------------------------------------------------------------------

const nodeTypes: NodeTypes = {
  workflow: WorkflowNode,
  loop_group: LoopGroupNode,
  loop_start: LoopStartNode,
  loop_end: LoopEndNode,
  loop_node: LoopN8nNode,
  reroute: RerouteNode,
};

const edgeTypes = {
  back_edge: BackEdge,
};

// ---------------------------------------------------------------------------
// Helper: ensure parents come before children (ReactFlow requirement)
// ---------------------------------------------------------------------------

function sortNodes(nodes: Node[]): Node[] {
  const parents = nodes.filter((n) => n.type === 'loop_group');
  const children = nodes.filter((n) => n.parentNode);
  const others = nodes.filter((n) => n.type !== 'loop_group' && !n.parentNode);
  return [...parents, ...others, ...children];
}

// ---------------------------------------------------------------------------
// Save/Load helpers
// ---------------------------------------------------------------------------

interface SavedWorkflow {
  name: string;
  version: string;
  viewport?: { x: number; y: number; zoom: number };
  nodes: Array<{
    id: string;
    type: string;
    position: { x: number; y: number };
    data: Record<string, unknown>;
    parentNode?: string;
    style?: Record<string, unknown>;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
  }>;
}

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function openFilePicker(): Promise<string | null> {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = () => {
      const file = input.files?.[0];
      if (!file) return resolve(null);
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.readAsText(file);
    };
    input.click();
  });
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function WorkflowCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [nodeRegistry, setNodeRegistry] = useState<PaletteNode[] | undefined>();

  // Fetch node registry from backend
  const refetchRegistry = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/workflow/nodes`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const registry: Record<string, any> = await res.json();
      setNodeRegistry(
        Object.values(registry).map((spec: any) => ({
          type: spec.type,
          label: spec.label,
          category: spec.category,
          description: spec.description || '',
          doc: spec.doc || '',
          inputs: spec.inputs || [],
          outputs: spec.outputs || [],
        })),
      );
    } catch {
      fetchNodeRegistry().then(setNodeRegistry);
    }
  }, []);

  // Fetch on mount (retry until API responds)
  useEffect(() => {
    let cancelled = false;
    const tryFetch = async () => {
      try {
        await refetchRegistry();
      } catch {
        if (!cancelled) setTimeout(tryFetch, 5000);
      }
    };
    tryFetch();
    return () => { cancelled = true; };
  }, [refetchRegistry]);

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<string | null>(null);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // ---- Log panel state ----
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logPanelVisible, setLogPanelVisible] = useState(false);

  // ---- Undo/Redo ----
  const { pushSnapshot, undo, redo, canUndo, canRedo, setIgnore, clearHistory } = useUndoRedo();

  // ---- Context menu state ----
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    actions: ContextMenuAction[];
  } | null>(null);

  // ---- Validation state ----
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [validationVisible, setValidationVisible] = useState(false);

  // ---- Data Inspector state ----
  const [dataInspector, setDataInspector] = useState<{
    x: number;
    y: number;
    data: Record<string, unknown>;
    edgeLabel: string;
  } | null>(null);

  // ---- Error trace state ----
  const [errorTrace, setErrorTrace] = useState<ErrorTraceInfo | null>(null);
  const [errorTraceVisible, setErrorTraceVisible] = useState(false);

  // ---- Modal states ----
  const [pluginManagerVisible, setPluginManagerVisible] = useState(false);
  const [helpVisible, setHelpVisible] = useState(false);

  // ---- Health data ----
  const [healthData, setHealthData] = useState({ pluginCount: 0, memoryMb: 0 });

  // Fetch health data periodically
  useEffect(() => {
    const fetchHealth = () => {
      fetch(`${API_BASE}/api/health`)
        .then((r) => r.json())
        .then((d) => {
          setHealthData({
            pluginCount: d.plugins_loaded ?? 0,
            memoryMb: d.memory_mb ?? 0,
          });
        })
        .catch(() => {});
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  // ---- WebSocket ----
  const { connected, on: wsOn } = useWebSocket(`ws://localhost:8500/ws/execution`);

  // Register WS event handlers
  useEffect(() => {
    wsOn('start', (data) => {
      const entry: LogEntry = {
        timestamp: Date.now() / 1000,
        level: 'SYSTEM',
        message: `Workflow started (${data.total_nodes} nodes)`,
        event: 'start',
      };
      setLogs((prev) => [...prev, entry]);
    });

    wsOn('node_start', (data) => {
      const nodeId = data.node_id as string;
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, status: 'running' } } : n,
        ),
      );
      setLogs((prev) => [
        ...prev,
        {
          timestamp: Date.now() / 1000,
          level: 'INFO',
          node_id: nodeId,
          node_type: data.node_label as string,
          message: `Started`,
          event: 'node_start',
        },
      ]);
    });

    wsOn('node_complete', (data) => {
      const nodeId = data.node_id as string;
      const duration = data.duration_ms as number;
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, status: 'completed', result: data.outputs } }
            : n,
        ),
      );
      setLogs((prev) => [
        ...prev,
        {
          timestamp: Date.now() / 1000,
          level: 'INFO',
          node_id: nodeId,
          message: `Completed (${duration?.toFixed(1) ?? '?'}ms)`,
          event: 'node_complete',
        },
      ]);
    });

    wsOn('node_error', (data) => {
      const nodeId = data.node_id as string;
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, status: 'error' } } : n,
        ),
      );
      setLogs((prev) => [
        ...prev,
        {
          timestamp: Date.now() / 1000,
          level: 'ERROR',
          node_id: nodeId,
          message: data.error as string,
          event: 'node_error',
        },
      ]);
      setLogPanelVisible(true); // Auto-show on error
      // Populate error trace panel
      setErrorTrace({
        node_id: nodeId,
        node_type: (data.node_label as string) ?? 'unknown',
        message: data.error as string,
        stack_trace: (data.stack_trace as string) ?? '',
      });
      setErrorTraceVisible(true);
    });

    wsOn('log', (data) => {
      setLogs((prev) => [
        ...prev,
        {
          timestamp: (data.timestamp as number) || Date.now() / 1000,
          level: data.level as string,
          node_id: data.node_id as string,
          node_type: data.node_type as string,
          message: data.message as string,
          event: 'log',
        },
      ]);
    });

    wsOn('complete', (data) => {
      const totalMs = data.total_ms as number;
      setLogs((prev) => [
        ...prev,
        {
          timestamp: Date.now() / 1000,
          level: 'SYSTEM',
          message: `Workflow complete (${totalMs?.toFixed(1) ?? '?'}ms)`,
          event: 'complete',
        },
      ]);
    });
  }, [wsOn, setNodes]);

  // ---- Snapshot helper: push current state for undo ----

  const snapshot = useCallback(() => {
    pushSnapshot(nodes, edges);
  }, [nodes, edges, pushSnapshot]);

  // ---- Apply undo/redo result ----

  const applySnapshot = useCallback(
    (snap: { nodes: Node[]; edges: Edge[] } | null) => {
      if (!snap) return;
      setIgnore(true);
      setNodes(
        sortNodes(
          snap.nodes.map((n) => ({
            ...n,
            data: { ...n.data, onConfigChange, onDelete: onDeleteNode },
          })),
        ),
      );
      setEdges(
        snap.edges.map((e) => ({
          ...e,
          animated: true,
          style: { stroke: '#34D399', strokeWidth: 2 },
        })),
      );
      setIgnore(false);
    },
    [setNodes, setEdges, setIgnore],
  );

  // ---- Config change handler (passed to nodes via data) ----

  const onConfigChange = useCallback(
    (nodeId: string, name: string, value: number) => {
      snapshot();
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id !== nodeId) return n;
          return {
            ...n,
            data: {
              ...n.data,
              config: { ...n.data.config, [name]: value },
            },
          };
        }),
      );
    },
    [setNodes, snapshot],
  );

  // ---- Delete node handler (passed to nodes via data.onDelete) ----

  const onDeleteNode = useCallback(
    (nodeId: string) => {
      snapshot();
      setNodes((nds) => {
        const deletedNode = nds.find((n) => n.id === nodeId);
        if (!deletedNode) return nds;

        if (deletedNode.type === 'loop_group') {
          const childIds = new Set(
            nds.filter((n) => n.parentNode === nodeId).map((n) => n.id),
          );
          childIds.add(nodeId);
          setEdges((eds) =>
            eds.filter((e) => !childIds.has(e.source) && !childIds.has(e.target)),
          );
          return nds.filter((n) => !childIds.has(n.id));
        }

        setEdges((eds) =>
          eds.filter((e) => e.source !== nodeId && e.target !== nodeId),
        );
        return nds.filter((n) => n.id !== nodeId);
      });
    },
    [setNodes, setEdges, snapshot],
  );

  // ---- Toggle mute on a node ----

  const toggleMute = useCallback(
    (nodeId: string) => {
      snapshot();
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id !== nodeId) return n;
          return {
            ...n,
            data: { ...n.data, muted: !n.data.muted },
          };
        }),
      );
    },
    [setNodes, snapshot],
  );

  // ---- Connection handler ----

  const onConnect: OnConnect = useCallback(
    (params: Connection) => {
      snapshot();
      // Detect back-edges: connections to feedback_* ports on loop_node
      const targetNode = nodes.find((n) => n.id === params.target);
      const isBackEdge = targetNode?.data?.nodeType === 'loop_node' &&
                         params.targetHandle?.startsWith('feedback_');
      setEdges((eds) =>
        addEdge(
          isBackEdge
            ? {
                ...params,
                type: 'back_edge',
                animated: false,
                data: { is_back_edge: true },
                style: { stroke: '#F59E0B', strokeWidth: 2, strokeDasharray: '8 4' },
              }
            : { ...params, animated: true, style: { stroke: '#34D399', strokeWidth: 2 } },
          eds,
        ),
      );
    },
    [setEdges, snapshot, nodes],
  );

  // ---- Edge update: drag to rewire, drop on empty to delete ----

  const edgeUpdateSuccessful = useRef(true);

  const onEdgeUpdateStart = useCallback(() => {
    edgeUpdateSuccessful.current = false;
  }, []);

  const onEdgeUpdate = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      edgeUpdateSuccessful.current = true;
      snapshot();
      setEdges((els) => updateEdge(oldEdge, newConnection, els));
    },
    [setEdges, snapshot],
  );

  const onEdgeUpdateEnd = useCallback(
    (_: MouseEvent | TouchEvent, edge: Edge) => {
      if (!edgeUpdateSuccessful.current) {
        snapshot();
        setEdges((eds) => eds.filter((e) => e.id !== edge.id));
      }
      edgeUpdateSuccessful.current = true;
    },
    [setEdges, snapshot],
  );

  // ---- Find loop_group node at a given flow position ----

  const findLoopGroupAt = useCallback(
    (flowPos: { x: number; y: number }): Node | null => {
      for (const node of nodes) {
        if (node.type !== 'loop_group') continue;
        const w = (node.style?.width as number) ?? (node.width ?? 500);
        const h = (node.style?.height as number) ?? (node.height ?? 300);
        const x0 = node.position.x;
        const y0 = node.position.y;
        if (
          flowPos.x >= x0 &&
          flowPos.x <= x0 + w &&
          flowPos.y >= y0 &&
          flowPos.y <= y0 + h
        ) {
          return node;
        }
      }
      return null;
    },
    [nodes],
  );

  // ---- Drag over ----

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // ---- Drop from palette ----

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const json = event.dataTransfer.getData('application/reactflow');
      if (!json) return;

      const spec = JSON.parse(json);
      const isLoopGroup = spec.type === 'loop_group';
      const isNewLoopType = ['loop_start', 'loop_end', 'loop_node'].includes(spec.type);

      let position = { x: event.clientX - 300, y: event.clientY - 80 };
      if (rfInstance) {
        position = rfInstance.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });
      }

      const defaultConfig: Record<string, unknown> = {};
      for (const port of spec.inputs ?? []) {
        if (port.type === 'NUMBER' && port.default != null) {
          defaultConfig[port.name] = port.default;
        }
      }

      let parentId: string | undefined;
      if (!isLoopGroup && !isNewLoopType) {
        const loopGroup = findLoopGroupAt(position);
        if (loopGroup) {
          parentId = loopGroup.id;
          position = {
            x: position.x - loopGroup.position.x,
            y: position.y - loopGroup.position.y,
          };
        }
      }

      snapshot();

      // Map node type to ReactFlow component type
      const rfType = isLoopGroup ? 'loop_group'
        : isNewLoopType ? spec.type  // loop_start, loop_end, loop_node
        : 'workflow';

      const newNode: Node = {
        id: `${spec.type}_${Date.now()}`,
        type: rfType,
        position,
        ...(isLoopGroup ? { style: { width: 500, height: 300 } } : {}),
        ...(parentId
          ? { parentNode: parentId, extent: 'parent' as const }
          : {}),
        data: {
          label: spec.label,
          color: spec.color,
          inputs: spec.inputs,
          outputs: spec.outputs,
          nodeType: spec.type,
          category: spec.category,
          config: defaultConfig,
          onConfigChange,
          onDelete: onDeleteNode,
        },
      };

      setNodes((nds) => sortNodes([...nds, newNode]));
    },
    [setNodes, rfInstance, findLoopGroupAt, onConfigChange, onDeleteNode, snapshot],
  );

  // ---- Drag existing node into/out of loop group ----

  const onNodeDragStop = useCallback(
    (_event: React.MouseEvent, draggedNode: Node) => {
      if (draggedNode.type === 'loop_group') return;

      let absPos = { ...draggedNode.position };
      if (draggedNode.parentNode) {
        const parent = nodes.find((n) => n.id === draggedNode.parentNode);
        if (parent) {
          absPos = {
            x: parent.position.x + draggedNode.position.x,
            y: parent.position.y + draggedNode.position.y,
          };
        }
      }

      const target = findLoopGroupAt(absPos);
      const newParent = target?.id;
      const currentParent = draggedNode.parentNode;

      if (newParent === currentParent) return;

      snapshot();

      setNodes((nds) => {
        const updated = nds.map((n) => {
          if (n.id !== draggedNode.id) return n;

          if (newParent && target) {
            return {
              ...n,
              parentNode: newParent,
              extent: 'parent' as const,
              position: {
                x: absPos.x - target.position.x,
                y: absPos.y - target.position.y,
              },
            };
          } else {
            const { parentNode, extent, ...rest } = n as any;
            return {
              ...rest,
              position: absPos,
            };
          }
        });
        return sortNodes(updated);
      });
    },
    [nodes, findLoopGroupAt, setNodes, snapshot],
  );

  // ---- Context menu handlers ----

  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault();
      const isMuted = !!node.data.muted;
      const actions: ContextMenuAction[] = [
        {
          label: isMuted ? 'Unmute Node' : 'Mute Node',
          onClick: () => toggleMute(node.id),
        },
        {
          label: 'Delete Node',
          onClick: () => onDeleteNode(node.id),
        },
        { label: '', onClick: () => {}, separator: true },
        {
          label: 'Add Reroute After',
          onClick: () => {
            snapshot();
            const rerouteId = `reroute_${Date.now()}`;
            const newNode: Node = {
              id: rerouteId,
              type: 'reroute',
              position: {
                x: node.position.x + 200,
                y: node.position.y + 30,
              },
              data: {},
            };
            setNodes((nds) => sortNodes([...nds, newNode]));
          },
        },
      ];
      setContextMenu({ x: event.clientX, y: event.clientY, actions });
    },
    [toggleMute, onDeleteNode, snapshot, setNodes],
  );

  const onPaneContextMenu = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      const flowPos = rfInstance?.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      }) ?? { x: event.clientX - 300, y: event.clientY - 80 };

      const actions: ContextMenuAction[] = [
        {
          label: 'Add Reroute Node',
          onClick: () => {
            snapshot();
            const rerouteId = `reroute_${Date.now()}`;
            const newNode: Node = {
              id: rerouteId,
              type: 'reroute',
              position: flowPos,
              data: {},
            };
            setNodes((nds) => sortNodes([...nds, newNode]));
          },
        },
        { label: '', onClick: () => {}, separator: true },
        {
          label: 'Select All (Ctrl+A)',
          onClick: () => {
            setNodes((nds) => nds.map((n) => ({ ...n, selected: true })));
            setEdges((eds) => eds.map((e) => ({ ...e, selected: true })));
          },
        },
      ];
      setContextMenu({ x: event.clientX, y: event.clientY, actions });
    },
    [rfInstance, snapshot, setNodes, setEdges],
  );

  // ---- Build API payload ----

  const buildPayload = useCallback(() => {
    return {
      name: 'PipeStudio Workflow',
      nodes: nodes
        .filter((n) => n.type !== 'reroute') // Reroute nodes are visual only
        .map((n) => ({
          id: n.id,
          type: n.data.nodeType ?? n.type,
          position: n.position,
          params: n.data.config ?? {},
          parent_id: n.parentNode ?? null,
          muted: !!n.data.muted,
        })),
      edges: edges.map((e, i) => ({
        id: e.id ?? `e${i}`,
        source: e.source,
        source_port: e.sourceHandle ?? 'array',
        target: e.target,
        target_port: e.targetHandle ?? 'array',
        is_back_edge: !!(e.data as any)?.is_back_edge,
      })),
    };
  }, [nodes, edges]);

  // ---- Execute workflow ----

  const executeWorkflow = useCallback(async () => {
    setExecuting(true);
    setExecutionResult(null);

    // Add run separator in logs
    setLogs((prev) => [
      ...prev,
      {
        timestamp: Date.now() / 1000,
        level: 'SYSTEM',
        message: '--- New Execution ---',
        event: 'separator',
      },
    ]);

    // Mark all nodes as running
    setNodes((nds) =>
      nds.map((n) => ({ ...n, data: { ...n.data, status: 'running', result: undefined } })),
    );

    try {
      const payload = buildPayload();
      const response = await fetch(`${API_BASE}/api/workflow/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(err.detail ?? `HTTP ${response.status}`);
      }

      const results = await response.json();

      // Update node statuses and results (WS events may have already done this)
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: {
            ...n.data,
            status: 'completed',
            result: results[n.id] ?? n.data.result,
          },
        })),
      );

      setExecutionResult('Workflow executed successfully!');
    } catch (err: any) {
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, status: n.data.status === 'completed' ? 'completed' : 'error' },
        })),
      );
      setExecutionResult(`Error: ${err.message}`);
    } finally {
      setExecuting(false);
    }
  }, [buildPayload, setNodes]);

  // ---- Clear canvas ----

  const clearCanvas = useCallback(() => {
    snapshot();
    setNodes([]);
    setEdges([]);
    setExecutionResult(null);
    clearHistory();
  }, [setNodes, setEdges, snapshot, clearHistory]);

  // ---- Validate workflow ----

  const validateWorkflow = useCallback(async () => {
    try {
      const payload = buildPayload();
      const response = await fetch(`${API_BASE}/api/workflow/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const issues: ValidationIssue[] = await response.json();
      setValidationIssues(issues);
      setValidationVisible(true);
    } catch (err: any) {
      setValidationIssues([
        { level: 'error', node_id: null, message: `Validation failed: ${err.message}` },
      ]);
      setValidationVisible(true);
    }
  }, [buildPayload]);

  // ---- Highlight node (scroll into view + select) ----

  const highlightNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          selected: n.id === nodeId,
        })),
      );
      // Center on the node
      const node = nodes.find((n) => n.id === nodeId);
      if (node && rfInstance) {
        rfInstance.setCenter(node.position.x + 80, node.position.y + 40, {
          zoom: 1.2,
          duration: 400,
        });
      }
    },
    [nodes, rfInstance, setNodes],
  );

  // ---- Edge click for Data Inspector ----

  const onEdgeClick = useCallback(
    (event: React.MouseEvent, edge: Edge) => {
      // Find source node outputs to show in inspector
      const sourceNode = nodes.find((n) => n.id === edge.source);
      const result = sourceNode?.data?.result;
      if (!result || typeof result !== 'object') return;

      setDataInspector({
        x: event.clientX,
        y: event.clientY,
        data: result as Record<string, unknown>,
        edgeLabel: `${edge.source} → ${edge.target}`,
      });
    },
    [nodes],
  );

  // ---- Save workflow ----

  const saveWorkflow = useCallback(() => {
    const viewport = rfInstance?.getViewport() ?? { x: 0, y: 0, zoom: 1 };
    const saved: SavedWorkflow = {
      name: 'PipeStudio Workflow',
      version: '1.0.0',
      viewport,
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type!,
        position: n.position,
        data: {
          label: n.data.label,
          color: n.data.color,
          inputs: n.data.inputs,
          outputs: n.data.outputs,
          nodeType: n.data.nodeType,
          category: n.data.category,
          config: n.data.config,
          muted: n.data.muted,
        },
        ...(n.parentNode ? { parentNode: n.parentNode } : {}),
        ...(n.style ? { style: n.style as Record<string, unknown> } : {}),
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
      })),
    };
    downloadJson(saved, `pipestudio-workflow-${Date.now()}.json`);
  }, [nodes, edges, rfInstance]);

  // ---- Load workflow (from JSON string) ----

  const restoreWorkflow = useCallback(
    (json: string) => {
      try {
        const saved: SavedWorkflow = JSON.parse(json);
        if (!saved.nodes || !saved.edges) {
          throw new Error('Invalid workflow file');
        }

        // Restore nodes with callbacks reattached
        const restoredNodes: Node[] = saved.nodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          ...(n.parentNode ? { parentNode: n.parentNode, extent: 'parent' as const } : {}),
          ...(n.style ? { style: n.style } : {}),
          data: {
            ...n.data,
            onConfigChange,
            onDelete: onDeleteNode,
          },
        }));

        const restoredEdges: Edge[] = saved.edges.map((e) => {
          const isBack = !!(e as any).data?.is_back_edge;
          return {
            id: e.id,
            source: e.source,
            target: e.target,
            sourceHandle: e.sourceHandle,
            targetHandle: e.targetHandle,
            ...(isBack
              ? {
                  type: 'back_edge',
                  animated: false,
                  data: { is_back_edge: true },
                  style: { stroke: '#F59E0B', strokeWidth: 2, strokeDasharray: '8 4' },
                }
              : {
                  animated: true,
                  style: { stroke: '#34D399', strokeWidth: 2 },
                }),
          };
        });

        setNodes(sortNodes(restoredNodes));
        setEdges(restoredEdges);
        setExecutionResult(null);
        clearHistory();

        // Restore viewport
        if (saved.viewport && rfInstance) {
          setTimeout(() => {
            rfInstance.setViewport(saved.viewport!);
          }, 50);
        }
      } catch (err: any) {
        setExecutionResult(`Load error: ${err.message}`);
      }
    },
    [setNodes, setEdges, rfInstance, onConfigChange, onDeleteNode, clearHistory],
  );

  const loadWorkflow = useCallback(async () => {
    const text = await openFilePicker();
    if (text) restoreWorkflow(text);
  }, [restoreWorkflow]);

  // ---- Load example from API ----

  const loadExample = useCallback(
    async (filename: string) => {
      try {
        const resp = await fetch(`${API_BASE}/api/workflow/example/${filename}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        // Example format has nodes as {id, type, params, position, parent_id}
        // Convert to canvas nodes
        const registryMap = new Map<string, PaletteNode>();
        for (const n of nodeRegistry ?? []) {
          registryMap.set(n.type, n);
        }

        const canvasNodes: Node[] = data.nodes.map((n: any) => {
          const spec = registryMap.get(n.type);
          const isLoop = n.type === 'loop_group';
          const isNewLoop = ['loop_start', 'loop_end', 'loop_node'].includes(n.type);
          const defaultConfig: Record<string, unknown> = {};
          for (const port of spec?.inputs ?? []) {
            if (port.type === 'NUMBER' && port.default != null) {
              defaultConfig[port.name] = port.default;
            }
          }
          // Merge defaults with saved params
          const config = { ...defaultConfig, ...n.params };

          return {
            id: n.id,
            type: isLoop ? 'loop_group' : isNewLoop ? n.type : 'workflow',
            position: n.position ?? { x: 0, y: 0 },
            ...(isLoop ? { style: { width: 500, height: 300 } } : {}),
            ...(n.parent_id
              ? { parentNode: n.parent_id, extent: 'parent' as const }
              : {}),
            data: {
              label: spec?.label ?? n.type,
              color: categoryColor(spec?.category ?? ''),
              inputs: spec?.inputs ?? [],
              outputs: spec?.outputs ?? [],
              nodeType: n.type,
              category: spec?.category ?? '',
              config,
              onConfigChange,
              onDelete: onDeleteNode,
            },
          };
        });

        const canvasEdges: Edge[] = (data.edges ?? []).map((e: any) => {
          const isBack = !!e.is_back_edge;
          return {
            id: e.id,
            source: e.source,
            target: e.target,
            sourceHandle: e.source_port,
            targetHandle: e.target_port,
            ...(isBack
              ? {
                  type: 'back_edge',
                  animated: false,
                  data: { is_back_edge: true },
                  style: { stroke: '#F59E0B', strokeWidth: 2, strokeDasharray: '8 4' },
                }
              : {
                  animated: true,
                  style: { stroke: '#34D399', strokeWidth: 2 },
                }),
          };
        });

        setNodes(sortNodes(canvasNodes));
        setEdges(canvasEdges);
        setExecutionResult(`Loaded: ${data.name ?? filename}`);
        clearHistory();
      } catch (err: any) {
        setExecutionResult(`Load error: ${err.message}`);
      }
    },
    [setNodes, setEdges, nodeRegistry, onConfigChange, onDeleteNode, clearHistory],
  );

  // ---- Keyboard shortcuts ----

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      // Ctrl+S: Save
      if (mod && e.key === 's') {
        e.preventDefault();
        saveWorkflow();
      }
      // Ctrl+O: Open
      if (mod && e.key === 'o') {
        e.preventDefault();
        loadWorkflow();
      }
      // Ctrl+Z: Undo
      if (mod && !e.shiftKey && e.key === 'z') {
        e.preventDefault();
        applySnapshot(undo());
      }
      // Ctrl+Shift+Z or Ctrl+Y: Redo
      if ((mod && e.shiftKey && e.key === 'z') || (mod && e.key === 'y')) {
        e.preventDefault();
        applySnapshot(redo());
      }
      // F1: Help
      if (e.key === 'F1') {
        e.preventDefault();
        setHelpVisible((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [saveWorkflow, loadWorkflow, undo, redo, applySnapshot]);

  // ---- MiniMap color ----

  const miniMapColor = useCallback(
    (node: Node) => {
      if (node.data?.muted) return '#555';
      return node.data?.color ?? '#6B7280';
    },
    [],
  );

  return (
    <div
      style={{
        width: '100%',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: '#111',
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
      }}
    >
      {/* CSS animations + edge styles */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .react-flow__attribution { display: none !important; }
        .react-flow__edge:hover .react-flow__edge-path {
          stroke: #fff !important;
          stroke-width: 3px !important;
          cursor: pointer;
        }
        .react-flow__edge.selected .react-flow__edge-path {
          stroke: #EF4444 !important;
          stroke-width: 3px !important;
        }
        .react-flow__edgeupdater {
          cursor: grab;
        }
      `}</style>

      {/* Toolbar */}
      <Toolbar
        onExecute={executeWorkflow}
        onClear={clearCanvas}
        onSave={saveWorkflow}
        onLoad={loadWorkflow}
        onLoadExample={loadExample}
        onToggleLog={() => setLogPanelVisible((v) => !v)}
        onToggleValidation={() => setValidationVisible((v) => !v)}
        onValidate={validateWorkflow}
        onUndo={() => applySnapshot(undo())}
        onRedo={() => applySnapshot(redo())}
        onOpenPlugins={() => setPluginManagerVisible(true)}
        onOpenHelp={() => setHelpVisible(true)}
        canUndo={canUndo()}
        canRedo={canRedo()}
        executing={executing}
        logPanelVisible={logPanelVisible}
        validationVisible={validationVisible}
        validationErrors={validationIssues.filter((i) => i.level === 'error').length}
        logCount={logs.length}
        connected={connected}
        executionResult={executionResult}
      />

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* Sidebar */}
          <NodePalette
            collapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed((v) => !v)}
            nodeList={nodeRegistry}
          />

          {/* Canvas */}
          <div ref={reactFlowWrapper} style={{ flex: 1, position: 'relative' }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onEdgeUpdateStart={onEdgeUpdateStart}
              onEdgeUpdate={onEdgeUpdate}
              onEdgeUpdateEnd={onEdgeUpdateEnd}
              onDragOver={onDragOver}
              onDrop={onDrop}
              onNodeDragStop={onNodeDragStop}
              onNodeContextMenu={onNodeContextMenu}
              onPaneContextMenu={onPaneContextMenu}
              onEdgeClick={onEdgeClick}
              onInit={setRfInstance}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              deleteKeyCode={['Backspace', 'Delete']}
              edgesUpdatable
              edgesFocusable
              defaultEdgeOptions={{
                animated: true,
                style: { stroke: '#34D399', strokeWidth: 2 },
              }}
              style={{ background: '#1A1A2E' }}
            >
              <Background color="#333" gap={20} size={1} />
              <Controls />
              <MiniMap
                nodeColor={miniMapColor}
                maskColor="rgba(0,0,0,0.7)"
                style={{ background: '#1E1E1E', border: '1px solid #333' }}
              />
            </ReactFlow>
          </div>
        </div>

        {/* Log Panel */}
        <LogPanel
          logs={logs}
          onClear={() => setLogs([])}
          visible={logPanelVisible}
        />

        {/* Validation Panel */}
        <ValidationPanel
          issues={validationIssues}
          onValidate={validateWorkflow}
          onHighlightNode={highlightNode}
          visible={validationVisible}
        />

        {/* Error Trace Panel */}
        <ErrorTracePanel
          error={errorTrace}
          visible={errorTraceVisible}
          onClose={() => setErrorTraceVisible(false)}
          onHighlightNode={highlightNode}
        />
      </div>

      {/* Status Bar */}
      <StatusBar
        connected={connected}
        pluginCount={healthData.pluginCount}
        memoryMb={healthData.memoryMb}
        version="1.0.0"
        nodeCount={nodes.length}
        edgeCount={edges.length}
      />

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          actions={contextMenu.actions}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Data Inspector */}
      {dataInspector && (
        <DataInspector
          x={dataInspector.x}
          y={dataInspector.y}
          data={dataInspector.data}
          edgeLabel={dataInspector.edgeLabel}
          onClose={() => setDataInspector(null)}
        />
      )}

      {/* Plugin Manager Modal */}
      <PluginManager
        visible={pluginManagerVisible}
        onClose={() => setPluginManagerVisible(false)}
        onReload={refetchRegistry}
      />

      {/* Help Modal */}
      <HelpPanel
        visible={helpVisible}
        onClose={() => setHelpVisible(false)}
        version="1.0.0"
      />
    </div>
  );
}
