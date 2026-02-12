"""Tests for workflow validator."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS
from pipestudio.plugin_loader import load_plugins
from pipestudio.models import WorkflowNode, WorkflowEdge, WorkflowDefinition
from pipestudio.validator import validate_workflow

PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "plugins")


def _load():
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    load_plugins(PLUGINS_DIR)


# --- Helper builders ---

def _node(id, type, muted=False, parent_id=None):
    return WorkflowNode(id=id, type=type, muted=muted, parent_id=parent_id)


def _edge(source, source_port, target, target_port, is_back_edge=False):
    return WorkflowEdge(
        id=f"{source}-{target}-{target_port}",
        source=source,
        source_port=source_port,
        target=target,
        target_port=target_port,
        is_back_edge=is_back_edge,
    )


def _wf(nodes=None, edges=None):
    return WorkflowDefinition(nodes=nodes or [], edges=edges or [])


# --- Tests ---

def test_empty_workflow_no_issues():
    _load()
    issues = validate_workflow(_wf())
    assert issues == []


def test_missing_required_input_connection():
    _load()
    wf = _wf(nodes=[_node("n1", "tsp_greedy")])
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any("dist_matrix" in i["message"] and i["node_id"] == "n1" for i in errors)


def test_disconnected_isolated_node_warning():
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "tsp_generate_points"),
            _node("n2", "tsp_distance_matrix"),
            _node("n3", "tsp_greedy"),
        ],
        edges=[_edge("n1", "points", "n2", "points")],
    )
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert any(i["node_id"] == "n3" for i in warnings)


def test_single_node_not_isolated_warning():
    _load()
    wf = _wf(nodes=[_node("n1", "tsp_generate_points")])
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert not any("isolat" in i["message"].lower() for i in warnings)


def test_cycle_detection_error():
    _load()
    wf = _wf(
        nodes=[_node("n1", "tsp_greedy"), _node("n2", "tsp_greedy")],
        edges=[
            _edge("n1", "tour", "n2", "dist_matrix"),
            _edge("n2", "tour", "n1", "dist_matrix"),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any("cycle" in i["message"].lower() for i in errors)


def test_unknown_node_type_error():
    _load()
    wf = _wf(nodes=[_node("n1", "totally_fake_node")])
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any(i["node_id"] == "n1" and "unknown" in i["message"].lower() for i in errors)


def test_muted_node_info():
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "tsp_generate_points"),
            _node("n2", "tsp_distance_matrix", muted=True),
        ],
        edges=[_edge("n1", "points", "n2", "points")],
    )
    issues = validate_workflow(wf)
    infos = [i for i in issues if i["level"] == "info"]
    assert any(i["node_id"] == "n2" for i in infos)
    errors = [i for i in issues if i["level"] == "error" and i["node_id"] == "n2"]
    assert len(errors) == 0


def test_valid_workflow_no_errors():
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "tsp_generate_points"),
            _node("n2", "tsp_distance_matrix"),
            _node("n3", "tsp_greedy"),
        ],
        edges=[
            _edge("n1", "points", "n2", "points"),
            _edge("n2", "dist_matrix", "n3", "dist_matrix"),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    assert errors == []
    assert warnings == []


def test_loop_group_not_flagged_as_unknown():
    _load()
    wf = _wf(
        nodes=[_node("n1", "tsp_generate_points"), _node("lg", "loop_group")],
        edges=[_edge("n1", "points", "lg", "slot_1")],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert not any(i["node_id"] == "lg" and "unknown" in i["message"].lower() for i in errors)


def test_loop_group_not_flagged_as_isolated():
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "tsp_generate_points"),
            _node("n2", "tsp_distance_matrix"),
            _node("lg", "loop_group"),
        ],
        edges=[_edge("n1", "points", "n2", "points")],
    )
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert not any(i["node_id"] == "lg" for i in warnings)


def test_child_node_inside_loop_group():
    _load()
    wf = _wf(
        nodes=[_node("lg", "loop_group"), _node("child1", "tsp_greedy", parent_id="lg")],
        edges=[],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error" and i["node_id"] == "child1"]
    assert any("dist_matrix" in i["message"] for i in errors)


def test_issue_structure():
    _load()
    wf = _wf(nodes=[_node("n1", "totally_fake_node")])
    issues = validate_workflow(wf)
    assert len(issues) > 0
    for issue in issues:
        assert "level" in issue
        assert "node_id" in issue
        assert "message" in issue
        assert issue["level"] in ("error", "warning", "info")


# ------------------------------------------------------------------
# ComfyUI style loop validation
# ------------------------------------------------------------------

def test_comfyui_loop_valid_pair():
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "tsp_generate_points"),
            _node("ls", "loop_start"),
            _node("dm", "tsp_distance_matrix"),
            _node("le", "loop_end"),
        ],
        edges=[
            _edge("gen", "points", "ls", "in_1"),
            _edge("ls", "out_1", "dm", "points"),
        ],
    )
    for n in wf.nodes:
        if n.id == "le":
            n.params = {"pair_id": "ls"}
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert not any("pair" in i["message"].lower() for i in errors)


def test_comfyui_loop_missing_pair():
    _load()
    wf = _wf(nodes=[_node("le", "loop_end")], edges=[])
    for n in wf.nodes:
        if n.id == "le":
            n.params = {"pair_id": "nonexistent"}
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any(i["node_id"] == "le" and "pair" in i["message"].lower() for i in errors)


def test_comfyui_loop_start_without_end():
    _load()
    wf = _wf(nodes=[_node("ls", "loop_start")], edges=[])
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any(
        i["node_id"] == "ls" and "loopend" in i["message"].lower().replace(" ", "")
        for i in errors
    )


def test_loop_end_feedback_ports_not_flagged():
    _load()
    wf = _wf(nodes=[_node("ls", "loop_start"), _node("le", "loop_end")], edges=[])
    for n in wf.nodes:
        if n.id == "le":
            n.params = {"pair_id": "ls"}
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert not any(i["node_id"] == "le" and "in_" in i["message"] for i in errors)


# ------------------------------------------------------------------
# n8n style loop validation
# ------------------------------------------------------------------

def test_n8n_back_edge_not_cycle():
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "tsp_generate_points"),
            _node("loop", "loop_node"),
            _node("dm", "tsp_distance_matrix"),
        ],
        edges=[
            _edge("gen", "points", "loop", "init_1"),
            _edge("loop", "loop_1", "dm", "points"),
            _edge("dm", "dist_matrix", "loop", "feedback_1", is_back_edge=True),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert not any("cycle" in i["message"].lower() for i in errors)


def test_n8n_real_cycle_still_detected():
    _load()
    wf = _wf(
        nodes=[_node("n1", "tsp_greedy"), _node("n2", "tsp_greedy")],
        edges=[
            _edge("n1", "tour", "n2", "dist_matrix"),
            _edge("n2", "tour", "n1", "dist_matrix"),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any("cycle" in i["message"].lower() for i in errors)


def test_n8n_loop_without_feedback_warns():
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "tsp_generate_points"),
            _node("loop", "loop_node"),
            _node("dm", "tsp_distance_matrix"),
        ],
        edges=[
            _edge("gen", "points", "loop", "init_1"),
            _edge("loop", "loop_1", "dm", "points"),
        ],
    )
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert any(i["node_id"] == "loop" and "feedback" in i["message"].lower() for i in warnings)


def test_n8n_loop_with_feedback_no_warning():
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "tsp_generate_points"),
            _node("loop", "loop_node"),
            _node("dm", "tsp_distance_matrix"),
        ],
        edges=[
            _edge("gen", "points", "loop", "init_1"),
            _edge("loop", "loop_1", "dm", "points"),
            _edge("dm", "dist_matrix", "loop", "feedback_1", is_back_edge=True),
        ],
    )
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert not any(i["node_id"] == "loop" and "feedback" in i["message"].lower() for i in warnings)


def test_n8n_feedback_ports_not_flagged_required():
    _load()
    wf = _wf(
        nodes=[_node("gen", "tsp_generate_points"), _node("loop", "loop_node")],
        edges=[_edge("gen", "points", "loop", "init_1")],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert not any(i["node_id"] == "loop" and "feedback_" in i["message"] for i in errors)


def test_loop_types_not_flagged_as_isolated():
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "tsp_generate_points"),
            _node("dm", "tsp_distance_matrix"),
            _node("ls", "loop_start"),
            _node("le", "loop_end"),
            _node("ln", "loop_node"),
        ],
        edges=[_edge("gen", "points", "dm", "points")],
    )
    for n in wf.nodes:
        if n.id == "le":
            n.params = {"pair_id": "ls"}
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    isolated_ids = {i["node_id"] for i in warnings if "isolated" in i["message"].lower()}
    assert "ls" not in isolated_ids
    assert "le" not in isolated_ids
    assert "ln" not in isolated_ids
