"""Tests for plugin loader and sorting plugin."""
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


def test_sorting_plugin_loads():
    manifests = _fresh_load()
    assert len(manifests) >= 1
    sorting = [m for m in manifests if m.get("name") == "sorting"]
    assert len(sorting) == 1
    assert sorting[0]["_loaded"] is True


def test_sorting_plugin_has_all_nodes():
    _fresh_load()
    expected = {"generate_array", "shuffle_segment", "reverse_segment",
                "partial_sort", "bubble_pass", "measure_disorder", "loop_group"}
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


def test_generate_array_executor():
    _fresh_load()
    result = _EXECUTORS["generate_array"]({"size": 100})
    assert "array" in result
    assert len(result["array"]) == 100


def test_bubble_pass_executor():
    import numpy as np
    _fresh_load()
    arr = np.array([3, 1, 2, 5, 4])
    result = _EXECUTORS["bubble_pass"]({}, array=arr)
    assert "array" in result
    # After one bubble pass: [1, 2, 3, 4, 5]
    assert list(result["array"]) == [1, 2, 3, 4, 5]


def test_measure_disorder_executor():
    import numpy as np
    _fresh_load()
    sorted_arr = np.arange(100)
    result = _EXECUTORS["measure_disorder"]({}, array=sorted_arr)
    assert result["score"] == 1.0


def test_node_spec_has_required_fields():
    _fresh_load()
    for node_type, spec in _NODE_REGISTRY.items():
        assert "type" in spec, f"{node_type} missing 'type'"
        assert "label" in spec, f"{node_type} missing 'label'"
        assert "category" in spec, f"{node_type} missing 'category'"
        assert "inputs" in spec, f"{node_type} missing 'inputs'"
        assert "outputs" in spec, f"{node_type} missing 'outputs'"
        assert "doc" in spec, f"{node_type} missing 'doc'"
