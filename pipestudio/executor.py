"""Workflow executor with loop support and event hooks.

Supports three loop styles:
- Legacy loop_group (container with parent_id children)
- ComfyUI style (loop_start + loop_end pair)
- n8n style (loop_node with back-edge feedback)
"""
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Set

import numpy as np

from pipestudio.models import WorkflowDefinition, WorkflowEdge, WorkflowNode, NodeUnavailableError
from pipestudio.plugin_api import get_executors, logger as node_logger


MAX_ITERATIONS = 10000


def _clamp_iterations(raw) -> int:
    """Clamp iterations to [1, MAX_ITERATIONS]."""
    return max(1, min(int(raw), MAX_ITERATIONS))


class WorkflowExecutor:
    """Executes a workflow DAG with support for loops and event streaming."""

    def __init__(
        self,
        workflow: WorkflowDefinition,
        event_handler: Optional[Callable] = None,
        breakpoints: Optional[set] = None,
    ):
        self.workflow = workflow
        self.nodes_by_id: Dict[str, WorkflowNode] = {n.id: n for n in workflow.nodes}
        self.node_outputs: Dict[str, Dict[str, Any]] = {}
        self.event_handler = event_handler
        self.breakpoints: set = breakpoints or set()
        self.executors = get_executors()
        self._log_entries: List[dict] = []
        self._node_timings: Dict[str, float] = {}

    def _emit(self, event_type: str, **data):
        """Emit an event (for WebSocket streaming)."""
        if self.event_handler:
            self.event_handler(event_type, data)

    def _log_handler(self, level: str, node_id: str, node_type: str, message: str):
        """Captures logs from plugin nodes via the logger singleton."""
        entry = {
            "level": level,
            "node_id": node_id,
            "node_type": node_type,
            "message": message,
            "timestamp": time.time(),
        }
        self._log_entries.append(entry)
        self._emit("log", **entry)
        print(f"  [{level}] [{node_type}:{node_id}] {message}")

    def _topological_sort(self, nodes: List[WorkflowNode], edges: List[WorkflowEdge]) -> List[str]:
        """Kahn's algorithm on given nodes/edges. Skips back-edges."""
        node_ids = {n.id for n in nodes}
        in_degree = {nid: 0 for nid in node_ids}
        adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}

        for e in edges:
            if e.is_back_edge:
                continue  # Skip back-edges to avoid false cycles
            if e.source in node_ids and e.target in node_ids:
                in_degree[e.target] = in_degree.get(e.target, 0) + 1
                adj[e.source].append(e.target)

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for neighbor in adj[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    def _get_node_inputs(self, node_id: str, edges: List[WorkflowEdge]) -> Dict[str, Any]:
        """Collect inputs for a node from upstream outputs.

        If multiple edges target the same port, values are collected into a list.
        Single-edge ports receive the value directly (no wrapping).
        """
        edge_stacks: Dict[str, list] = {}
        for e in edges:
            if e.is_back_edge:
                continue  # Back-edges handled by loop executor
            if e.target == node_id and e.source in self.node_outputs:
                source_outputs = self.node_outputs[e.source]
                if e.source_port in source_outputs:
                    if e.target_port not in edge_stacks:
                        edge_stacks[e.target_port] = []
                    edge_stacks[e.target_port].append(source_outputs[e.source_port])

        inputs: Dict[str, Any] = {}
        for port_name, values in edge_stacks.items():
            inputs[port_name] = values[0] if len(values) == 1 else values
        return inputs

    # ------------------------------------------------------------------
    # Legacy loop_group (container with parent_id children)
    # ------------------------------------------------------------------

    def _execute_loop_group(self, node_def: WorkflowNode, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute child nodes N times, passing output as input each iteration."""
        iterations = _clamp_iterations(node_def.params.get("iterations", 10))
        all_edges = self.workflow.edges

        child_nodes = [n for n in self.workflow.nodes if n.parent_id == node_def.id]
        if not child_nodes:
            print(f"  Loop group {node_def.id} has no children, passing through")
            return inputs

        child_ids = {n.id for n in child_nodes}
        internal_edges = [
            e for e in all_edges
            if (e.source in child_ids or e.source == node_def.id)
            and (e.target in child_ids or e.target == node_def.id)
        ]

        entry_edges = [e for e in internal_edges if e.source == node_def.id and e.target in child_ids]
        feedback_map = {}
        for e in entry_edges:
            feedback_map[e.target_port] = e.source_port

        children_with_outgoing_internal = set()
        for e in internal_edges:
            if e.source in child_ids and e.target in child_ids:
                children_with_outgoing_internal.add(e.source)
        exit_candidates = child_ids - children_with_outgoing_internal
        exit_node_id = exit_candidates.pop() if exit_candidates else child_nodes[-1].id

        current_data = dict(inputs)
        for i in range(iterations):
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  Loop iteration {i + 1}/{iterations}")
                self._emit("log", level="INFO", node_id=node_def.id,
                           node_type="loop_group",
                           message=f"Iteration {i + 1}/{iterations}",
                           timestamp=time.time())

            virtual_id = "__loop_in__"
            self.node_outputs[virtual_id] = current_data

            sub_edges = []
            for e in internal_edges:
                if e.source == node_def.id:
                    sub_edges.append(WorkflowEdge(
                        id=e.id, source=virtual_id, source_port=e.source_port,
                        target=e.target, target_port=e.target_port
                    ))
                else:
                    sub_edges.append(e)

            sub_nodes = [n.model_copy(update={"parent_id": None}) for n in child_nodes]

            order = self._topological_sort(sub_nodes, sub_edges)
            for child_id in order:
                child_def = self.nodes_by_id[child_id]
                child_inputs = self._get_node_inputs(child_id, sub_edges)

                node_logger._set_context(child_id, child_def.type, self._log_handler)
                try:
                    result = self.executors[child_def.type](child_def.params or {}, **child_inputs)
                    self.node_outputs[child_id] = result
                finally:
                    node_logger._clear_context()

            if exit_node_id in self.node_outputs:
                exit_output = self.node_outputs[exit_node_id]
                for child_port, loop_port in feedback_map.items():
                    if child_port in exit_output:
                        current_data[loop_port] = exit_output[child_port]

            self.node_outputs.pop(virtual_id, None)

        return current_data

    # ------------------------------------------------------------------
    # ComfyUI style: loop_start + loop_end pair
    # ------------------------------------------------------------------

    def _find_loop_body(self, start_id: str, end_id: str) -> Set[str]:
        """Find all nodes between loop_start and loop_end via BFS on forward edges."""
        forward_edges = [e for e in self.workflow.edges if not e.is_back_edge]
        adj: Dict[str, List[str]] = {}
        for e in forward_edges:
            adj.setdefault(e.source, []).append(e.target)

        visited: Set[str] = set()
        queue = [start_id]
        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            # Don't traverse past end_id (but include it)
            if nid == end_id:
                continue
            for neighbor in adj.get(nid, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        return visited

    def _execute_comfyui_loop(self, start_node: WorkflowNode) -> Set[str]:
        """Execute a LoopStart+LoopEnd pair. Returns set of node IDs already executed."""
        pair_id = start_node.id

        # Find paired loop_end
        end_node = None
        for n in self.workflow.nodes:
            if n.type == "loop_end" and n.params.get("pair_id") == pair_id:
                end_node = n
                break
        if not end_node:
            raise ValueError(f"LoopStart '{pair_id}' has no paired LoopEnd (set pair_id param)")

        iterations = _clamp_iterations(start_node.params.get("iterations", 10))

        # Find loop body: all nodes from start to end
        body_ids = self._find_loop_body(start_node.id, end_node.id)
        body_nodes = [self.nodes_by_id[nid] for nid in body_ids if nid in self.nodes_by_id]
        forward_edges = [e for e in self.workflow.edges if not e.is_back_edge]
        body_edges = [e for e in forward_edges if e.source in body_ids and e.target in body_ids]
        body_order = self._topological_sort(body_nodes, body_edges)

        # Get initial inputs to loop_start from upstream
        initial_inputs = self._get_node_inputs(start_node.id, self.workflow.edges)

        # Build current_data: maps in_N → value
        current_data = {}
        for key, value in initial_inputs.items():
            if key.startswith("in_"):
                current_data[key] = value

        node_start_time = time.time()

        for i in range(iterations):
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  ComfyUI loop iteration {i + 1}/{iterations}")
                self._emit("log", level="INFO", node_id=start_node.id,
                           node_type="loop_start",
                           message=f"Iteration {i + 1}/{iterations}",
                           timestamp=time.time())

            # Set loop_start outputs: in_N → out_N
            start_outputs = {}
            for key, value in current_data.items():
                out_key = key.replace("in_", "out_", 1)
                start_outputs[out_key] = value
            self.node_outputs[start_node.id] = start_outputs

            # Execute body nodes in order (skip start, it's already set)
            for nid in body_order:
                if nid == start_node.id:
                    continue
                node_def = self.nodes_by_id[nid]

                node_logger._set_context(nid, node_def.type, self._log_handler)
                try:
                    # body_edges may already contain start→body edges; deduplicate
                    extra = [e for e in forward_edges
                             if e.source == start_node.id and e.target in body_ids
                             and e not in body_edges]
                    node_inputs = self._get_node_inputs(nid, body_edges + extra)
                    if nid == end_node.id:
                        # loop_end is a pass-through
                        result = self.executors[node_def.type](node_def.params or {}, **node_inputs)
                    else:
                        result = self.executors[node_def.type](node_def.params or {}, **node_inputs)
                    self.node_outputs[nid] = result
                finally:
                    node_logger._clear_context()

            # Feedback: loop_end outputs → loop_start inputs for next iteration
            if end_node.id in self.node_outputs:
                end_out = self.node_outputs[end_node.id]
                for key, value in end_out.items():
                    # out_N → in_N
                    in_key = key.replace("out_", "in_", 1)
                    if in_key in current_data or value is not None:
                        current_data[in_key] = value

        # Record timing for the loop_start node
        duration = (time.time() - node_start_time) * 1000
        self._node_timings[start_node.id] = duration
        self._emit("node_complete", node_id=start_node.id,
                   outputs=self.node_outputs.get(start_node.id, {}), duration_ms=duration)

        # The end_node outputs are already set, so downstream nodes can read from it
        # Return body IDs so the main loop skips them
        return body_ids

    # ------------------------------------------------------------------
    # n8n style: loop_node with back-edge feedback
    # ------------------------------------------------------------------

    def _execute_n8n_loop(self, loop_def: WorkflowNode) -> Set[str]:
        """Execute an n8n-style loop node. Returns set of chain node IDs already executed."""
        iterations = _clamp_iterations(loop_def.params.get("iterations", 10))

        forward_edges = [e for e in self.workflow.edges if not e.is_back_edge]
        back_edges = [e for e in self.workflow.edges if e.is_back_edge]

        # Find processing chain: nodes reachable from loop_node via loop_* ports
        loop_output_targets: Set[str] = set()
        for e in forward_edges:
            if e.source == loop_def.id and e.source_port.startswith("loop_"):
                loop_output_targets.add(e.target)

        # BFS to find all chain nodes
        chain_ids: Set[str] = set()
        queue = list(loop_output_targets)
        while queue:
            nid = queue.pop(0)
            if nid in chain_ids or nid == loop_def.id:
                continue
            chain_ids.add(nid)
            for e in forward_edges:
                if e.source == nid and e.target != loop_def.id:
                    queue.append(e.target)

        chain_nodes = [self.nodes_by_id[nid] for nid in chain_ids if nid in self.nodes_by_id]
        chain_edges = [e for e in forward_edges if e.source in chain_ids and e.target in chain_ids]
        chain_order = self._topological_sort(chain_nodes, chain_edges)

        # Get initial inputs
        initial_inputs = self._get_node_inputs(loop_def.id, forward_edges)

        # Build current_data: init_N → slot N value
        current_data: Dict[str, Any] = {}
        for key, value in initial_inputs.items():
            if key.startswith("init_"):
                slot = key[len("init_"):]  # "1", "2", "3"
                current_data[slot] = value

        node_start_time = time.time()

        for i in range(iterations):
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  n8n loop iteration {i + 1}/{iterations}")
                self._emit("log", level="INFO", node_id=loop_def.id,
                           node_type="loop_node",
                           message=f"Iteration {i + 1}/{iterations}",
                           timestamp=time.time())

            # Set loop_* outputs
            loop_outputs: Dict[str, Any] = {}
            for slot, value in current_data.items():
                loop_outputs[f"loop_{slot}"] = value
            # Also set done_* (will be overwritten after final iteration, but needed for topology)
            for slot, value in current_data.items():
                loop_outputs[f"done_{slot}"] = value
            self.node_outputs[loop_def.id] = loop_outputs

            # Execute chain nodes
            edges_for_chain = chain_edges + [
                e for e in forward_edges
                if e.source == loop_def.id and e.target in chain_ids
            ]
            for nid in chain_order:
                node_def = self.nodes_by_id[nid]
                node_logger._set_context(nid, node_def.type, self._log_handler)
                try:
                    node_inputs = self._get_node_inputs(nid, edges_for_chain)
                    result = self.executors[node_def.type](node_def.params or {}, **node_inputs)
                    self.node_outputs[nid] = result
                finally:
                    node_logger._clear_context()

            # Read feedback from back-edges
            for be in back_edges:
                if be.target == loop_def.id and be.target_port.startswith("feedback_"):
                    slot = be.target_port[len("feedback_"):]  # "1", "2", "3"
                    if be.source in self.node_outputs:
                        src_out = self.node_outputs[be.source]
                        if be.source_port in src_out:
                            current_data[slot] = src_out[be.source_port]

        # After all iterations, set done_* outputs for downstream
        done_outputs: Dict[str, Any] = {}
        for slot, value in current_data.items():
            done_outputs[f"loop_{slot}"] = value
            done_outputs[f"done_{slot}"] = value
        self.node_outputs[loop_def.id] = done_outputs

        # Record timing
        duration = (time.time() - node_start_time) * 1000
        self._node_timings[loop_def.id] = duration
        self._emit("node_complete", node_id=loop_def.id,
                   outputs=done_outputs, duration_ms=duration)

        return chain_ids

    # ------------------------------------------------------------------
    # Main execution loop
    # ------------------------------------------------------------------

    def execute(self) -> Dict[str, Dict[str, Any]]:
        """Execute the workflow. Returns dict of node_id -> outputs."""
        # Top-level nodes only (no parent_id)
        top_nodes = [n for n in self.workflow.nodes if n.parent_id is None]
        top_ids = {n.id for n in top_nodes}
        top_edges = [
            e for e in self.workflow.edges
            if e.source in top_ids and e.target in top_ids
        ]

        order = self._topological_sort(top_nodes, top_edges)
        total = len(order)
        self._emit("start", total_nodes=total)
        print(f"Executing {total} top-level nodes: {order}")

        start_time = time.time()
        already_executed: Set[str] = set()

        for idx, node_id in enumerate(order):
            node_def = self.nodes_by_id[node_id]

            # Skip nodes already executed by loop handlers
            if node_id in already_executed or node_id in self.node_outputs:
                continue

            node_start = time.time()
            self._emit("node_start", node_id=node_id, node_label=node_def.type)
            print(f"[{idx + 1}/{total}] Executing {node_def.type} ({node_id})")

            inputs = self._get_node_inputs(node_id, self.workflow.edges)
            params = node_def.params or {}

            # Breakpoints
            if node_id in self.breakpoints:
                self._emit(
                    "breakpoint",
                    node_id=node_id,
                    node_type=node_def.type,
                    inputs=self._summarize_data(inputs),
                )
                self._emit(
                    "log",
                    level="WARN",
                    node_id=node_id,
                    node_type=node_def.type,
                    message=f"Breakpoint hit - inspecting node inputs",
                    timestamp=time.time(),
                )
                print(f"  BREAKPOINT: {node_def.type} ({node_id})")

            # Muted nodes
            if node_def.muted:
                self.node_outputs[node_id] = inputs
                duration = (time.time() - node_start) * 1000
                self._node_timings[node_id] = duration
                self._emit("node_complete", node_id=node_id,
                           outputs=inputs, duration_ms=duration)
                self._emit("log", level="INFO", node_id=node_id,
                           node_type=node_def.type,
                           message="Muted - passing inputs through",
                           timestamp=time.time())
                print(f"  Muted (skipped)")
                continue

            try:
                if node_def.type == "loop_group":
                    # Legacy container-based loop
                    result = self._execute_loop_group(node_def, inputs)
                    self.node_outputs[node_id] = result
                    duration = (time.time() - node_start) * 1000
                    self._node_timings[node_id] = duration
                    self._emit("node_complete", node_id=node_id,
                               outputs=result, duration_ms=duration)
                    print(f"  Done ({duration:.1f}ms)")

                elif node_def.type == "loop_start":
                    # ComfyUI style: execute entire loop_start→loop_end pair
                    body_ids = self._execute_comfyui_loop(node_def)
                    already_executed.update(body_ids)
                    print(f"  ComfyUI loop done")
                    continue

                elif node_def.type == "loop_node":
                    # n8n style: execute loop_node with back-edge chain
                    chain_ids = self._execute_n8n_loop(node_def)
                    already_executed.update(chain_ids)
                    print(f"  n8n loop done")
                    continue

                else:
                    # Check node type is available before executing
                    if node_def.type not in self.executors:
                        raise NodeUnavailableError(
                            node_id=node_id,
                            node_type=node_def.type,
                            reason="inactive or not installed",
                        )
                    # Normal node execution
                    node_logger._set_context(node_id, node_def.type, self._log_handler)
                    try:
                        result = self.executors[node_def.type](params, **inputs)
                    finally:
                        node_logger._clear_context()

                    self.node_outputs[node_id] = result
                    duration = (time.time() - node_start) * 1000
                    self._node_timings[node_id] = duration
                    self._emit("node_complete", node_id=node_id,
                               outputs=result, duration_ms=duration)
                    print(f"  Done ({duration:.1f}ms)")

            except Exception as exc:
                duration = (time.time() - node_start) * 1000
                self._node_timings[node_id] = duration
                tb = traceback.format_exc()
                self._emit("node_error", node_id=node_id,
                           error=str(exc), stack_trace=tb, duration_ms=duration)
                print(f"  ERROR: {exc}")
                raise

        total_ms = (time.time() - start_time) * 1000

        # Profiler summary
        profiler_data = {
            node_id: {
                "node_type": self.nodes_by_id[node_id].type,
                "duration_ms": round(dur, 2),
            }
            for node_id, dur in self._node_timings.items()
        }
        self._emit(
            "profiler_summary",
            total_ms=round(total_ms, 2),
            node_timings=profiler_data,
            slowest_node=max(self._node_timings, key=self._node_timings.get)
            if self._node_timings
            else None,
        )

        self._emit("complete", total_ms=total_ms)
        print(f"Workflow complete ({total_ms:.1f}ms)")

        return self.node_outputs

    def _summarize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a JSON-safe summary of node input/output data for breakpoint events."""
        summary: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, np.ndarray):
                summary[key] = {
                    "_type": "array",
                    "shape": list(value.shape),
                    "dtype": str(value.dtype),
                    "length": int(value.shape[0]) if value.ndim >= 1 else 1,
                }
            elif isinstance(value, dict) and value.get("_type") == "array":
                summary[key] = value
            elif isinstance(value, (int, float, str, bool)):
                summary[key] = value
            elif callable(value):
                name = getattr(value, '__name__', type(value).__name__)
                summary[key] = {"_type": "function", "name": name}
            elif isinstance(value, (list, tuple)):
                summary[key] = {
                    "_type": "list",
                    "length": len(value),
                }
            else:
                summary[key] = {"_type": type(value).__name__}
        return summary
