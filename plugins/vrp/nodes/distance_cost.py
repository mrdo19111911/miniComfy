"""Distance cost constraint (binary-add): cumulative travel distance per route."""
import numpy as np

NODE_INFO = {
    "type": "vrp_distance_cost",
    "label": "Distance Cost",
    "category": "CONSTRAINT",
    "description": "Cumulative travel distance with per-vehicle max and cost.",
    "constraint_class": "binary_add",
    "ports_in": [
        {"name": "fleet", "type": "ARRAY", "required": True},
        {"name": "customers", "type": "ARRAY", "required": True},
    ],
    "ports_out": [
        {"name": "bundle", "type": "ARRAY"},
    ],
}

X_COL, Y_COL = 0, 1


def run(fleet, customers):
    k = fleet["num_vehicles"]
    coords = customers[:, [X_COL, Y_COL]]

    # Euclidean distance matrix
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    dist_matrix = np.sqrt((diff ** 2).sum(axis=-1))

    upper = fleet.get("max_distance", np.full(k, 1e9))
    init = np.zeros(k)
    cost_w = fleet.get("cost_per_km", np.ones(k)).copy()
    penalty_w = np.full(k, 0.0)

    return {
        "node_values": None,
        "edge_values": dist_matrix,
        "upper": upper,
        "init": init,
        "cost_w": cost_w,
        "penalty_w": penalty_w,
        "scan_fn": None,
    }
