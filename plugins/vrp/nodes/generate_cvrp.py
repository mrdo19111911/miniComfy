"""Generate random CVRP test data (customers + fleet)."""
import numpy as np

NODE_INFO = {
    "type": "vrp_generate_cvrp",
    "label": "Generate CVRP",
    "category": "DATA",
    "description": "Generate random CVRP test instance with customers and fleet.",
    "ports_in": [
        {"name": "num_customers", "type": "NUMBER", "required": False, "default": 50},
        {"name": "num_vehicles", "type": "NUMBER", "required": False, "default": 5},
        {"name": "seed", "type": "NUMBER", "required": False, "default": 0},
    ],
    "ports_out": [
        {"name": "customers", "type": "ARRAY"},
        {"name": "fleet", "type": "ARRAY"},
    ],
}


def run(num_customers=50, num_vehicles=5, seed=0):
    rng = np.random.default_rng(int(seed) if seed else None)
    n = int(num_customers)
    k = int(num_vehicles)

    # Depot at (50, 50), customers random in [0, 100]^2
    coords = rng.uniform(0, 100, size=(n + 1, 2))
    coords[0] = [50.0, 50.0]  # depot

    # Demands: depot=0, customers uniform [1, 20]
    demands = np.zeros(n + 1)
    demands[1:] = rng.integers(1, 21, size=n)

    # Placeholder tw_open column (all zeros for basic CVRP)
    tw_open = np.zeros(n + 1)

    # customers array: (n+1, 4) — [x, y, demand, tw_open]
    customers = np.column_stack([coords, demands, tw_open])

    # Fleet: all vehicles identical, capacity ~ total_demand / k * 1.5
    total_demand = demands.sum()
    capacity = total_demand / k * 1.5

    fleet = {
        "num_vehicles": k,
        "num_vehicle_types": 1,
        "vehicle_types": np.zeros(k, dtype=np.int64),
        "depot": np.zeros(k, dtype=np.int64),
        "capacity_weight": np.full(k, capacity),
        "cost_per_km": np.ones(k),
        "deploy_cost": np.zeros(k),
    }

    return customers, fleet
