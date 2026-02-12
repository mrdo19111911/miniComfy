"""Tests for multi-edge stacking: multiple edges into same input port."""
import numpy as np
import pytest
from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS, register_node
from pipestudio.executor import WorkflowExecutor
from pipestudio.models import WorkflowDefinition, WorkflowNode, WorkflowEdge

# --- Inline test plugins ---

SOURCE_A_INFO = {
    "type": "test_source_a",
    "label": "Source A",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "ARRAY", "required": True}],
}

SOURCE_B_INFO = {
    "type": "test_source_b",
    "label": "Source B",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "ARRAY", "required": True}],
}

STACKER_INFO = {
    "type": "test_stacker",
    "label": "Stacker",
    "category": "TEST",
    "ports_in": [{"name": "items", "type": "ARRAY", "required": True}],
    "ports_out": [{"name": "result", "type": "ARRAY", "required": True}],
}


def source_a_exec(params, **inputs):
    return {"out": np.array([1.0, 2.0, 3.0])}


def source_b_exec(params, **inputs):
    return {"out": np.array([4.0, 5.0, 6.0])}


def stacker_exec(params, **inputs):
    items = inputs.get("items")
    if isinstance(items, list):
        return {"result": np.array(items, dtype=object)}
    return {"result": items}


@pytest.fixture(autouse=True)
def _register():
    register_node(SOURCE_A_INFO, source_a_exec)
    register_node(SOURCE_B_INFO, source_b_exec)
    register_node(STACKER_INFO, stacker_exec)
    yield
    for t in ["test_source_a", "test_source_b", "test_stacker"]:
        _NODE_REGISTRY.pop(t, None)
        _EXECUTORS.pop(t, None)


def test_multi_edge_stacks_into_list():
    """Two edges into same input port should produce a list of values."""
    wf = WorkflowDefinition(
        nodes=[
            WorkflowNode(id="a", type="test_source_a", params={}),
            WorkflowNode(id="b", type="test_source_b", params={}),
            WorkflowNode(id="s", type="test_stacker", params={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", source_port="out", target="s", target_port="items"),
            WorkflowEdge(id="e2", source="b", source_port="out", target="s", target_port="items"),
        ],
    )

    executor = WorkflowExecutor(wf)
    results = executor.execute()

    stacker_result = results["s"]["result"]
    # Should be a list (or object array) of two numpy arrays
    assert isinstance(stacker_result, (list, np.ndarray))
    if isinstance(stacker_result, np.ndarray):
        assert stacker_result.dtype == object
        assert len(stacker_result) == 2
    else:
        assert len(stacker_result) == 2


def test_single_edge_no_wrapping():
    """Single edge into a port should NOT produce a list — just the value."""
    wf = WorkflowDefinition(
        nodes=[
            WorkflowNode(id="a", type="test_source_a", params={}),
            WorkflowNode(id="s", type="test_stacker", params={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", source_port="out", target="s", target_port="items"),
        ],
    )

    executor = WorkflowExecutor(wf)
    results = executor.execute()

    stacker_input = results["s"]["result"]
    # Single edge → value passed directly, not wrapped in list
    assert isinstance(stacker_input, np.ndarray)
    assert len(stacker_input) == 3
