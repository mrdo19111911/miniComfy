"""Tests for VRP Generate CVRP node."""
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


def test_generate_cvrp_registered():
    """Node should be discoverable after plugin load."""
    assert "vrp_generate_cvrp" in _NODE_REGISTRY


def test_generate_cvrp_output_shapes():
    """Output arrays should have correct shapes."""
    executor = _EXECUTORS["vrp_generate_cvrp"]

    result = executor({"num_customers": 20, "num_vehicles": 3})

    customers = result["customers"]
    fleet = result["fleet"]

    # customers: (n+1, 4) — [x, y, demand, tw_open] (depot at index 0)
    assert customers.shape == (21, 4)
    assert customers[0, 2] == 0  # depot has zero demand

    # fleet is a dict with numpy arrays
    assert fleet["num_vehicles"] == 3
    assert fleet["vehicle_types"].shape == (3,)
    assert fleet["depot"].shape == (3,)
    assert fleet["capacity_weight"].shape == (3,)


def test_generate_cvrp_deterministic_with_seed():
    """Same seed should produce identical data."""
    executor = _EXECUTORS["vrp_generate_cvrp"]

    r1 = executor({"num_customers": 10, "num_vehicles": 2, "seed": 42})
    r2 = executor({"num_customers": 10, "num_vehicles": 2, "seed": 42})

    np.testing.assert_array_equal(r1["customers"], r2["customers"])
