"""Tests for VRP Constraint Assembler."""
import numpy as np
import pytest
from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS
from pipestudio.plugin_loader import load_plugins

PLUGINS_DIR = "plugins"


@pytest.fixture(autouse=True)
def _load():
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    load_plugins(PLUGINS_DIR)


def test_assembler_registered():
    assert "vrp_constraint_assembler" in _NODE_REGISTRY


def test_assembler_with_weight_only():
    """Assembler with single weight constraint should produce working check_route."""
    assembler = _EXECUTORS["vrp_constraint_assembler"]

    weight_bundle = {
        "node_values": np.array([0, 10, 20, 5, 15, 8], dtype=np.float64),
        "edge_values": None,
        "upper": np.array([40.0, 40.0]),
        "init": np.zeros(2),
        "cost_w": np.ones(2),
        "penalty_w": np.zeros(2),
        "scan_fn": None,
    }

    fleet = {
        "num_vehicles": 2,
        "depot": np.zeros(2, dtype=np.int64),
    }

    result = assembler(
        {},
        unary_add=weight_bundle,
        fleet=fleet,
    )

    check_route = result["check_route"]
    compute_cost = result["compute_cost"]
    data = result["data"]

    assert callable(check_route)
    assert callable(compute_cost)

    # Route [1, 3] → weight = 10 + 5 = 15 ≤ 40 → feasible
    route = np.array([1, 3], dtype=np.int64)
    feasible, _ = check_route(route, len(route), 0, data)
    assert feasible

    # Route [1, 2, 4, 5] → weight = 10 + 20 + 15 + 8 = 53 > 40 → infeasible
    route2 = np.array([1, 2, 4, 5], dtype=np.int64)
    feasible2, fail_pos = check_route(route2, len(route2), 0, data)
    assert not feasible2


def test_assembler_with_distance():
    """Assembler with distance constraint should check cumulative distance."""
    assembler = _EXECUTORS["vrp_constraint_assembler"]

    dist = np.array([
        [0, 10, 20, 30],
        [10, 0, 15, 25],
        [20, 15, 0, 10],
        [30, 25, 10, 0],
    ], dtype=np.float64)

    dist_bundle = {
        "node_values": None,
        "edge_values": dist,
        "upper": np.array([50.0]),
        "init": np.zeros(1),
        "cost_w": np.ones(1),
        "penalty_w": np.zeros(1),
        "scan_fn": None,
    }

    fleet = {"num_vehicles": 1, "depot": np.zeros(1, dtype=np.int64)}

    result = assembler({}, binary_add=dist_bundle, fleet=fleet)
    check_route = result["check_route"]
    data = result["data"]

    # Route depot→1→2 → dist = 10 + 15 = 25 ≤ 50 → feasible
    route = np.array([1, 2], dtype=np.int64)
    feasible, _ = check_route(route, 2, 0, data)
    assert feasible

    # Route depot→3→2→1 → dist = 30 + 10 + 15 = 55 > 50 → infeasible
    route2 = np.array([3, 2, 1], dtype=np.int64)
    feasible2, _ = check_route(route2, 3, 0, data)
    assert not feasible2


def test_assembler_stacks_multiple_bundles():
    """Two weight bundles (weight + cbm) into unary_add should stack to (n, 2)."""
    assembler = _EXECUTORS["vrp_constraint_assembler"]

    weight_bundle = {
        "node_values": np.array([0, 10, 20, 5], dtype=np.float64),
        "edge_values": None,
        "upper": np.array([30.0]),
        "init": np.zeros(1),
        "cost_w": np.ones(1),
        "penalty_w": np.zeros(1),
        "scan_fn": None,
    }
    cbm_bundle = {
        "node_values": np.array([0, 5, 3, 8], dtype=np.float64),
        "edge_values": None,
        "upper": np.array([15.0]),
        "init": np.zeros(1),
        "cost_w": np.ones(1),
        "penalty_w": np.zeros(1),
        "scan_fn": None,
    }

    fleet = {"num_vehicles": 1, "depot": np.zeros(1, dtype=np.int64)}

    # Pass as list (multi-edge stacking)
    result = assembler({}, unary_add=[weight_bundle, cbm_bundle], fleet=fleet)
    check_route = result["check_route"]
    data = result["data"]

    # Route [1, 3] → weight=15, cbm=13 → both ≤ limits → feasible
    route = np.array([1, 3], dtype=np.int64)
    feasible, _ = check_route(route, 2, 0, data)
    assert feasible

    # Route [1, 2, 3] → weight=35>30 → infeasible (weight violated)
    route2 = np.array([1, 2, 3], dtype=np.int64)
    feasible2, _ = check_route(route2, 3, 0, data)
    assert not feasible2
