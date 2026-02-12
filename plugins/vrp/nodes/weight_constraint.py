"""Weight constraint (unary-add): cumulative cargo weight per route."""
import numpy as np

NODE_INFO = {
    "type": "vrp_weight_constraint",
    "label": "Weight",
    "category": "CONSTRAINT",
    "description": "Cumulative cargo weight must not exceed vehicle capacity.",
    "constraint_class": "unary_add",
    "ports_in": [
        {"name": "fleet", "type": "ARRAY", "required": True},
        {"name": "customers", "type": "ARRAY", "required": True},
    ],
    "ports_out": [
        {"name": "bundle", "type": "ARRAY"},
    ],
}

DEMAND_COL = 2  # column index in customers array


def run(fleet, customers):
    k = fleet["num_vehicles"]

    node_values = customers[:, DEMAND_COL].copy()
    upper = fleet["capacity_weight"].copy()
    init = np.zeros(k)
    cost_w = fleet.get("cost_per_kg", np.zeros(k)).copy()
    penalty_w = np.full(k, 0.0)  # hard constraint by default

    return {
        "node_values": node_values,
        "edge_values": None,
        "upper": upper,
        "init": init,
        "cost_w": cost_w,
        "penalty_w": penalty_w,
        "scan_fn": None,
    }
