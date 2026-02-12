"""Tests for plugin loader and TSP plugin."""
import sys
import os

# Ensure PipeStudio package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS
from pipestudio.plugin_loader import load_plugins

PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "plugins")


def _fresh_load():
    """Clear registry and reload all plugins."""
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    return load_plugins(PLUGINS_DIR)


def test_tsp_plugin_loads():
    manifests = _fresh_load()
    assert len(manifests) >= 1
    tsp = [m for m in manifests if m.get("name") == "tsp"]
    assert len(tsp) == 1
    assert tsp[0]["_loaded"] is True


def test_tsp_plugin_has_all_nodes():
    _fresh_load()
    expected = {
        "tsp_generate_points", "tsp_distance_matrix", "tsp_greedy",
        "tsp_2opt", "tsp_evaluate", "tsp_log_tour",
        "tsp_map_visualize", "tsp_view_text", "loop_group",
    }
    assert expected.issubset(set(_NODE_REGISTRY.keys()))


def test_loop_group_not_in_executors():
    _fresh_load()
    assert "loop_group" not in _EXECUTORS
    assert "loop_group" in _NODE_REGISTRY


def test_all_non_control_nodes_have_executors():
    _fresh_load()
    for node_type, spec in _NODE_REGISTRY.items():
        if spec["category"] != "CONTROL":
            assert node_type in _EXECUTORS, f"{node_type} missing executor"


def test_generate_points_executor():
    _fresh_load()
    result = _EXECUTORS["tsp_generate_points"]({"num_points": 20})
    assert "points" in result
    assert result["points"].shape == (20, 2)


def test_greedy_executor():
    import numpy as np
    _fresh_load()
    points = np.array([[0, 0], [1, 0], [0, 1]], dtype=float)
    diff = points[:, np.newaxis, :] - points[np.newaxis, :, :]
    dm = np.sqrt(np.sum(diff ** 2, axis=2))
    result = _EXECUTORS["tsp_greedy"]({}, dist_matrix=dm)
    assert "tour" in result
    assert "tour_length" in result
    assert len(result["tour"]) == 3


def test_evaluate_executor():
    import numpy as np
    _fresh_load()
    dm = np.array([[0, 1, 2], [1, 0, 1.5], [2, 1.5, 0]], dtype=float)
    tour = np.array([0, 1, 2])
    result = _EXECUTORS["tsp_evaluate"]({}, dist_matrix=dm, tour=tour)
    assert "tour_length" in result
    assert result["tour_length"] > 0


def test_node_spec_has_required_fields():
    _fresh_load()
    for node_type, spec in _NODE_REGISTRY.items():
        assert "type" in spec, f"{node_type} missing 'type'"
        assert "label" in spec, f"{node_type} missing 'label'"
        assert "category" in spec, f"{node_type} missing 'category'"
        assert "inputs" in spec, f"{node_type} missing 'inputs'"
        assert "outputs" in spec, f"{node_type} missing 'outputs'"
        assert "doc" in spec, f"{node_type} missing 'doc'"
