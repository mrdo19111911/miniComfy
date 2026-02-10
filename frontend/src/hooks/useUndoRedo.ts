/**
 * useUndoRedo - Snapshot-based undo/redo for ReactFlow canvas.
 * Stores serializable snapshots of nodes + edges (up to 50 levels).
 */
import { useCallback, useRef } from 'react';
import type { Node, Edge } from 'reactflow';

interface Snapshot {
  nodes: Node[];
  edges: Edge[];
}

const MAX_HISTORY = 50;

/**
 * Strip non-serializable callbacks from node data for snapshot storage.
 */
function stripCallbacks(nodes: Node[]): Node[] {
  return nodes.map((n) => {
    const { onConfigChange, onDelete, ...rest } = n.data ?? {};
    return { ...n, data: rest };
  });
}

export function useUndoRedo() {
  const historyRef = useRef<Snapshot[]>([]);
  const indexRef = useRef(-1);
  const ignoreRef = useRef(false);

  /**
   * Push a new snapshot onto the history stack.
   * Call this after any user action that changes nodes/edges.
   */
  const pushSnapshot = useCallback((nodes: Node[], edges: Edge[]) => {
    if (ignoreRef.current) return;

    const snapshot: Snapshot = {
      nodes: stripCallbacks(nodes),
      edges: edges.map((e) => ({ ...e })),
    };

    // Truncate any redo history beyond current index
    const history = historyRef.current;
    history.splice(indexRef.current + 1);
    history.push(snapshot);

    // Cap at max
    if (history.length > MAX_HISTORY) {
      history.shift();
    }

    indexRef.current = history.length - 1;
  }, []);

  /**
   * Undo: return previous snapshot or null if nothing to undo.
   */
  const undo = useCallback((): Snapshot | null => {
    if (indexRef.current <= 0) return null;
    indexRef.current -= 1;
    return historyRef.current[indexRef.current];
  }, []);

  /**
   * Redo: return next snapshot or null if nothing to redo.
   */
  const redo = useCallback((): Snapshot | null => {
    if (indexRef.current >= historyRef.current.length - 1) return null;
    indexRef.current += 1;
    return historyRef.current[indexRef.current];
  }, []);

  /**
   * Whether undo/redo are currently available.
   */
  const canUndo = useCallback(() => indexRef.current > 0, []);
  const canRedo = useCallback(
    () => indexRef.current < historyRef.current.length - 1,
    [],
  );

  /**
   * Set ignore flag (to prevent snapshot on restore).
   */
  const setIgnore = useCallback((val: boolean) => {
    ignoreRef.current = val;
  }, []);

  /**
   * Clear all history.
   */
  const clearHistory = useCallback(() => {
    historyRef.current = [];
    indexRef.current = -1;
  }, []);

  return { pushSnapshot, undo, redo, canUndo, canRedo, setIgnore, clearHistory };
}
