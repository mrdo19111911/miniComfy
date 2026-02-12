# Rich VRP Solver — Architecture Design

## 1. Vision

A modular, visual Vehicle Routing Problem solver built as a PipeStudio plugin project. Users compose VRP problems on canvas by connecting nodes: data sources, constraints, solvers, and visualizations. The system supports all VRP variants (CVRP, VRPTW, PDVRP, MDVRP, etc.) without code changes — constraint shape determines the problem.

**Design principles:**
- **Constraint = data, not code** — array shape determines active constraints
- **100% numpy + numba** — all computation is `@njit`, zero Python in hot paths
- **Modular canvas nodes** — each concern is a separate node, composable via edges
- **Compile-time assembly** — scan functions baked into solver at JIT time, zero runtime dispatch overhead

---

## 2. Canvas Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PipeStudio Canvas                          │
│                                                                     │
│  ┌──────────┐    ┌─────────┐    ┌───────────────────┐              │
│  │ Load CSV │───→│  Fleet  │───→│ Weight Constraint  │──┐          │
│  └──────────┘    └─────────┘ ┌→│ CBM Constraint     │──┤          │
│                              │ │ Time Window         │──┤          │
│                              │ │ Incompatibility     │──┤          │
│                              │ └───────────────────────┘ │          │
│                              │                           ▼          │
│                              │              ┌─────────────────────┐ │
│  ┌───────────────┐           │              │                     │ │
│  │ Random Remove │──┐        │              │ Constraint          │ │
│  │ Shaw Remove   │──┤        │              │ Assembler           │ │
│  │ Worst Remove  │──┤        │              │                     │ │
│  └───────────────┘  │        │              │ → check_route()     │ │
│                     │        │              │ → compute_cost()    │ │
│  ┌───────────────┐  │        │              └──────────┬──────────┘ │
│  │ Greedy Insert │──┤        │                         │            │
│  │ Regret Insert │──┤        │                         ▼            │
│  │ 2-Opt*        │──┤        │              ┌──────────────────┐   │
│  └───────────────┘  ├───────────────────────→│   ALNS Solver    │   │
│                     │        │              └────────┬─────────┘   │
│                              │                       │              │
│                              │          ┌────────────┼──────────┐  │
│                              │          ▼            ▼          ▼  │
│                              │  ┌──────────┐ ┌────────────┐ ┌────┐│
│                              │  │Route Map │ │Convergence │ │KPI ││
│                              │  └──────────┘ └────────────┘ └────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Node categories

| Category | Color | Nodes |
|----------|-------|-------|
| DATA | `#2563EB` | Load CSV, Load JSON |
| FLEET | `#0891B2` | Fleet Definition |
| CONSTRAINT | `#D97706` | Weight, CBM, Time Window, Distance, Battery, Incompatibility, ... |
| ASSEMBLER | `#7C3AED` | Constraint Assembler |
| DESTROY | `#DC2626` | Random Remove, Shaw Remove, Worst Remove, Related Remove |
| REPAIR | `#10B981` | Greedy Insert, Regret-k Insert, 2-Opt* |
| SOLVER | `#8B5CF6` | ALNS, Greedy Construction |
| OUTPUT | `#6B7280` | Route Map, Convergence Chart, Route Table, KPI Summary |

---

## 3. Constraint Framework (3×3)

Every constraint maps to one cell in a 3×3 grid of (arity × aggregation):

|  | **Add** | **Max** | **Scan** |
|---|---------|---------|----------|
| **Unary** (per node) | Weight, CBM, Demand | Max single-item weight | Time Window, Hub Replenish, Battery |
| **Binary** (consecutive pair) | Distance, Travel cost | Max edge weight | Time-Dependent Travel |
| **Any-ary** (arbitrary group) | — | — | Incompatibility (per vehicle type) |

### 3.1 Aggregation semantics

```
Add:   state[d] += delta                    — cumulative, reversible
Max:   state[d]  = max(state[d], delta)     — monotone increasing
Scan:  state[d]  = f(state[d], node, edge)  — arbitrary sequential dependency
```

### 3.2 Solver port mapping (9 color-coded ports)

The **Constraint Assembler** node has 9 input ports, one per grid cell. Each port has a distinct color so users visually know where to connect:

| Port | Arity | Agg | Color | Accepts |
|------|-------|-----|-------|---------|
| `unary_add` | Unary | Add | `#34D399` | Weight, CBM, Demand bundles |
| `unary_max` | Unary | Max | `#FBBF24` | Max single-item bundles |
| `unary_scan` | Unary | Scan | `#F97316` | Time Window, Battery bundles + `@njit` scan_fn |
| `binary_add` | Binary | Add | `#60A5FA` | Distance, Fuel cost bundles |
| `binary_max` | Binary | Max | `#A78BFA` | Max edge weight bundles |
| `binary_scan` | Binary | Scan | `#F472B6` | Time-dependent travel bundles + `@njit` scan_fn |
| `anyary_add` | Any-ary | Add | `#EF4444` | (reserved) |
| `anyary_max` | Any-ary | Max | `#9CA3AF` | (reserved) |
| `anyary_any` | Any-ary | Any | `#E5E7EB` | Incompatibility bundles |

**Stacking**: Multiple constraints of the same type connect to the same port. The assembler stacks them along a new dimension. Example: Weight + CBM both connect to `unary_add` → assembler stacks into `(n, 2)`.

---

## 4. Data Model (100% numpy)

### 4.1 Constraint Bundle

Every constraint node outputs a self-contained **bundle** dict (pure Python wrapper, internal arrays are numpy):

```python
bundle = {
    # Data arrays
    "node_values":  np.ndarray,  # (n,) or (n, n) depending on arity
    "edge_values":  np.ndarray,  # (n, n) for binary, None for unary

    # Per-vehicle bounds and costs
    "upper":        np.ndarray,  # (k,) — upper limit per vehicle type
    "init":         np.ndarray,  # (k,) — initial state per vehicle type
    "cost_w":       np.ndarray,  # (k,) — cost weight per vehicle type
    "penalty_w":    np.ndarray,  # (k,) — penalty weight for soft violations

    # Scan-only (None for add/max)
    "scan_fn":      njit_fn,     # @njit(float64(float64, float64, float64))
}
```

**Soft/Hard constraint**: controlled by `penalty_w`:
- `penalty_w = 0` → hard constraint (infeasible if violated)
- `penalty_w > 0` → soft constraint (cost penalty proportional to violation)

### 4.2 Stacked arrays (after assembly)

The Constraint Assembler stacks all bundles per port into contiguous arrays:

```python
# After assembly — fed to @njit functions
nodes_add:    (n, C_add)         # C_add = number of unary-add constraints
dist_add:     (n, n, D_add)      # D_add = number of binary-add constraints
nodes_max:    (n, C_max)
dist_max:     (n, n, D_max)
nodes_scan:   (n, C_scan)
dist_scan:    (n, n, D_scan)

upper_add:    (k, C_add)
upper_max:    (k, C_max)
upper_scan:   (k, C_scan)

init_add:     (k, C_add)
init_max:     (k, C_max)
init_scan:    (k, C_scan)

cost_w:       (k, C_add + C_max + C_scan)
penalty_w:    (k, C_add + C_max + C_scan)

# Any-ary (incompatibility)
incompat:     (n, n, num_vehicle_types)  # bool matrix per vehicle type

# Scan functions — list of @njit functions, one per scan dimension
scan_fns:     List[@njit]        # len == C_scan
```

### 4.3 Fleet

```python
# Fleet node output
num_vehicles:   int
vehicle_types:  (k,)  int        # maps vehicle → type index
depot:          (k,)  int        # depot node index per vehicle
```

### 4.4 Solution encoding

```python
# Solution = assignment of nodes to routes
route_nodes:    (k, max_route_len)  int   # node IDs per route, -1 = empty slot
route_len:      (k,)                int   # actual length of each route
node_to_route:  (n,)                int   # which route each node belongs to (-1 = unassigned)
```

---

## 5. Constraint Assembler — Compile-Time JIT

The assembler is the performance-critical bridge between modular canvas design and zero-overhead runtime.

### 5.1 Three execution phases

```
Phase 1: COLLECT (pure Python, once per Execute)
├── Read all constraint bundles from input edges
├── Group by constraint class (add/max/scan)
├── Stack arrays into contiguous blocks
└── Collect @njit scan functions

Phase 2: COMPILE (numba JIT, once per workflow change, ~1-2s)
├── Generate evaluate_route() with scan functions baked in
├── Generate compute_cost() wrapping evaluate_route
├── Numba compiles to native code
└── Cache compiled functions (reuse if workflow unchanged)

Phase 3: OUTPUT (pass compiled functions downstream)
├── check_route: @njit (route, route_len, vehicle_id, data) → (bool, int)
├── compute_cost: @njit (route, route_len, vehicle_id, data) → float
└── data: tuple of all stacked numpy arrays
```

### 5.2 evaluate_route — the inner kernel

```python
def assemble_evaluate_route(scan_fns, C_add, C_max, C_scan):
    """Generate a @njit evaluate_route with scan functions baked in at compile time."""

    # Capture scan functions in closure — numba inlines them
    fns = tuple(scan_fns)  # e.g. (time_window_scan, hub_replenish_scan)

    @njit
    def evaluate_route(route, route_len, vehicle_id,
                       nodes_add, dist_add, upper_add, init_add,
                       nodes_max, dist_max, upper_max, init_max,
                       nodes_scan, dist_scan, upper_scan, init_scan):

        state_add  = init_add[vehicle_id].copy()
        state_max  = init_max[vehicle_id].copy()
        state_scan = init_scan[vehicle_id].copy()

        for pos in range(route_len):
            cur  = route[pos]
            prev = route[pos - 1] if pos > 0 else depot[vehicle_id]

            # ── Add dimensions ──
            for d in range(C_add):
                state_add[d] += nodes_add[cur, d] + dist_add[prev, cur, d]
                if state_add[d] > upper_add[vehicle_id, d]:
                    return False, pos

            # ── Max dimensions ──
            for d in range(C_max):
                val = nodes_max[cur, d] + dist_max[prev, cur, d]
                if val > state_max[d]:
                    state_max[d] = val
                if state_max[d] > upper_max[vehicle_id, d]:
                    return False, pos

            # ── Scan dimensions (each function baked in) ──
            # Unrolled per scan dimension at compile time
            if C_scan > 0:
                state_scan[0] = fns[0](state_scan[0],
                                       nodes_scan[cur, 0],
                                       dist_scan[prev, cur, 0])
                if state_scan[0] > upper_scan[vehicle_id, 0]:
                    return False, pos

            if C_scan > 1:
                state_scan[1] = fns[1](state_scan[1],
                                       nodes_scan[cur, 1],
                                       dist_scan[prev, cur, 1])
                if state_scan[1] > upper_scan[vehicle_id, 1]:
                    return False, pos

            # ... pattern continues for each scan dimension

        return True, route_len

    return evaluate_route
```

**Why this works:**
- `fns[i]` are `@njit` functions captured at closure time → LLVM inlines them
- `C_add`, `C_max`, `C_scan` are compile-time constants → dead branches eliminated
- Early exit at every step → skip remaining route on first violation
- Single pass over route → O(route_len) per call, minimal memory

### 5.3 compute_cost

```python
def assemble_compute_cost(evaluate_route, total_dims):

    @njit
    def compute_cost(route, route_len, vehicle_id, data,
                     cost_w, penalty_w, upper_all):
        feasible, final_state = evaluate_route_full(route, route_len, vehicle_id, data)

        cost = 0.0
        for d in range(total_dims):
            if final_state[d] <= upper_all[vehicle_id, d]:
                cost += cost_w[vehicle_id, d] * final_state[d]
            else:
                violation = final_state[d] - upper_all[vehicle_id, d]
                cost += cost_w[vehicle_id, d] * upper_all[vehicle_id, d]
                cost += penalty_w[vehicle_id, d] * violation

        return cost

    return compute_cost
```

### 5.4 Constraint Assembler as PipeStudio node

```python
NODE_INFO = {
    "type": "vrp_constraint_assembler",
    "label": "Constraint Assembler",
    "category": "ASSEMBLER",
    "ports_in": [
        {"name": "unary_add",   "type": "ARRAY"},
        {"name": "unary_max",   "type": "ARRAY"},
        {"name": "unary_scan",  "type": "ARRAY"},
        {"name": "binary_add",  "type": "ARRAY"},
        {"name": "binary_max",  "type": "ARRAY"},
        {"name": "binary_scan", "type": "ARRAY"},
        {"name": "anyary_add",  "type": "ARRAY"},
        {"name": "anyary_max",  "type": "ARRAY"},
        {"name": "anyary_any",  "type": "ARRAY"},
        {"name": "fleet",       "type": "ARRAY"},
    ],
    "ports_out": [
        {"name": "check_route",  "type": "FUNCTION"},
        {"name": "compute_cost", "type": "FUNCTION"},
        {"name": "data",         "type": "ARRAY"},
    ],
}

def run(unary_add, unary_max, unary_scan,
        binary_add, binary_max, binary_scan,
        anyary_add, anyary_max, anyary_any,
        fleet):
    # Phase 1: Stack bundles
    # Phase 2: Compile
    # Phase 3: Return
    check_fn, cost_fn, data = assemble(...)
    return check_fn, cost_fn, data
```

---

## 6. Constraint Nodes — Self-Contained Modules

Each constraint node is a standalone plugin. It receives raw data + fleet info, outputs a bundle.

### 6.1 Example: Weight Constraint (unary-add)

```python
NODE_INFO = {
    "type": "vrp_weight_constraint",
    "label": "Weight",
    "category": "CONSTRAINT",
    "constraint_class": "unary_add",
    "ports_in": [
        {"name": "fleet",     "type": "ARRAY"},
        {"name": "customers", "type": "ARRAY"},
    ],
    "ports_out": [
        {"name": "bundle", "type": "ARRAY"},
    ],
}

def run(fleet, customers):
    n = len(customers)
    k = fleet["num_vehicles"]

    node_values = customers[:, WEIGHT_COL]        # (n,)
    upper       = fleet["capacity_weight"]         # (k,)
    init        = np.zeros(k)                      # start empty
    cost_w      = fleet["cost_per_kg"]             # (k,)
    penalty_w   = np.full(k, 100.0)               # soft, high penalty

    return {
        "node_values": node_values,
        "edge_values": None,
        "upper": upper,
        "init": init,
        "cost_w": cost_w,
        "penalty_w": penalty_w,
        "scan_fn": None,
    }
```

### 6.2 Example: Time Window (unary-scan)

```python
@njit
def time_window_scan(acc, node_val, edge_val):
    """arrival = max(window_open, travel_arrival)"""
    return max(node_val, acc + edge_val)

NODE_INFO = {
    "type": "vrp_time_window",
    "label": "Time Window",
    "category": "CONSTRAINT",
    "constraint_class": "unary_scan",
    "ports_in": [
        {"name": "fleet",     "type": "ARRAY"},
        {"name": "customers", "type": "ARRAY"},
        {"name": "distances", "type": "ARRAY"},
    ],
    "ports_out": [
        {"name": "bundle", "type": "ARRAY"},
    ],
}

def run(fleet, customers, distances):
    node_values = customers[:, TW_OPEN_COL]
    edge_values = distances / fleet["avg_speed"]    # travel time matrix (n, n)
    upper       = customers[:, TW_CLOSE_COL]        # deadline
    # ... assemble bundle with scan_fn = time_window_scan
    return bundle
```

### 6.3 Example: Hub Replenishment (unary-scan)

```python
@njit
def hub_replenish_scan(acc, node_val, edge_val):
    """Reset to 0 at hubs (node_val = -inf for hub nodes)."""
    return max(0.0, acc + node_val)

def run(fleet, customers):
    # hub nodes have weight = -inf → resets accumulator
    node_values = customers[:, WEIGHT_COL].copy()
    hub_mask = customers[:, IS_HUB_COL] == 1
    node_values[hub_mask] = -np.inf
    # ...
```

### 6.4 Example: Battery/Fuel (unary-scan)

```python
@njit
def battery_scan(acc, node_val, edge_val):
    """Charge at nodes (node_val = charge amount), consume on edges."""
    return min(node_val, acc - edge_val)

def run(fleet, customers, distances):
    node_values = customers[:, CHARGE_COL]      # charge amount (0 for non-charging)
    edge_values = distances * fleet["fuel_rate"] # consumption per km
    upper       = fleet["battery_capacity"]
    init        = fleet["battery_capacity"]      # start full
    # ...
```

### 6.5 Example: Incompatibility (any-ary)

```python
NODE_INFO = {
    "type": "vrp_incompatibility",
    "label": "Incompatibility",
    "category": "CONSTRAINT",
    "constraint_class": "anyary_any",
    "ports_in": [
        {"name": "fleet",     "type": "ARRAY"},
        {"name": "customers", "type": "ARRAY"},
    ],
    "ports_out": [
        {"name": "bundle", "type": "ARRAY"},
    ],
}

def run(fleet, customers):
    n = len(customers)
    num_vtypes = fleet["num_vehicle_types"]
    cargo_types = customers[:, CARGO_TYPE_COL]

    # 3D matrix: incompat[i, j, vtype] = True if i,j cannot share route on vtype
    incompat = np.zeros((n, n, num_vtypes), dtype=np.bool_)

    for vt in range(num_vtypes):
        rules = fleet["incompat_rules"][vt]  # list of (cargo_a, cargo_b) pairs
        for ca, cb in rules:
            mask_a = cargo_types == ca
            mask_b = cargo_types == cb
            incompat[np.ix_(mask_a, mask_b, [vt])] = True
            incompat[np.ix_(mask_b, mask_a, [vt])] = True

    return {"incompat": incompat}
```

---

## 7. Fleet Node

Single source of truth for vehicle information.

```python
NODE_INFO = {
    "type": "vrp_fleet",
    "label": "Fleet",
    "category": "FLEET",
    "ports_in": [
        {"name": "data", "type": "ARRAY"},   # raw CSV/JSON
    ],
    "ports_out": [
        {"name": "fleet", "type": "ARRAY"},
    ],
}

def run(data):
    # Parse vehicle definitions from input data
    return {
        "num_vehicles": k,
        "num_vehicle_types": num_types,
        "vehicle_types": np.array([...]),      # (k,) type index
        "depot": np.array([...]),              # (k,) depot node per vehicle
        "capacity_weight": np.array([...]),    # (k,) per vehicle
        "capacity_cbm": np.array([...]),       # (k,)
        "battery_capacity": np.array([...]),   # (k,)
        "cost_per_km": np.array([...]),        # (k,) varies by vehicle type
        "cost_per_kg": np.array([...]),        # (k,)
        "deploy_cost": np.array([...]),        # (k,) fixed cost to use vehicle
        "avg_speed": np.array([...]),          # (k,) for time calculations
        "incompat_rules": [...],               # per vehicle type
    }
```

**Key**: Fleet output is a Python dict (I/O layer). Constraint nodes extract what they need and pack into numpy bundles. Only bundles enter the `@njit` world.

---

## 8. Operator Nodes — Function Registration

Destroy/Repair operators are canvas nodes that **register `@njit` functions** into the solver. They do NOT execute per iteration in the DAG — the solver calls them directly in its tight loop.

### 8.1 Operator interface

Every operator node exports:
```python
NODE_INFO = {
    "type": "vrp_random_remove",
    "label": "Random Remove",
    "category": "DESTROY",
    "operator_role": "destroy",        # or "repair"
    "ports_in": [],
    "ports_out": [
        {"name": "operator", "type": "FUNCTION"},
    ],
}

@njit
def operator_fn(solution, data, rng, params):
    """
    Destroy: remove nodes from solution, return list of removed node IDs.
    Repair: insert unassigned nodes into solution.

    Args:
        solution: (route_nodes, route_len, node_to_route) tuple
        data: all constraint arrays tuple
        rng: numba random state
        params: operator-specific parameters
    Returns:
        modified solution (in-place), removed nodes array
    """
    ...

def run():
    return operator_fn
```

### 8.2 Built-in operators

**Destroy:**
| Node | Strategy |
|------|----------|
| Random Remove | Remove q random nodes |
| Shaw Remove | Remove related nodes (similar location/time/demand) |
| Worst Remove | Remove nodes with highest insertion cost |
| Related Remove | Remove nodes from same route segment |

**Repair:**
| Node | Strategy |
|------|----------|
| Greedy Insert | Insert each node at cheapest feasible position |
| Regret-k Insert | Insert node with largest regret (difference between best and k-th best position) |
| 2-Opt* | Inter-route edge exchange local search |

### 8.3 Custom operators

Users can write custom operator plugins:
```python
# plugins/my_vrp/nodes/custom_destroy.py
from numba import njit

NODE_INFO = {
    "type": "vrp_cluster_remove",
    "label": "Cluster Remove",
    "category": "DESTROY",
    "operator_role": "destroy",
    "ports_in": [],
    "ports_out": [{"name": "operator", "type": "FUNCTION"}],
}

@njit
def operator_fn(solution, data, rng, params):
    # Custom destroy logic
    ...

def run():
    return operator_fn
```

---

## 9. ALNS Solver Node

```python
NODE_INFO = {
    "type": "vrp_alns",
    "label": "ALNS Solver",
    "category": "SOLVER",
    "ports_in": [
        {"name": "check_route",  "type": "FUNCTION"},
        {"name": "compute_cost", "type": "FUNCTION"},
        {"name": "data",         "type": "ARRAY"},
        {"name": "fleet",        "type": "ARRAY"},
        {"name": "destroy_ops",  "type": "FUNCTION"},  # stacked from multiple edges
        {"name": "repair_ops",   "type": "FUNCTION"},   # stacked from multiple edges
        {"name": "iterations",   "type": "NUMBER", "default": 10000},
        {"name": "init_temp",    "type": "NUMBER", "default": 100.0},
        {"name": "cool_rate",    "type": "NUMBER", "default": 0.9997},
    ],
    "ports_out": [
        {"name": "solution", "type": "ARRAY"},
        {"name": "cost",     "type": "NUMBER"},
        {"name": "history",  "type": "ARRAY"},
        {"name": "routes",   "type": "ARRAY"},
    ],
}
```

### 9.1 ALNS loop (inside solver, all @njit)

```python
@njit
def alns_solve(check_route, compute_cost, data, fleet,
               destroy_fns, repair_fns, iterations, init_temp, cool_rate):

    # --- Initial solution (greedy construction) ---
    solution = greedy_construct(check_route, compute_cost, data, fleet)
    best = copy_solution(solution)
    best_cost = total_cost(compute_cost, solution, data)

    # --- Adaptive weights ---
    n_destroy = len(destroy_fns)
    n_repair = len(repair_fns)
    d_weights = np.ones(n_destroy)
    r_weights = np.ones(n_repair)

    history = np.empty(iterations)
    temperature = init_temp

    for i in range(iterations):
        # Pick operators (roulette wheel)
        d_idx = roulette_pick(d_weights, rng)
        r_idx = roulette_pick(r_weights, rng)

        # Destroy
        trial = copy_solution(solution)
        removed = destroy_fns[d_idx](trial, data, rng, params)

        # Repair (calls check_route internally for feasibility)
        repair_fns[r_idx](trial, removed, check_route, compute_cost, data, rng, params)

        # Evaluate
        trial_cost = total_cost(compute_cost, trial, data)

        # Accept (simulated annealing)
        if accept_sa(trial_cost, best_cost, temperature, rng):
            solution = trial
            if trial_cost < best_cost:
                best = copy_solution(trial)
                best_cost = trial_cost
                update_weights(d_weights, r_weights, d_idx, r_idx, REWARD_BEST)
            else:
                update_weights(d_weights, r_weights, d_idx, r_idx, REWARD_ACCEPT)
        else:
            update_weights(d_weights, r_weights, d_idx, r_idx, REWARD_REJECT)

        history[i] = best_cost
        temperature *= cool_rate

    return best, best_cost, history
```

---

## 10. Output & Visualization Nodes

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| Route Map | solution, fleet, customers | svg (STRING) | Geographic route visualization |
| Convergence Chart | history | svg (STRING) | Cost vs iteration plot |
| Route Table | solution, fleet, customers | text (STRING) | Per-route detail table |
| KPI Summary | solution, fleet, cost | text (STRING) | Vehicles used, total distance, utilization %, violations |

---

## 11. Separation of Concerns

```
┌────────────────────────────────────────────────────────────┐
│                    I/O Layer (pure Python)                  │
│  Load CSV, Fleet, Constraint Nodes, Visualization Nodes    │
│  - Parse files, build dicts, generate SVG/HTML             │
│  - OK to use pandas, json, etc.                            │
└──────────────────────┬─────────────────────────────────────┘
                       │ numpy arrays + @njit functions
                       ▼
┌────────────────────────────────────────────────────────────┐
│              Assembly Layer (pure Python, runs once)        │
│  Constraint Assembler                                      │
│  - Stack bundles into contiguous arrays                    │
│  - Compile evaluate_route / compute_cost via numba JIT     │
│  - ~1-2s compile time, cached if workflow unchanged        │
└──────────────────────┬─────────────────────────────────────┘
                       │ compiled @njit functions + data tuple
                       ▼
┌────────────────────────────────────────────────────────────┐
│              Compute Layer (100% @njit)                     │
│  ALNS loop, Greedy Construction, Local Search              │
│  evaluate_route, compute_cost                              │
│  Destroy/Repair operators                                  │
│  - Zero Python overhead                                    │
│  - All arrays contiguous, cache-friendly                   │
│  - Scan functions inlined by LLVM                          │
│  - Millions of iterations per second                       │
└────────────────────────────────────────────────────────────┘
```

**Rule**: Data crosses the I/O → Compute boundary exactly once (at assembly time). After that, everything is numpy arrays and `@njit` functions. No Python objects, no dicts, no lists in the hot path.

---

## 12. Extensibility

### Adding a new constraint

1. Create `plugins/vrp/nodes/my_constraint.py`
2. Define `NODE_INFO` with `constraint_class` matching one of the 9 ports
3. For scan types: write `@njit def scan_fn(acc, node_val, edge_val) → float`
4. Implement `run()` that returns a bundle dict
5. Done — drag node onto canvas, connect to assembler

**No changes to**: assembler, solver, other constraints, frontend

### Adding a new operator

1. Create `plugins/vrp/nodes/my_operator.py`
2. Define `NODE_INFO` with `operator_role: "destroy"` or `"repair"`
3. Write `@njit def operator_fn(solution, data, rng, params)`
4. Implement `run()` that returns the function
5. Done — drag node onto canvas, connect to solver

**No changes to**: solver loop, other operators, constraint system

### Adding a new solver

1. Create `plugins/vrp/nodes/my_solver.py`
2. Accept `check_route`, `compute_cost`, `data` as inputs (same interface)
3. Implement solving logic using those functions
4. Done — swap ALNS node for new solver on canvas

**No changes to**: constraints, assembler, operators

---

## 13. Plugin File Structure

```
plugins/
└── vrp/
    ├── manifest.json
    └── nodes/
        ├── # ── DATA ──
        ├── load_csv.py
        ├── load_json.py
        │
        ├── # ── FLEET ──
        ├── fleet.py
        │
        ├── # ── CONSTRAINTS ──
        ├── weight_constraint.py        # unary-add
        ├── cbm_constraint.py           # unary-add
        ├── demand_constraint.py        # unary-add
        ├── time_window.py              # unary-scan
        ├── hub_replenish.py            # unary-scan
        ├── battery.py                  # unary-scan
        ├── distance_cost.py            # binary-add
        ├── time_dependent_travel.py    # binary-scan
        ├── incompatibility.py          # anyary-any
        │
        ├── # ── ASSEMBLER ──
        ├── constraint_assembler.py
        │
        ├── # ── DESTROY OPERATORS ──
        ├── random_remove.py
        ├── shaw_remove.py
        ├── worst_remove.py
        ├── related_remove.py
        │
        ├── # ── REPAIR OPERATORS ──
        ├── greedy_insert.py
        ├── regret_insert.py
        ├── two_opt_star.py
        │
        ├── # ── SOLVERS ──
        ├── alns_solver.py
        ├── greedy_construction.py
        │
        └── # ── VISUALIZATION ──
            ├── route_map.py
            ├── convergence_chart.py
            ├── route_table.py
            └── kpi_summary.py
```

---

## 14. Example Canvas Workflow

**CVRP (Capacitated VRP):**
```
[Load CSV] → [Fleet] → [Weight] → [Assembler] → [ALNS] → [Route Map]
                    └→ [Distance Cost] →  ↑        ↑  ↑ → [KPI Summary]
                                    [Random Remove] ┘  │
                                    [Shaw Remove] ──────┘
                                    [Greedy Insert] ────┘
                                    [Regret Insert] ────┘
```

**VRPTW (VRP with Time Windows):**
```
Same as CVRP, plus:
[Fleet] → [Time Window] → Assembler's unary_scan port
```

**Rich VRP (everything):**
```
Same as VRPTW, plus:
[Fleet] → [CBM] → Assembler's unary_add port
[Fleet] → [Battery] → Assembler's unary_scan port
[Fleet] → [Incompatibility] → Assembler's anyary_any port
```

Each variant is the same workflow with more/fewer constraint nodes connected.

---

## 15. Industry Comparison & Lessons Learned

Research into existing VRP solvers informed several design refinements.

### 15.1 Google OR-Tools — Dimension pattern

OR-Tools models constraints as **Dimensions** with the recurrence:

```
cumul(j) = cumul(i) + transit(i,j) + slack(i)
```

- `cumul` = accumulated state (weight, time, distance)
- `transit` = change between consecutive nodes
- `slack` = waiting time (non-negative), used for time windows
- Each dimension has per-vehicle capacity via `AddDimensionWithVehicleCapacity`

**Lesson**: OR-Tools only supports **additive** accumulation (`cumul += transit + slack`). Time windows require the `slack` hack — a variable that "absorbs" early arrival. Our 3×3 framework (add/max/scan) is strictly more general. However, OR-Tools' `slack` concept is useful: when a vehicle arrives early at a time window, the waiting time has a cost. We should track slack as an implicit output of scan constraints for cost computation.

**Applied**: Scan constraints now return `(new_state, slack)` tuple. `slack = max(0, window_open - arrival)`. The assembler tracks accumulated slack per scan dimension, and `compute_cost` can penalize total waiting time.

### 15.2 PyVRP — C++ hot path + Python shell

PyVRP ranked #1 in DIMACS 2021 VRPTW challenge and EURO-NeurIPS 2022 competition. Architecture:

- **C++ core**: `Route` evaluation, `CostEvaluator`, local search operators, population management
- **Python shell**: problem setup, configuration, result analysis
- Adding a new VRP variant requires modifying C++ `Client` class and `CostEvaluator`, then updating Python bindings

**Lesson**: PyVRP achieves peak performance by implementing route evaluation in C++, but at the cost of extensibility — every new constraint requires C++ changes, recompilation, and binding updates. Our numba approach trades ~2-5x raw speed for dramatically better extensibility: new constraints are pure Python plugin files that get JIT-compiled. For most practical VRP instances (< 10,000 nodes), this tradeoff is favorable.

**Applied**: We maintain strict layering so that future C++ migration of the compute layer is possible without changing the I/O or assembly layers. The `check_route` / `compute_cost` interface is the migration boundary.

### 15.3 ALNS Library (N-Wouda) — Operator registration

The `alns` Python library provides a clean operator interface:

```python
# Operator signature
def destroy(state, rng) -> state
def repair(state, rng) -> state

# Registration
alns = ALNS(rng)
alns.add_destroy_operator(random_remove)
alns.add_destroy_operator(worst_remove)
alns.add_repair_operator(greedy_insert)

# Selection & acceptance
select = SegmentedRouletteWheel(
    scores=[5, 2, 1, 0.5],  # new_best, better, accepted, rejected
    decay=0.8,
    seg_length=500
)
accept = RecordToRecordTravel(
    start_threshold=255, end_threshold=5,
    step=250/10_000, method="linear"
)
res = alns.iterate(init_sol, select, accept, MaxIterations(10_000))
```

**Lessons applied**:

1. **Segmented Roulette Wheel** with 4-tier scoring `[σ₁, σ₂, σ₃, σ₄]` — better than simple weight increment. Scores update every `seg_length` iterations, weights decay by factor `λ`. This prevents stale operators from dominating.

2. **Record-to-Record Travel** acceptance — simpler than Simulated Annealing, often performs equally well. Accept if `cost(candidate) < cost(best) + threshold`, where threshold decreases linearly. We offer both SA and RRT as configurable acceptance criteria.

3. **Operator signature simplicity** — their `(state, rng) → state` is clean. Our `@njit` version adds `data` and `params` but maintains the same simplicity.

### 15.4 VROOM — Speed-first heuristic

VROOM solves VRP in milliseconds using C++20 with constructive heuristics + local search (no metaheuristic). Focus: real-time, production API.

**Lesson**: For simple VRP variants, a fast heuristic initial solution is often "good enough." Our Greedy Construction node serves this role — it can be used standalone (without ALNS) for quick solutions, or as the ALNS initial solution.

### 15.5 Recent research (2025-2026)

- **Parallel ALNS** on Spark achieved 3-5x speedup via parallel destroy/repair evaluation
- **RL-guided ALNS** (PPO-ALNS) treats operator selection as MDP, achieving 11-17% improvements on complex instances
- **VAE-guided ALNS** uses deep generative models to learn routing patterns for neighborhood selection

**Applied**: Our architecture supports future parallelism — the `check_route` and `compute_cost` functions are stateless and can be called from multiple threads. The operator selection mechanism (Segmented Roulette Wheel) can be swapped for RL-based selection in a future plugin node.

---

## 16. Design Refinements from Research

### 16.1 Slack tracking for scan constraints

**Before**: Scan returns only `new_state`.
**After**: `evaluate_route` also computes slack per scan dimension.

```python
# Inside evaluate_route, after scan update:
raw_arrival = state_scan[d]  # before scan_fn
state_scan[d] = fns[d](state_scan[d], nodes_scan[cur, d], dist_scan[prev, cur, d])
slack_scan[d] += max(0.0, state_scan[d] - raw_arrival)  # waiting time
```

This enables waiting cost in `compute_cost` without requiring a separate constraint.

### 16.2 Acceptance criteria as configurable parameter

ALNS Solver node adds acceptance criterion config:

```python
# Additional ports_in for ALNS Solver:
{"name": "acceptance", "type": "STRING", "default": "sa"},
# Options: "sa" (Simulated Annealing), "rrt" (Record-to-Record Travel)
{"name": "rrt_start_threshold", "type": "NUMBER", "default": 0.05},
{"name": "rrt_end_threshold",   "type": "NUMBER", "default": 0.0},
```

### 16.3 Segmented Roulette Wheel operator selection

Replace simple weight update with segmented approach:

```python
# Operator selection parameters (ALNS Solver config)
{"name": "score_best",     "type": "NUMBER", "default": 5},
{"name": "score_better",   "type": "NUMBER", "default": 2},
{"name": "score_accepted",  "type": "NUMBER", "default": 1},
{"name": "score_rejected",  "type": "NUMBER", "default": 0.5},
{"name": "weight_decay",    "type": "NUMBER", "default": 0.8},
{"name": "segment_length",  "type": "NUMBER", "default": 500},
```

Weights reset every `segment_length` iterations:
```
w_new = decay * w_old + (1 - decay) * (score_sum / times_used)
```

### 16.4 Future C++ migration path

The 3-layer architecture enables incremental migration:

```
Phase 1 (now):    I/O Python  →  Assembly Python  →  Compute @njit
Phase 2 (future): I/O Python  →  Assembly Python  →  Compute C++ (.pyd)
Phase 3 (future): I/O Python  →  Assembly C++     →  Compute C++
```

The `check_route` / `compute_cost` / operator function signatures are the stable interface. Replacing numba with C++ extensions requires zero changes to I/O layer, constraint nodes, or canvas architecture.

---

## 17. Summary of Competitive Advantages

| Aspect | OR-Tools | PyVRP | VROOM | Our Design |
|--------|----------|-------|-------|------------|
| **Constraint model** | Additive only (cumul + transit + slack) | Fixed C++ types | Fixed C++ types | 3×3 grid (add/max/scan) × (unary/binary/any-ary) |
| **Adding constraints** | API calls, same process | C++ code changes + rebuild | C++ code changes + rebuild | Drag & drop plugin node |
| **Performance** | C++ native | C++ native (#1 DIMACS) | C++ native (milliseconds) | @njit (~2-5x slower than C++) |
| **Extensibility** | Medium (API-driven) | Low (C++ required) | Low (C++ required) | High (Python plugins) |
| **Visual workflow** | No | No | No | Yes (PipeStudio canvas) |
| **Soft constraints** | Disjunctions/penalties | CostEvaluator penalties | No | penalty_w per dimension |
| **Custom operators** | No | Subclass in C++ | No | @njit plugin nodes |
| **Custom scan functions** | No | No | No | @njit baked at compile time |

Sources:
- [OR-Tools Dimensions](https://developers.google.com/optimization/routing/dimensions)
- [OR-Tools VRP](https://developers.google.com/optimization/routing/vrp)
- [PyVRP Paper (arXiv)](https://arxiv.org/abs/2403.13795)
- [PyVRP Adding New Variants](https://pyvrp.org/dev/new_vrp_variants.html)
- [ALNS Library](https://github.com/N-Wouda/ALNS)
- [ALNS Features & Examples](https://alns.readthedocs.io/en/latest/examples/alns_features.html)
- [VROOM Project](https://github.com/VROOM-Project/vroom)
- [OR-Tools Routing Solver Paper](https://hal.science/hal-04015496/document)
- [Parallel ALNS on Spark](https://www.nature.com/articles/s41598-024-74432-2)
- [RL-guided ALNS (PPO-ALNS)](https://dl.acm.org/doi/10.1007/s10878-025-01364-6)
