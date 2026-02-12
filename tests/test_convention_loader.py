"""Tests for the NODE_INFO + run() convention-based plugin loading."""
import sys
import os
import types
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS


def _clear():
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()


# ---------------------------------------------------------------------------
# Test register_node() function
# ---------------------------------------------------------------------------

def test_register_node_basic():
    """register_node() populates both registries."""
    _clear()
    from pipestudio.plugin_api import register_node

    node_info = {
        "type": "test_basic",
        "label": "Test Basic",
        "category": "TEST",
        "ports_in": [{"name": "x", "type": "ARRAY"}],
        "ports_out": [{"name": "y", "type": "ARRAY"}],
    }

    def fake_executor(params, **inputs):
        return {"y": inputs["x"]}

    register_node(node_info, fake_executor)
    assert "test_basic" in _NODE_REGISTRY
    assert "test_basic" in _EXECUTORS
    spec = _NODE_REGISTRY["test_basic"]
    assert spec["type"] == "test_basic"
    assert spec["label"] == "Test Basic"
    assert spec["category"] == "TEST"
    assert len(spec["inputs"]) == 1
    assert spec["inputs"][0]["name"] == "x"
    assert len(spec["outputs"]) == 1


def test_register_node_spec_only():
    """register_node(info, None) registers spec but NOT executor (loop_group case)."""
    _clear()
    from pipestudio.plugin_api import register_node

    node_info = {
        "type": "test_spec_only",
        "label": "Spec Only",
        "category": "CONTROL",
        "ports_in": [],
        "ports_out": [],
    }
    register_node(node_info, None)
    assert "test_spec_only" in _NODE_REGISTRY
    assert "test_spec_only" not in _EXECUTORS


def test_register_node_normalizes_ports():
    """register_node() converts ports_in/ports_out to inputs/outputs with required/default."""
    _clear()
    from pipestudio.plugin_api import register_node

    node_info = {
        "type": "test_normalize",
        "label": "T",
        "category": "T",
        "ports_in": [
            {"name": "a", "type": "ARRAY"},
            {"name": "b", "type": "NUMBER", "default": 50},
            {"name": "c", "type": "ARRAY", "required": False},
        ],
        "ports_out": [{"name": "out", "type": "ARRAY"}],
    }
    register_node(node_info, lambda p, **kw: {"out": None})

    spec = _NODE_REGISTRY["test_normalize"]
    inputs = spec["inputs"]
    assert inputs[0]["required"] is True
    assert inputs[0]["default"] is None
    assert inputs[1]["required"] is False
    assert inputs[1]["default"] == 50
    assert inputs[2]["required"] is False


# ---------------------------------------------------------------------------
# Test _make_executor wrapper
# ---------------------------------------------------------------------------

def test_wrapper_maps_inputs_to_positional_args():
    """Wrapper converts (params, **inputs) to positional args for run()."""
    _clear()
    from pipestudio.plugin_loader import _make_executor

    module = types.ModuleType("fake")
    module.NODE_INFO = {
        "type": "test_pos",
        "label": "T",
        "category": "T",
        "ports_in": [{"name": "array", "type": "ARRAY"}],
        "ports_out": [{"name": "array", "type": "ARRAY"}],
    }
    captured = {}

    def fake_run(array):
        captured["array"] = array
        return array

    module.run = fake_run
    executor = _make_executor(module)
    result = executor({}, array=[1, 2, 3])
    assert captured["array"] == [1, 2, 3]
    assert result == {"array": [1, 2, 3]}


def test_wrapper_maps_params_to_positional_args():
    """NUMBER config params are passed as positional args to run()."""
    _clear()
    from pipestudio.plugin_loader import _make_executor

    module = types.ModuleType("fake")
    module.NODE_INFO = {
        "type": "test_params",
        "label": "T",
        "category": "T",
        "ports_in": [{"name": "size", "type": "NUMBER", "default": 1000}],
        "ports_out": [{"name": "array", "type": "ARRAY"}],
    }

    def fake_run(size):
        return list(range(int(size)))

    module.run = fake_run
    executor = _make_executor(module)
    result = executor({"size": 5})
    assert result == {"array": [0, 1, 2, 3, 4]}


def test_wrapper_uses_defaults_from_node_info():
    """When params/inputs don't provide a value, default from NODE_INFO is used."""
    _clear()
    from pipestudio.plugin_loader import _make_executor

    module = types.ModuleType("fake")
    module.NODE_INFO = {
        "type": "test_defaults",
        "label": "T",
        "category": "T",
        "ports_in": [{"name": "size", "type": "NUMBER", "default": 42}],
        "ports_out": [{"name": "val", "type": "NUMBER"}],
    }

    def fake_run(size):
        return size

    module.run = fake_run
    executor = _make_executor(module)
    result = executor({})  # no params, no inputs
    assert result == {"val": 42}


def test_wrapper_tuple_return_to_dict():
    """Wrapper converts tuple return to dict using ports_out names."""
    _clear()
    from pipestudio.plugin_loader import _make_executor

    module = types.ModuleType("fake")
    module.NODE_INFO = {
        "type": "test_tuple",
        "label": "T",
        "category": "T",
        "ports_in": [{"name": "x", "type": "NUMBER"}],
        "ports_out": [
            {"name": "a", "type": "NUMBER"},
            {"name": "b", "type": "NUMBER"},
        ],
    }

    def fake_run(x):
        return x * 2, x * 3

    module.run = fake_run
    executor = _make_executor(module)
    result = executor({"x": 10})
    assert result == {"a": 20, "b": 30}


def test_wrapper_single_return_to_dict():
    """Single (non-tuple) return wraps to dict with one key."""
    _clear()
    from pipestudio.plugin_loader import _make_executor

    module = types.ModuleType("fake")
    module.NODE_INFO = {
        "type": "test_single",
        "label": "T",
        "category": "T",
        "ports_in": [{"name": "x", "type": "ARRAY"}],
        "ports_out": [{"name": "y", "type": "ARRAY"}],
    }

    def fake_run(x):
        return x  # single value, not tuple

    module.run = fake_run
    executor = _make_executor(module)
    result = executor({}, x=[1, 2])
    assert result == {"y": [1, 2]}


# ---------------------------------------------------------------------------
# Test convention-based module loading
# ---------------------------------------------------------------------------

def test_convention_module_loads_and_registers():
    """A .py file with NODE_INFO + run() gets registered via the loader."""
    _clear()
    from pipestudio.plugin_loader import _import_module

    # Create a temp plugin file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
    ) as f:
        f.write(
            'NODE_INFO = {\n'
            '    "type": "conv_test_node",\n'
            '    "label": "Conv Test",\n'
            '    "category": "TEST",\n'
            '    "ports_in": [{"name": "x", "type": "NUMBER", "default": 5}],\n'
            '    "ports_out": [{"name": "y", "type": "NUMBER"}],\n'
            '}\n\n'
            'def run(x):\n'
            '    return x * 10\n'
        )
        tmp_path = f.name

    try:
        _import_module("test_conv_module", tmp_path)
        assert "conv_test_node" in _NODE_REGISTRY
        assert "conv_test_node" in _EXECUTORS
        # Test the executor works
        result = _EXECUTORS["conv_test_node"]({"x": 7})
        assert result == {"y": 70}
    finally:
        os.unlink(tmp_path)


def test_convention_module_spec_only_no_run():
    """A module with NODE_INFO but no run() registers spec only."""
    _clear()
    from pipestudio.plugin_loader import _import_module

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
    ) as f:
        f.write(
            'NODE_INFO = {\n'
            '    "type": "spec_only_test",\n'
            '    "label": "Spec Only",\n'
            '    "category": "CONTROL",\n'
            '    "ports_in": [],\n'
            '    "ports_out": [],\n'
            '}\n'
        )
        tmp_path = f.name

    try:
        _import_module("test_spec_only_module", tmp_path)
        assert "spec_only_test" in _NODE_REGISTRY
        assert "spec_only_test" not in _EXECUTORS
    finally:
        os.unlink(tmp_path)
