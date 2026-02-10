"""Workflow validator for PipeStudio.

Validates a WorkflowDefinition and returns a list of issues, each a dict:
    {"level": "error"|"warning"|"info", "node_id": str|None, "message": str}
"""
from typing import Any, Dict, List, Set

from pipestudio.models import WorkflowDefinition, WorkflowNode, WorkflowEdge
from pipestudio.plugin_api import _NODE_REGISTRY

# Node types handled by the executor (not in _NODE_REGISTRY but still valid)
_EXECUTOR_TYPES = {"loop_group"}


def validate_workflow(wf: WorkflowDefinition) -> List[Dict[str, Any]]:
    """Validate a workflow definition and return a list of issues.

    Checks performed:
    1. Unknown node type (error)
    2. Missing required input connections (error)
    3. Cycle detection via DFS on top-level nodes (error) — excludes back-edges
    4. Isolated nodes with no edges (warning, skip if single node)
    5. Muted nodes (info note)
    6. LoopStart↔LoopEnd pairing (error if unpaired)
    7. loop_node without feedback back-edges (warning)
    """
    issues: List[Dict[str, Any]] = []

    if not wf.nodes:
        return issues

    # Build lookup sets for quick edge queries
    incoming_ports: Dict[str, Set[str]] = {n.id: set() for n in wf.nodes}
    has_edge: Dict[str, bool] = {n.id: False for n in wf.nodes}

    for edge in wf.edges:
        if edge.target in incoming_ports:
            incoming_ports[edge.target].add(edge.target_port)
        if edge.source in has_edge:
            has_edge[edge.source] = True
        if edge.target in has_edge:
            has_edge[edge.target] = True

    # --- Check 1: Unknown node type ---
    for n in wf.nodes:
        if n.type not in _NODE_REGISTRY and n.type not in _EXECUTOR_TYPES:
            issues.append({
                "level": "error",
                "node_id": n.id,
                "message": f"Unknown node type '{n.type}'",
            })

    # --- Check 2: Missing required input connections ---
    # Ports that receive data from loop feedback (not from edges)
    _feedback_ports = {"loop_end": {"in_1", "in_2", "in_3"},
                       "loop_node": {"feedback_1", "feedback_2", "feedback_3"}}

    for n in wf.nodes:
        spec = _NODE_REGISTRY.get(n.type)
        if spec is None:
            continue
        skip_ports = _feedback_ports.get(n.type, set())
        for port in spec.get("inputs", []):
            if port.get("required", True) and port.get("default") is None:
                port_name = port["name"]
                if port_name in skip_ports:
                    continue  # Feedback ports get data from executor, not edges
                if port_name not in incoming_ports.get(n.id, set()):
                    issues.append({
                        "level": "error",
                        "node_id": n.id,
                        "message": (
                            f"Required input port '{port_name}' has no incoming connection"
                        ),
                    })

    # --- Check 3: Cycle detection (DFS on top-level nodes, excluding back-edges) ---
    top_level_ids = {n.id for n in wf.nodes if n.parent_id is None}
    adjacency: Dict[str, List[str]] = {nid: [] for nid in top_level_ids}
    for edge in wf.edges:
        if edge.is_back_edge:
            continue  # Back-edges are intentional loop feedback, not cycles
        if edge.source in top_level_ids and edge.target in top_level_ids:
            adjacency[edge.source].append(edge.target)

    if _has_cycle(adjacency, top_level_ids):
        issues.append({
            "level": "error",
            "node_id": None,
            "message": "Workflow contains a cycle",
        })

    # --- Check 4: Isolated nodes ---
    if len(wf.nodes) > 1:
        _skip_isolated = {"loop_group", "loop_start", "loop_end", "loop_node"}
        for n in wf.nodes:
            if n.type in _skip_isolated:
                continue
            if not has_edge.get(n.id, False):
                issues.append({
                    "level": "warning",
                    "node_id": n.id,
                    "message": f"Node '{n.id}' is isolated (no connections)",
                })

    # --- Check 5: Muted nodes ---
    for n in wf.nodes:
        if n.muted:
            issues.append({
                "level": "info",
                "node_id": n.id,
                "message": f"Node '{n.id}' is muted and will be skipped during execution",
            })

    # --- Check 6: LoopStart↔LoopEnd pairing ---
    start_ids = {n.id for n in wf.nodes if n.type == "loop_start"}
    end_nodes = [n for n in wf.nodes if n.type == "loop_end"]
    paired_starts: Set[str] = set()

    for n in end_nodes:
        pid = n.params.get("pair_id")
        if not pid or pid not in start_ids:
            issues.append({
                "level": "error",
                "node_id": n.id,
                "message": f"LoopEnd pair_id '{pid}' does not match any LoopStart",
            })
        else:
            paired_starts.add(pid)

    for sid in start_ids:
        if sid not in paired_starts:
            issues.append({
                "level": "error",
                "node_id": sid,
                "message": "LoopStart has no matching LoopEnd (set pair_id on LoopEnd)",
            })

    # --- Check 7: loop_node without feedback ---
    back_edge_targets = {e.target for e in wf.edges if e.is_back_edge}
    for n in wf.nodes:
        if n.type == "loop_node" and n.id not in back_edge_targets:
            issues.append({
                "level": "warning",
                "node_id": n.id,
                "message": "Loop node has no feedback back-edges (loop will repeat same data)",
            })

    return issues


def _has_cycle(adjacency: Dict[str, List[str]], all_nodes: Set[str]) -> bool:
    """Detect cycles using DFS with coloring."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in all_nodes}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in adjacency.get(node, []):
            if color.get(neighbor) == GRAY:
                return True
            if color.get(neighbor) == WHITE:
                if dfs(neighbor):
                    return True
        color[node] = BLACK
        return False

    for node in all_nodes:
        if color[node] == WHITE:
            if dfs(node):
                return True
    return False
