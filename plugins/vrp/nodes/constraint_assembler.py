"""Constraint Assembler — stacks bundles, JIT-compiles check_route & compute_cost."""
import numpy as np
from numba import njit

NODE_INFO = {
    "type": "vrp_constraint_assembler",
    "label": "Constraint Assembler",
    "category": "ASSEMBLER",
    "description": "Collects constraint bundles and compiles check_route / compute_cost.",
    "ports_in": [
        {"name": "unary_add", "type": "ARRAY", "required": False},
        {"name": "unary_max", "type": "ARRAY", "required": False},
        {"name": "unary_scan", "type": "ARRAY", "required": False},
        {"name": "binary_add", "type": "ARRAY", "required": False},
        {"name": "binary_max", "type": "ARRAY", "required": False},
        {"name": "binary_scan", "type": "ARRAY", "required": False},
        {"name": "anyary_add", "type": "ARRAY", "required": False},
        {"name": "anyary_max", "type": "ARRAY", "required": False},
        {"name": "anyary_any", "type": "ARRAY", "required": False},
        {"name": "fleet", "type": "ARRAY", "required": True},
    ],
    "ports_out": [
        {"name": "check_route", "type": "FUNCTION"},
        {"name": "compute_cost", "type": "FUNCTION"},
        {"name": "data", "type": "ARRAY"},
    ],
}


def _to_list(val):
    """Normalize single bundle or list of bundles to list."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _stack_bundles(bundles, n, k, has_edges):
    """Stack bundles into contiguous arrays for numba."""
    if not bundles:
        if has_edges:
            return (np.zeros((n, n, 0), dtype=np.float64),
                    np.zeros((k, 0), dtype=np.float64),
                    np.zeros((k, 0), dtype=np.float64),
                    np.zeros((k, 0), dtype=np.float64),
                    np.zeros((k, 0), dtype=np.float64))
        return (np.zeros((n, 0), dtype=np.float64),
                np.zeros((k, 0), dtype=np.float64),
                np.zeros((k, 0), dtype=np.float64),
                np.zeros((k, 0), dtype=np.float64),
                np.zeros((k, 0), dtype=np.float64))

    if has_edges:
        values = np.stack([b["edge_values"] for b in bundles], axis=-1)
    else:
        # Each bundle has node_values shape (n,) → stack to (n, D)
        values = np.column_stack([b["node_values"] for b in bundles])

    upper = np.column_stack([b["upper"] for b in bundles])
    init = np.column_stack([b["init"] for b in bundles])
    cost_w = np.column_stack([b["cost_w"] for b in bundles])
    penalty_w = np.column_stack([b["penalty_w"] for b in bundles])

    return values, upper, init, cost_w, penalty_w


def run(unary_add=None, unary_max=None, unary_scan=None,
        binary_add=None, binary_max=None, binary_scan=None,
        anyary_add=None, anyary_max=None, anyary_any=None,
        fleet=None):

    depot = fleet["depot"]
    k = fleet["num_vehicles"]

    # Determine n from first non-None bundle
    n = 0
    for bundles_raw in [unary_add, unary_max, unary_scan,
                        binary_add, binary_max, binary_scan]:
        bl = _to_list(bundles_raw)
        for b in bl:
            if b.get("node_values") is not None:
                n = len(b["node_values"])
                break
            if b.get("edge_values") is not None:
                n = b["edge_values"].shape[0]
                break
        if n > 0:
            break

    # Stack each constraint class
    ua_bundles = _to_list(unary_add)
    ba_bundles = _to_list(binary_add)

    nodes_add, upper_add, init_add, cost_w_add, pen_w_add = \
        _stack_bundles(ua_bundles, n, k, False)
    dist_add, upper_dist, init_dist, cost_w_dist, pen_w_dist = \
        _stack_bundles(ba_bundles, n, k, True)

    C_add = nodes_add.shape[1] if nodes_add.ndim == 2 else 0
    D_add = dist_add.shape[2] if dist_add.ndim == 3 else 0

    # Merge upper/init/cost_w/penalty_w across all dimension types
    if C_add + D_add > 0:
        all_upper = np.hstack([upper_add, upper_dist]).astype(np.float64)
        all_init = np.hstack([init_add, init_dist]).astype(np.float64)
        all_cost_w = np.hstack([cost_w_add, cost_w_dist]).astype(np.float64)
        all_pen_w = np.hstack([pen_w_add, pen_w_dist]).astype(np.float64)
    else:
        all_upper = np.zeros((k, 0), dtype=np.float64)
        all_init = np.zeros((k, 0), dtype=np.float64)
        all_cost_w = np.zeros((k, 0), dtype=np.float64)
        all_pen_w = np.zeros((k, 0), dtype=np.float64)

    # Ensure contiguous float64 arrays for numba
    nodes_add = np.ascontiguousarray(nodes_add, dtype=np.float64)
    dist_add = np.ascontiguousarray(dist_add, dtype=np.float64)

    # Pack data tuple (numba-compatible)
    data = (depot, nodes_add, dist_add, all_upper, all_init,
            all_cost_w, all_pen_w)

    # Capture dimension counts as compile-time constants
    _C_add = C_add
    _D_add = D_add

    @njit(cache=True)
    def check_route(route, route_len, vehicle_id, data_tuple):
        (depot_arr, nodes_add_arr, dist_add_arr,
         upper, init, cost_w, pen_w) = data_tuple

        state = init[vehicle_id].copy()

        for pos in range(route_len):
            cur = route[pos]
            prev = route[pos - 1] if pos > 0 else depot_arr[vehicle_id]

            # Unary-add dimensions
            for d in range(_C_add):
                state[d] += nodes_add_arr[cur, d]
                if pen_w[vehicle_id, d] == 0.0 and state[d] > upper[vehicle_id, d]:
                    return False, pos

            # Binary-add dimensions
            for d in range(_D_add):
                dim_idx = _C_add + d
                state[dim_idx] += dist_add_arr[prev, cur, d]
                if pen_w[vehicle_id, dim_idx] == 0.0 and state[dim_idx] > upper[vehicle_id, dim_idx]:
                    return False, pos

        return True, route_len

    @njit(cache=True)
    def compute_cost(route, route_len, vehicle_id, data_tuple):
        (depot_arr, nodes_add_arr, dist_add_arr,
         upper, init, cost_w, pen_w) = data_tuple

        state = init[vehicle_id].copy()

        for pos in range(route_len):
            cur = route[pos]
            prev = route[pos - 1] if pos > 0 else depot_arr[vehicle_id]

            for d in range(_C_add):
                state[d] += nodes_add_arr[cur, d]
            for d in range(_D_add):
                state[_C_add + d] += dist_add_arr[prev, cur, d]

        cost = 0.0
        total_dims = _C_add + _D_add
        for d in range(total_dims):
            if state[d] <= upper[vehicle_id, d]:
                cost += cost_w[vehicle_id, d] * state[d]
            else:
                violation = state[d] - upper[vehicle_id, d]
                cost += cost_w[vehicle_id, d] * upper[vehicle_id, d]
                cost += pen_w[vehicle_id, d] * violation

        return cost

    return check_route, compute_cost, data
