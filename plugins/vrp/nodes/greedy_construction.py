"""Greedy construction — insert customers one by one at cheapest feasible position."""
import numpy as np

NODE_INFO = {
    "type": "vrp_greedy_construction",
    "label": "Greedy Construction",
    "category": "SOLVER",
    "description": "Build initial VRP solution by greedy insertion.",
    "ports_in": [
        {"name": "check_route", "type": "FUNCTION", "required": True},
        {"name": "compute_cost", "type": "FUNCTION", "required": True},
        {"name": "data", "type": "ARRAY", "required": True},
        {"name": "fleet", "type": "ARRAY", "required": True},
        {"name": "customers", "type": "ARRAY", "required": True},
    ],
    "ports_out": [
        {"name": "route_nodes", "type": "ARRAY"},
        {"name": "route_len", "type": "ARRAY"},
        {"name": "cost", "type": "NUMBER"},
    ],
}


def run(check_route, compute_cost, data, fleet, customers):
    n = len(customers)  # includes depot at 0
    k = fleet["num_vehicles"]
    max_route_len = n  # worst case: all customers on one route

    route_nodes = np.full((k, max_route_len), -1, dtype=np.int64)
    route_len = np.zeros(k, dtype=np.int64)
    assigned = np.zeros(n, dtype=np.bool_)
    assigned[0] = True  # depot is not a customer

    # Sort customers by demand descending (heaviest first heuristic)
    customer_ids = np.arange(1, n)
    demands = customers[1:, 2]
    order = customer_ids[np.argsort(-demands)]

    for cust in order:
        best_cost = np.inf
        best_route = -1
        best_pos = -1

        for r in range(k):
            rl = int(route_len[r])
            # Try inserting at each position
            for pos in range(rl + 1):
                # Build trial route
                trial = np.empty(rl + 1, dtype=np.int64)
                trial[:pos] = route_nodes[r, :pos]
                trial[pos] = cust
                trial[pos + 1:] = route_nodes[r, pos:rl]

                feasible, _ = check_route(trial, rl + 1, r, data)
                if feasible:
                    c = compute_cost(trial, rl + 1, r, data)
                    if c < best_cost:
                        best_cost = c
                        best_route = r
                        best_pos = pos

        if best_route >= 0:
            r = best_route
            rl = int(route_len[r])
            # Shift right
            route_nodes[r, best_pos + 1:rl + 1] = route_nodes[r, best_pos:rl]
            route_nodes[r, best_pos] = cust
            route_len[r] += 1
            assigned[cust] = True

    # Total cost
    total_cost = 0.0
    for r in range(k):
        if route_len[r] > 0:
            total_cost += compute_cost(
                route_nodes[r, :int(route_len[r])],
                int(route_len[r]), r, data
            )

    return route_nodes, route_len, float(total_cost)
