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
    """tsp_generate_points -> tsp_distance_matrix"""
    _load()
    wf = WorkflowDefinition(
        name="test",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="dm", target_port="points"),
        ],
    )
    executor = WorkflowExecutor(wf)
    results = executor.execute()
    assert "gen" in results
    assert "dm" in results
    assert "dist_matrix" in results["dm"]
    assert results["dm"]["dist_matrix"].shape == (10, 10)


def test_chain_workflow():
    """generate_points -> distance_matrix -> greedy -> evaluate"""
    _load()
    wf = WorkflowDefinition(
        name="test_chain",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
            WorkflowNode(id="greedy", type="tsp_greedy"),
            WorkflowNode(id="eval", type="tsp_evaluate"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="dm", target_port="points"),
            WorkflowEdge(id="e2", source="dm", source_port="dist_matrix",
                         target="greedy", target_port="dist_matrix"),
            WorkflowEdge(id="e3", source="dm", source_port="dist_matrix",
                         target="eval", target_port="dist_matrix"),
            WorkflowEdge(id="e4", source="greedy", source_port="tour",
                         target="eval", target_port="tour"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert len(results) == 4
    assert "tour_length" in results["eval"]


def test_loop_group():
    """generate_points -> dm -> greedy -> loop_group(2opt) -> evaluate"""
    _load()
    wf = WorkflowDefinition(
        name="test_loop",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
            WorkflowNode(id="greedy", type="tsp_greedy"),
            WorkflowNode(id="loop", type="loop_group", params={"iterations": 3}),
            WorkflowNode(id="opt", type="tsp_2opt", parent_id="loop"),
            WorkflowNode(id="eval", type="tsp_evaluate"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="dm", target_port="points"),
            WorkflowEdge(id="e2", source="dm", source_port="dist_matrix",
                         target="greedy", target_port="dist_matrix"),
            WorkflowEdge(id="e3", source="dm", source_port="dist_matrix",
                         target="loop", target_port="slot_1"),
            WorkflowEdge(id="e4", source="greedy", source_port="tour",
                         target="loop", target_port="slot_2"),
            WorkflowEdge(id="e5", source="loop", source_port="slot_1",
                         target="opt", target_port="dist_matrix"),
            WorkflowEdge(id="e6", source="loop", source_port="slot_2",
                         target="opt", target_port="tour"),
            WorkflowEdge(id="e7", source="dm", source_port="dist_matrix",
                         target="eval", target_port="dist_matrix"),
            WorkflowEdge(id="e8", source="loop", source_port="slot_2",
                         target="eval", target_port="tour"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "eval" in results
    assert "tour_length" in results["eval"]


def test_empty_loop_group_passthrough():
    """Loop group with no children should pass data through."""
    _load()
    wf = WorkflowDefinition(
        name="test_empty_loop",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 5}),
            WorkflowNode(id="loop", type="loop_group", params={"iterations": 5}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="loop", target_port="slot_1"),
            WorkflowEdge(id="e2", source="loop", source_port="slot_1",
                         target="dm", target_port="points"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "dm" in results


def test_event_handler_called():
    """Event handler receives start, node_start, node_complete, complete."""
    _load()
    events = []

    def handler(event_type, data):
        events.append(event_type)

    wf = WorkflowDefinition(
        name="test_events",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 5}),
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
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
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
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 5}),
            WorkflowNode(id="dm", type="tsp_distance_matrix", muted=True),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="dm", target_port="points"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "dm" in results
    assert "points" in results["dm"]
    gen_points = results["gen"]["points"]
    muted_points = results["dm"]["points"]
    assert np.array_equal(gen_points, muted_points)


# ------------------------------------------------------------------
# ComfyUI style loop (loop_start + loop_end pair)
# ------------------------------------------------------------------

def test_comfyui_loop_sorting():
    """loop_start + 2opt + loop_end => improved tour."""
    _load()
    wf = WorkflowDefinition(
        name="test_comfyui_tsp",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
            WorkflowNode(id="greedy", type="tsp_greedy"),
            WorkflowNode(id="ls", type="loop_start", params={"iterations": 3}),
            WorkflowNode(id="opt", type="tsp_2opt"),
            WorkflowNode(id="le", type="loop_end", params={"pair_id": "ls"}),
            WorkflowNode(id="eval", type="tsp_evaluate"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="dm", target_port="points"),
            WorkflowEdge(id="e2", source="dm", source_port="dist_matrix",
                         target="greedy", target_port="dist_matrix"),
            WorkflowEdge(id="e3", source="dm", source_port="dist_matrix",
                         target="ls", target_port="in_1"),
            WorkflowEdge(id="e4", source="greedy", source_port="tour",
                         target="ls", target_port="in_2"),
            WorkflowEdge(id="e5", source="ls", source_port="out_1",
                         target="opt", target_port="dist_matrix"),
            WorkflowEdge(id="e6", source="ls", source_port="out_2",
                         target="opt", target_port="tour"),
            WorkflowEdge(id="e7", source="opt", source_port="tour",
                         target="le", target_port="in_2"),
            WorkflowEdge(id="e8", source="ls", source_port="out_1",
                         target="le", target_port="in_1"),
            WorkflowEdge(id="e9", source="le", source_port="out_1",
                         target="eval", target_port="dist_matrix"),
            WorkflowEdge(id="e10", source="le", source_port="out_2",
                         target="eval", target_port="tour"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "tour_length" in results["eval"]
    assert results["eval"]["tour_length"] > 0


def test_comfyui_loop_two_channels():
    """ComfyUI loop passing two data channels."""
    _load()
    wf = WorkflowDefinition(
        name="test_comfyui_2ch",
        nodes=[
            WorkflowNode(id="gen1", type="tsp_generate_points", params={"num_points": 5}),
            WorkflowNode(id="gen2", type="tsp_generate_points", params={"num_points": 5}),
            WorkflowNode(id="ls", type="loop_start", params={"iterations": 2}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
            WorkflowNode(id="le", type="loop_end", params={"pair_id": "ls"}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen1", source_port="points",
                         target="ls", target_port="in_1"),
            WorkflowEdge(id="e2", source="gen2", source_port="points",
                         target="ls", target_port="in_2"),
            WorkflowEdge(id="e3", source="ls", source_port="out_1",
                         target="dm", target_port="points"),
            WorkflowEdge(id="e5", source="ls", source_port="out_1",
                         target="le", target_port="in_1"),
            WorkflowEdge(id="e4", source="ls", source_port="out_2",
                         target="le", target_port="in_2"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "out_1" in results["le"]
    assert "out_2" in results["le"]


# ------------------------------------------------------------------
# n8n style loop (loop_node with back-edge feedback)
# ------------------------------------------------------------------

def test_n8n_loop_sorting():
    """loop_node + 2opt with back-edge => improved tour."""
    _load()
    wf = WorkflowDefinition(
        name="test_n8n_tsp",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
            WorkflowNode(id="greedy", type="tsp_greedy"),
            WorkflowNode(id="loop", type="loop_node", params={"iterations": 3}),
            WorkflowNode(id="opt", type="tsp_2opt"),
            WorkflowNode(id="eval", type="tsp_evaluate"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="dm", target_port="points"),
            WorkflowEdge(id="e2", source="dm", source_port="dist_matrix",
                         target="greedy", target_port="dist_matrix"),
            WorkflowEdge(id="e3", source="dm", source_port="dist_matrix",
                         target="loop", target_port="init_1"),
            WorkflowEdge(id="e4", source="greedy", source_port="tour",
                         target="loop", target_port="init_2"),
            WorkflowEdge(id="e5", source="loop", source_port="loop_1",
                         target="opt", target_port="dist_matrix"),
            WorkflowEdge(id="e6", source="loop", source_port="loop_2",
                         target="opt", target_port="tour"),
            WorkflowEdge(id="e7", source="opt", source_port="tour",
                         target="loop", target_port="feedback_2",
                         is_back_edge=True),
            WorkflowEdge(id="e8", source="loop", source_port="done_1",
                         target="eval", target_port="dist_matrix"),
            WorkflowEdge(id="e9", source="loop", source_port="done_2",
                         target="eval", target_port="tour"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "tour_length" in results["eval"]
    assert results["eval"]["tour_length"] > 0


def test_n8n_loop_two_channels():
    """n8n loop with two data channels, only one has feedback."""
    _load()
    wf = WorkflowDefinition(
        name="test_n8n_2ch",
        nodes=[
            WorkflowNode(id="gen1", type="tsp_generate_points", params={"num_points": 5}),
            WorkflowNode(id="gen2", type="tsp_generate_points", params={"num_points": 5}),
            WorkflowNode(id="loop", type="loop_node", params={"iterations": 2}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen1", source_port="points",
                         target="loop", target_port="init_1"),
            WorkflowEdge(id="e2", source="gen2", source_port="points",
                         target="loop", target_port="init_2"),
            WorkflowEdge(id="e3", source="loop", source_port="loop_1",
                         target="dm", target_port="points"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "done_1" in results["loop"]
    assert "done_2" in results["loop"]


def test_legacy_loop_still_works():
    """Ensure legacy loop_group still works."""
    _load()
    wf = WorkflowDefinition(
        name="test_legacy",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
            WorkflowNode(id="loop", type="loop_group", params={"iterations": 2}),
            WorkflowNode(id="greedy", type="tsp_greedy", parent_id="loop"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="dm", target_port="points"),
            WorkflowEdge(id="e2", source="dm", source_port="dist_matrix",
                         target="loop", target_port="slot_1"),
            WorkflowEdge(id="e3", source="loop", source_port="slot_1",
                         target="greedy", target_port="dist_matrix"),
        ],
    )
    results = WorkflowExecutor(wf).execute()
    assert "greedy" in results
    assert "tour" in results["greedy"]
