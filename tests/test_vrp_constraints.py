"""Tests for VRP constraint nodes."""
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


# --- Weight Constraint ---

def test_weight_constraint_registered():
    assert "vrp_weight_constraint" in _NODE_REGISTRY


def test_weight_constraint_bundle_shape():
    executor = _EXECUTORS["vrp_weight_constraint"]

    n, k = 10, 3
    customers = np.zeros((n + 1, 4))
    customers[1:, 2] = np.arange(1, n + 1, dtype=float)  # demands 1..10

    fleet = {
        "num_vehicles": k,
        "capacity_weight": np.full(k, 50.0),
        "cost_per_kg": np.ones(k),
        "deploy_cost": np.zeros(k),
    }

    result = executor({}, customers=customers, fleet=fleet)
    bundle = result["bundle"]

    assert bundle["node_values"].shape == (n + 1,)
    assert bundle["upper"].shape == (k,)
    assert bundle["init"].shape == (k,)
    assert bundle["cost_w"].shape == (k,)
    assert bundle["penalty_w"].shape == (k,)
    assert bundle["edge_values"] is None
    assert bundle["scan_fn"] is None

    # Depot should have zero demand
    assert bundle["node_values"][0] == 0.0
    # Upper should match fleet capacity
    np.testing.assert_array_equal(bundle["upper"], np.full(k, 50.0))


# --- Distance Cost ---

def test_distance_cost_registered():
    assert "vrp_distance_cost" in _NODE_REGISTRY


def test_distance_cost_bundle_shape():
    executor = _EXECUTORS["vrp_distance_cost"]

    n, k = 5, 2
    customers = np.zeros((n + 1, 4))
    customers[:, :2] = np.random.default_rng(42).uniform(0, 100, (n + 1, 2))

    fleet = {
        "num_vehicles": k,
        "cost_per_km": np.array([1.0, 1.5]),
        "max_distance": np.full(k, 500.0),
    }

    result = executor({}, customers=customers, fleet=fleet)
    bundle = result["bundle"]

    assert bundle["node_values"] is None
    assert bundle["edge_values"].shape == (n + 1, n + 1)
    assert bundle["upper"].shape == (k,)
    assert bundle["scan_fn"] is None

    # Distance matrix should be symmetric
    np.testing.assert_array_almost_equal(
        bundle["edge_values"], bundle["edge_values"].T
    )
    # Diagonal should be zero
    np.testing.assert_array_equal(np.diag(bundle["edge_values"]), 0)
