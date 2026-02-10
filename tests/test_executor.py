"""Tests for workflow executor."""
import sys
import os

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS
from pipestudio.plugin_loader import load_plugins
from pipestudio.models import WorkflowNode, WorkflowEdge, WorkflowDefinition
from pipestudio.executor import WorkflowExecutor

PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "plugins")


def _load():
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    load_plugins(PLUGINS_DIR)


def test_simple_workflow():
    """generate_array -> measure_disorder"""
    _load()
    wf = WorkflowDefinition(
        name="test",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 100}),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="array",
                         target="meas", target_port="array"),
        ],
    )
    executor = WorkflowExecutor(wf)
    results = executor.execute()
    assert "gen" in results
    assert "meas" in results
    assert "score" in results["meas"]
    assert 0.0 <= results["meas"]["score"] <= 1.0


def test_chain_workflow():
    """generate -> shuffle -> bubble -> measure"""
    _load()
    wf = WorkflowDefinition(
        name="test_chain",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 50}),
            WorkflowNode(id="shuf", type="shuffle_segment"),
            WorkflowNode(id="bp", type="bubble_pass"),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="array",
                         target="shuf", target_port="array"),
            WorkflowEdge(id="e2", source="shuf", source_port="array",
                         target="bp", target_port="array"),
            WorkflowEdge(id="e3", source="bp", source_port="array",
                         target="meas", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert len(results) == 4
    assert "score" in results["meas"]


def test_loop_group():
    """generate -> loop_group(bubble_pass) -> measure"""
    _load()
    wf = WorkflowDefinition(
        name="test_loop",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 50}),
            WorkflowNode(id="loop", type="loop_group", params={"iterations": 100}),
            WorkflowNode(id="bp", type="bubble_pass", parent_id="loop"),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="array",
                         target="loop", target_port="array"),
            WorkflowEdge(id="e2", source="loop", source_port="array",
                         target="meas", target_port="array"),
            WorkflowEdge(id="e3", source="loop", source_port="array",
                         target="bp", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    score = results["meas"]["score"]
    assert score > 0.9, f"Expected mostly sorted after 100 bubble passes, got {score}"


def test_empty_loop_group_passthrough():
    """Loop group with no children should pass data through."""
    _load()
    wf = WorkflowDefinition(
        name="test_empty_loop",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 10}),
            WorkflowNode(id="loop", type="loop_group", params={"iterations": 5}),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="array",
                         target="loop", target_port="array"),
            WorkflowEdge(id="e2", source="loop", source_port="array",
                         target="meas", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "meas" in results


def test_event_handler_called():
    """Event handler receives start, node_start, node_complete, complete."""
    _load()
    events = []

    def handler(event_type, data):
        events.append(event_type)

    wf = WorkflowDefinition(
        name="test_events",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 10}),
        ],
        edges=[],
    )
    WorkflowExecutor(wf, event_handler=handler).execute()
    assert "start" in events
    assert "node_start" in events
    assert "node_complete" in events
    assert "complete" in events


def test_logger_captures_entries():
    """Node logger entries are captured in executor._log_entries."""
    _load()
    wf = WorkflowDefinition(
        name="test_log",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 100}),
        ],
        edges=[],
    )
    executor = WorkflowExecutor(wf)
    executor.execute()
    assert len(executor._log_entries) > 0
    entry = executor._log_entries[0]
    assert "level" in entry
    assert "node_id" in entry
    assert "message" in entry


def test_muted_node_passes_through():
    """Muted node passes inputs through without executing."""
    _load()
    wf = WorkflowDefinition(
        name="test_muted",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 50}),
            WorkflowNode(id="shuf", type="shuffle_segment", muted=True),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="array",
                         target="shuf", target_port="array"),
            WorkflowEdge(id="e2", source="shuf", source_port="array",
                         target="meas", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    # Muted shuffle should pass array through unchanged
    assert "meas" in results
    # The array passed through muted node should be the same as generated
    gen_array = results["gen"]["array"]
    # The muted node output should have the same input key
    assert "array" in results["shuf"]
    muted_array = results["shuf"]["array"]
    assert np.array_equal(gen_array, muted_array)


# ------------------------------------------------------------------
# ComfyUI style loop (loop_start + loop_end pair)
# ------------------------------------------------------------------

def test_comfyui_loop_sorting():
    """loop_start + bubble_pass + loop_end => mostly sorted after 100 iters."""
    _load()
    wf = WorkflowDefinition(
        name="test_comfyui_sorting",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 50}),
            WorkflowNode(id="ls", type="loop_start", params={"iterations": 100}),
            WorkflowNode(id="bp", type="bubble_pass"),
            WorkflowNode(id="le", type="loop_end", params={"pair_id": "ls"}),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="array",
                         target="ls", target_port="in_1"),
            WorkflowEdge(id="e2", source="ls", source_port="out_1",
                         target="bp", target_port="array"),
            WorkflowEdge(id="e3", source="bp", source_port="array",
                         target="le", target_port="in_1"),
            WorkflowEdge(id="e4", source="le", source_port="out_1",
                         target="meas", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    score = results["meas"]["score"]
    assert score > 0.9, f"Expected mostly sorted after 100 bubble passes, got {score}"


def test_comfyui_loop_two_channels():
    """ComfyUI loop passing two data channels (like TSP: dist_matrix + tour)."""
    _load()
    wf = WorkflowDefinition(
        name="test_comfyui_2ch",
        nodes=[
            WorkflowNode(id="gen1", type="generate_array", params={"size": 30}),
            WorkflowNode(id="gen2", type="generate_array", params={"size": 30}),
            WorkflowNode(id="ls", type="loop_start", params={"iterations": 5}),
            WorkflowNode(id="bp", type="bubble_pass"),
            WorkflowNode(id="le", type="loop_end", params={"pair_id": "ls"}),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            # Channel 1: gen1 → ls:in_1 (static, not processed)
            WorkflowEdge(id="e1", source="gen1", source_port="array",
                         target="ls", target_port="in_1"),
            # Channel 2: gen2 → ls:in_2 (will be bubble-sorted)
            WorkflowEdge(id="e2", source="gen2", source_port="array",
                         target="ls", target_port="in_2"),
            # Only process channel 2 through bubble_pass
            WorkflowEdge(id="e3", source="ls", source_port="out_2",
                         target="bp", target_port="array"),
            WorkflowEdge(id="e4", source="bp", source_port="array",
                         target="le", target_port="in_2"),
            # Pass channel 1 through unchanged
            WorkflowEdge(id="e5", source="ls", source_port="out_1",
                         target="le", target_port="in_1"),
            # Measure the sorted channel
            WorkflowEdge(id="e6", source="le", source_port="out_2",
                         target="meas", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "meas" in results
    assert "score" in results["meas"]
    # Channel 1 should be untouched in le output
    assert "out_1" in results["le"]


# ------------------------------------------------------------------
# n8n style loop (loop_node with back-edge feedback)
# ------------------------------------------------------------------

def test_n8n_loop_sorting():
    """loop_node + bubble_pass with back-edge => mostly sorted after 100 iters."""
    _load()
    wf = WorkflowDefinition(
        name="test_n8n_sorting",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 50}),
            WorkflowNode(id="loop", type="loop_node", params={"iterations": 100}),
            WorkflowNode(id="bp", type="bubble_pass"),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            # gen → loop:init_1
            WorkflowEdge(id="e1", source="gen", source_port="array",
                         target="loop", target_port="init_1"),
            # loop:loop_1 → bp (forward)
            WorkflowEdge(id="e2", source="loop", source_port="loop_1",
                         target="bp", target_port="array"),
            # bp → loop:feedback_1 (back-edge)
            WorkflowEdge(id="e3", source="bp", source_port="array",
                         target="loop", target_port="feedback_1",
                         is_back_edge=True),
            # loop:done_1 → measure
            WorkflowEdge(id="e4", source="loop", source_port="done_1",
                         target="meas", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    score = results["meas"]["score"]
    assert score > 0.9, f"Expected mostly sorted after 100 bubble passes, got {score}"


def test_n8n_loop_two_channels():
    """n8n loop with two data channels, only one has feedback."""
    _load()
    wf = WorkflowDefinition(
        name="test_n8n_2ch",
        nodes=[
            WorkflowNode(id="gen1", type="generate_array", params={"size": 30}),
            WorkflowNode(id="gen2", type="generate_array", params={"size": 30}),
            WorkflowNode(id="loop", type="loop_node", params={"iterations": 5}),
            WorkflowNode(id="bp", type="bubble_pass"),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            # Channel 1: static (no feedback)
            WorkflowEdge(id="e1", source="gen1", source_port="array",
                         target="loop", target_port="init_1"),
            # Channel 2: will be sorted via feedback
            WorkflowEdge(id="e2", source="gen2", source_port="array",
                         target="loop", target_port="init_2"),
            # loop:loop_2 → bp → feedback_2
            WorkflowEdge(id="e3", source="loop", source_port="loop_2",
                         target="bp", target_port="array"),
            WorkflowEdge(id="e4", source="bp", source_port="array",
                         target="loop", target_port="feedback_2",
                         is_back_edge=True),
            # done_2 → measure
            WorkflowEdge(id="e5", source="loop", source_port="done_2",
                         target="meas", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "meas" in results
    assert "score" in results["meas"]
    # Channel 1 should still be in done outputs
    assert "done_1" in results["loop"]


def test_legacy_loop_still_works():
    """Ensure legacy loop_group still works after new loop additions."""
    _load()
    wf = WorkflowDefinition(
        name="test_legacy",
        nodes=[
            WorkflowNode(id="gen", type="generate_array", params={"size": 50}),
            WorkflowNode(id="loop", type="loop_group", params={"iterations": 50}),
            WorkflowNode(id="bp", type="bubble_pass", parent_id="loop"),
            WorkflowNode(id="meas", type="measure_disorder"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="array",
                         target="loop", target_port="array"),
            WorkflowEdge(id="e2", source="loop", source_port="array",
                         target="meas", target_port="array"),
            WorkflowEdge(id="e3", source="loop", source_port="array",
                         target="bp", target_port="array"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    score = results["meas"]["score"]
    assert score > 0.7, f"Expected partially sorted after 50 bubble passes, got {score}"
