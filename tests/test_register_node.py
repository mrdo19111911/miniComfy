"""Tests for register_node edge cases: required logic, duplicate detection."""
import os
import sys
import warnings

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS, register_node, unregister_node


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Save and restore registry around each test."""
    saved_reg = dict(_NODE_REGISTRY)
    saved_exec = dict(_EXECUTORS)
    yield
    _NODE_REGISTRY.clear()
    _NODE_REGISTRY.update(saved_reg)
    _EXECUTORS.clear()
    _EXECUTORS.update(saved_exec)


# --- B10: Port required logic ---

def test_port_required_false_without_default():
    """A port with required=False but no default should be marked as NOT required."""
    register_node({
        "type": "test_b10",
        "ports_in": [{"name": "x", "type": "ARRAY", "required": False}],
        "ports_out": [],
    })
    spec = _NODE_REGISTRY["test_b10"]
    assert spec["inputs"][0]["required"] is False


def test_port_required_true_with_no_flags():
    """A port with no required flag and no default should be required."""
    register_node({
        "type": "test_b10b",
        "ports_in": [{"name": "x", "type": "ARRAY"}],
        "ports_out": [],
    })
    spec = _NODE_REGISTRY["test_b10b"]
    assert spec["inputs"][0]["required"] is True


def test_port_with_default_not_required():
    """A port with a default value should NOT be required."""
    register_node({
        "type": "test_b10c",
        "ports_in": [{"name": "n", "type": "NUMBER", "default": 10}],
        "ports_out": [],
    })
    spec = _NODE_REGISTRY["test_b10c"]
    assert spec["inputs"][0]["required"] is False


# --- B9: Duplicate node type warning ---

def test_duplicate_node_type_warns():
    """Registering the same node type twice should emit a warning."""
    register_node({
        "type": "test_dup",
        "ports_in": [],
        "ports_out": [],
    })
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        register_node({
            "type": "test_dup",
            "ports_in": [{"name": "x", "type": "ARRAY"}],
            "ports_out": [],
        })
        assert len(w) == 1
        assert "test_dup" in str(w[0].message)
