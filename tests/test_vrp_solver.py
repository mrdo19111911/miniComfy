"""Tests for VRP solver nodes."""
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


def _make_simple_problem():
    """Create a small CVRP: 5 customers, 2 vehicles, capacity 30."""
    n, k = 5, 2
    customers = np.array([
        [50, 50, 0, 0],   # depot
        [20, 80, 10, 0],  # customer 1
        [80, 80, 10, 0],  # customer 2
        [20, 20, 10, 0],  # customer 3
        [80, 20, 10, 0],  # customer 4
        [50, 50, 5, 0],   # customer 5 (near depot)
    ], dtype=np.float64)

    fleet = {
        "num_vehicles": k,
        "depot": np.zeros(k, dtype=np.int64),
        "capacity_weight": np.full(k, 30.0),
        "cost_per_km": np.ones(k),
    }

    # Build constraint via assembler
    weight_exec = _EXECUTORS["vrp_weight_constraint"]
    dist_exec = _EXECUTORS["vrp_distance_cost"]
    assembler_exec = _EXECUTORS["vrp_constraint_assembler"]

    weight_bundle = weight_exec({}, customers=customers, fleet=fleet)["bundle"]

    fleet_with_max = {**fleet, "max_distance": np.full(k, 1e9)}
    dist_bundle = dist_exec({}, customers=customers, fleet=fleet_with_max)["bundle"]

    assembled = assembler_exec(
        {},
        unary_add=weight_bundle,
        binary_add=dist_bundle,
        fleet=fleet,
    )
    return assembled, customers, fleet


def test_greedy_construction_registered():
    assert "vrp_greedy_construction" in _NODE_REGISTRY


def test_greedy_construction_all_assigned():
    """Greedy construction should assign all customers to routes."""
    assembled, customers, fleet = _make_simple_problem()

    solver = _EXECUTORS["vrp_greedy_construction"]
    result = solver(
        {},
        check_route=assembled["check_route"],
        compute_cost=assembled["compute_cost"],
        data=assembled["data"],
        fleet=fleet,
        customers=customers,
    )

    route_nodes = result["route_nodes"]
    route_len = result["route_len"]
    cost = result["cost"]

    # All 5 customers should be assigned
    assigned = set()
    for r in range(fleet["num_vehicles"]):
        for pos in range(int(route_len[r])):
            assigned.add(int(route_nodes[r, pos]))

    assert assigned == {1, 2, 3, 4, 5}
    assert cost > 0


def test_greedy_construction_respects_capacity():
    """No route should exceed capacity."""
    assembled, customers, fleet = _make_simple_problem()

    solver = _EXECUTORS["vrp_greedy_construction"]
    result = solver(
        {},
        check_route=assembled["check_route"],
        compute_cost=assembled["compute_cost"],
        data=assembled["data"],
        fleet=fleet,
        customers=customers,
    )

    route_nodes = result["route_nodes"]
    route_len = result["route_len"]

    for r in range(fleet["num_vehicles"]):
        total_demand = 0
        for pos in range(int(route_len[r])):
            node = int(route_nodes[r, pos])
            total_demand += customers[node, 2]
        assert total_demand <= fleet["capacity_weight"][r]
