"""Tests for workflow validator (Phase 5.1)."""
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
    """An empty workflow should produce no issues."""
    _load()
    issues = validate_workflow(_wf())
    assert issues == []


def test_missing_required_input_connection():
    """A node whose required input port has no incoming edge => error."""
    _load()
    # bubble_pass has a required 'array' input
    wf = _wf(nodes=[_node("n1", "bubble_pass")])
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any("array" in i["message"] and i["node_id"] == "n1" for i in errors)


def test_disconnected_isolated_node_warning():
    """A node with zero edges when other nodes exist => warning."""
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "generate_array"),
            _node("n2", "bubble_pass"),
            _node("n3", "measure_disorder"),
        ],
        edges=[
            _edge("n1", "array", "n2", "array"),
        ],
    )
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    # n3 is isolated (no edges connect to/from it)
    assert any(i["node_id"] == "n3" for i in warnings)


def test_single_node_not_isolated_warning():
    """A single node in the workflow should NOT produce an isolated warning."""
    _load()
    wf = _wf(nodes=[_node("n1", "generate_array")])
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert not any("isolat" in i["message"].lower() for i in warnings)


def test_cycle_detection_error():
    """A cycle in the graph should produce an error."""
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "bubble_pass"),
            _node("n2", "bubble_pass"),
        ],
        edges=[
            _edge("n1", "array", "n2", "array"),
            _edge("n2", "array", "n1", "array"),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any("cycle" in i["message"].lower() for i in errors)


def test_unknown_node_type_error():
    """A node with an unregistered type => error."""
    _load()
    wf = _wf(nodes=[_node("n1", "totally_fake_node")])
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any(
        i["node_id"] == "n1" and "unknown" in i["message"].lower()
        for i in errors
    )


def test_muted_node_info():
    """A muted node should produce an info-level note, not an error."""
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "generate_array"),
            _node("n2", "bubble_pass", muted=True),
        ],
        edges=[
            _edge("n1", "array", "n2", "array"),
        ],
    )
    issues = validate_workflow(wf)
    infos = [i for i in issues if i["level"] == "info"]
    assert any(i["node_id"] == "n2" for i in infos)
    # Muted node should NOT produce an error just because it's muted
    errors = [i for i in issues if i["level"] == "error" and i["node_id"] == "n2"]
    assert len(errors) == 0


def test_valid_workflow_no_errors():
    """A fully-connected valid workflow should produce no errors or warnings."""
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "generate_array"),
            _node("n2", "bubble_pass"),
            _node("n3", "measure_disorder"),
        ],
        edges=[
            _edge("n1", "array", "n2", "array"),
            _edge("n2", "array", "n3", "array"),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    assert errors == []
    assert warnings == []


def test_loop_group_not_flagged_as_unknown():
    """loop_group is in the registry and should not be flagged as unknown."""
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "generate_array"),
            _node("lg", "loop_group"),
        ],
        edges=[
            _edge("n1", "array", "lg", "array"),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert not any(
        i["node_id"] == "lg" and "unknown" in i["message"].lower()
        for i in errors
    )


def test_loop_group_not_flagged_as_isolated():
    """loop_group nodes should be exempt from isolated-node warnings."""
    _load()
    wf = _wf(
        nodes=[
            _node("n1", "generate_array"),
            _node("n2", "bubble_pass"),
            _node("lg", "loop_group"),
        ],
        edges=[
            _edge("n1", "array", "n2", "array"),
        ],
    )
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert not any(i["node_id"] == "lg" for i in warnings)


def test_child_node_inside_loop_group():
    """Nodes with parent_id (inside a loop group) should still be validated."""
    _load()
    wf = _wf(
        nodes=[
            _node("lg", "loop_group"),
            _node("child1", "bubble_pass", parent_id="lg"),
        ],
        edges=[],
    )
    issues = validate_workflow(wf)
    # child1 has required input 'array' with no edge -> error
    errors = [i for i in issues if i["level"] == "error" and i["node_id"] == "child1"]
    assert any("array" in i["message"] for i in errors)


def test_issue_structure():
    """Each issue dict must have 'level', 'node_id', 'message' keys."""
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
    """Properly paired LoopStart+LoopEnd should produce no pairing errors."""
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "generate_array"),
            _node("ls", "loop_start"),
            _node("bp", "bubble_pass"),
            _node("le", "loop_end"),
        ],
        edges=[
            _edge("gen", "array", "ls", "in_1"),
            _edge("ls", "out_1", "bp", "array"),
            _edge("bp", "array", "le", "in_1"),
        ],
    )
    # Set pair_id on the loop_end node
    for n in wf.nodes:
        if n.id == "le":
            n.params = {"pair_id": "ls"}
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    # No pairing errors
    assert not any("pair" in i["message"].lower() for i in errors)


def test_comfyui_loop_missing_pair():
    """LoopEnd without matching LoopStart pair_id should error."""
    _load()
    wf = _wf(
        nodes=[
            _node("le", "loop_end"),
        ],
        edges=[],
    )
    for n in wf.nodes:
        if n.id == "le":
            n.params = {"pair_id": "nonexistent"}
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any(
        i["node_id"] == "le" and "pair" in i["message"].lower()
        for i in errors
    )


def test_comfyui_loop_start_without_end():
    """LoopStart without any matching LoopEnd should error."""
    _load()
    wf = _wf(
        nodes=[
            _node("ls", "loop_start"),
        ],
        edges=[],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any(
        i["node_id"] == "ls" and "loopend" in i["message"].lower().replace(" ", "")
        for i in errors
    )


def test_loop_end_feedback_ports_not_flagged():
    """LoopEnd in_* ports should not produce 'missing connection' errors."""
    _load()
    wf = _wf(
        nodes=[
            _node("ls", "loop_start"),
            _node("le", "loop_end"),
        ],
        edges=[],
    )
    for n in wf.nodes:
        if n.id == "le":
            n.params = {"pair_id": "ls"}
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    # loop_end's in_* ports are in _feedback_ports, so no "required input" errors for them
    assert not any(
        i["node_id"] == "le" and "in_" in i["message"]
        for i in errors
    )


# ------------------------------------------------------------------
# n8n style loop validation
# ------------------------------------------------------------------

def test_n8n_back_edge_not_cycle():
    """A back-edge from processing node to loop_node:feedback_* should NOT be flagged as cycle."""
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "generate_array"),
            _node("loop", "loop_node"),
            _node("bp", "bubble_pass"),
        ],
        edges=[
            _edge("gen", "array", "loop", "init_1"),
            _edge("loop", "loop_1", "bp", "array"),
            # Back-edge: bp → loop:feedback_1
            _edge("bp", "array", "loop", "feedback_1", is_back_edge=True),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert not any("cycle" in i["message"].lower() for i in errors)


def test_n8n_real_cycle_still_detected():
    """A real cycle (non-back-edge) should still be flagged even with loop nodes."""
    _load()
    wf = _wf(
        nodes=[
            _node("bp1", "bubble_pass"),
            _node("bp2", "bubble_pass"),
        ],
        edges=[
            _edge("bp1", "array", "bp2", "array"),
            _edge("bp2", "array", "bp1", "array"),  # Real cycle, NOT a back-edge
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert any("cycle" in i["message"].lower() for i in errors)


def test_n8n_loop_without_feedback_warns():
    """loop_node with no back-edges should produce a warning."""
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "generate_array"),
            _node("loop", "loop_node"),
            _node("bp", "bubble_pass"),
        ],
        edges=[
            _edge("gen", "array", "loop", "init_1"),
            _edge("loop", "loop_1", "bp", "array"),
            # No back-edge!
        ],
    )
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert any(
        i["node_id"] == "loop" and "feedback" in i["message"].lower()
        for i in warnings
    )


def test_n8n_loop_with_feedback_no_warning():
    """loop_node with a proper back-edge should NOT produce feedback warning."""
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "generate_array"),
            _node("loop", "loop_node"),
            _node("bp", "bubble_pass"),
        ],
        edges=[
            _edge("gen", "array", "loop", "init_1"),
            _edge("loop", "loop_1", "bp", "array"),
            _edge("bp", "array", "loop", "feedback_1", is_back_edge=True),
        ],
    )
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    assert not any(
        i["node_id"] == "loop" and "feedback" in i["message"].lower()
        for i in warnings
    )


def test_n8n_feedback_ports_not_flagged_required():
    """loop_node feedback_* ports should not produce 'missing connection' errors."""
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "generate_array"),
            _node("loop", "loop_node"),
        ],
        edges=[
            _edge("gen", "array", "loop", "init_1"),
        ],
    )
    issues = validate_workflow(wf)
    errors = [i for i in issues if i["level"] == "error"]
    assert not any(
        i["node_id"] == "loop" and "feedback_" in i["message"]
        for i in errors
    )


def test_loop_types_not_flagged_as_isolated():
    """All new loop types should be exempt from isolated-node warnings."""
    _load()
    wf = _wf(
        nodes=[
            _node("gen", "generate_array"),
            _node("bp", "bubble_pass"),
            _node("ls", "loop_start"),
            _node("le", "loop_end"),
            _node("ln", "loop_node"),
        ],
        edges=[
            _edge("gen", "array", "bp", "array"),
        ],
    )
    # Set pair_id for loop_end
    for n in wf.nodes:
        if n.id == "le":
            n.params = {"pair_id": "ls"}
    issues = validate_workflow(wf)
    warnings = [i for i in issues if i["level"] == "warning"]
    # None of the loop nodes should be flagged as isolated
    isolated_ids = {i["node_id"] for i in warnings if "isolated" in i["message"].lower()}
    assert "ls" not in isolated_ids
    assert "le" not in isolated_ids
    assert "ln" not in isolated_ids
