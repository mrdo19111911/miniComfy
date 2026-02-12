# VRP Solver — Implementation Plan (Milestone 1 + 2)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** End-to-end working VRP solver with CVRP (Weight constraint + Distance cost) — from Load Data to Route Map visualization.

**Architecture:** Three-layer system (I/O → Assembly → Compute). Constraint nodes output bundles, Constraint Assembler stacks & JIT-compiles check_route/compute_cost, ALNS Solver uses compiled functions in @njit loop. Multi-edge stacking enables multiple constraints into same assembler port.

**Tech Stack:** Python 3.10+, NumPy, Numba, FastAPI (existing PipeStudio backend), React/ReactFlow (existing frontend)

**Design doc:** `docs/plans/2026-02-12-vrp-solver-design.md`

---

## Phase 1: Infrastructure (Tasks 1-5)

### Task 1: FUNCTION port type support (frontend)

**Files:**
- Modify: `frontend/src/constants.ts` (portColor function, line 57-68)

**Step 1: Add FUNCTION case to portColor**

```typescript
export function portColor(type: string): string {
  switch (type) {
    case 'ARRAY':
      return '#34D399';
    case 'NUMBER':
      return '#FBBF24';
    case 'STRING':
      return '#A78BFA';
    case 'FUNCTION':
      return '#EC4899';
    default:
      return '#9CA3AF';
  }
}
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Clean build, zero errors

**Step 3: Commit**

```bash
git add frontend/src/constants.ts
git commit -m "feat: add FUNCTION port type with pink color"
```

---

### Task 2: Multi-edge stacking in executor

**Files:**
- Test: `tests/test_multi_edge.py` (CREATE)
- Modify: `pipestudio/executor.py` (method `_get_node_inputs`)

**Step 1: Write the failing test**

```python
"""Tests for multi-edge stacking: multiple edges into same input port."""
import numpy as np
import pytest
from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS, register_node

# --- Inline test plugins ---

SOURCE_A_INFO = {
    "type": "test_source_a",
    "label": "Source A",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "ARRAY", "required": True}],
}

SOURCE_B_INFO = {
    "type": "test_source_b",
    "label": "Source B",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "ARRAY", "required": True}],
}

STACKER_INFO = {
    "type": "test_stacker",
    "label": "Stacker",
    "category": "TEST",
    "ports_in": [{"name": "items", "type": "ARRAY", "required": True}],
    "ports_out": [{"name": "result", "type": "ARRAY", "required": True}],
}


def source_a_exec(params, **inputs):
    return {"out": np.array([1.0, 2.0, 3.0])}


def source_b_exec(params, **inputs):
    return {"out": np.array([4.0, 5.0, 6.0])}


def stacker_exec(params, **inputs):
    items = inputs.get("items")
    if isinstance(items, list):
        return {"result": np.array(items, dtype=object)}
    return {"result": items}


@pytest.fixture(autouse=True)
def _register(tmp_path):
    register_node(SOURCE_A_INFO, source_a_exec)
    register_node(SOURCE_B_INFO, source_b_exec)
    register_node(STACKER_INFO, stacker_exec)
    yield
    for t in ["test_source_a", "test_source_b", "test_stacker"]:
        _NODE_REGISTRY.pop(t, None)
        _EXECUTORS.pop(t, None)


def test_multi_edge_stacks_into_list():
    """Two edges into same input port should produce a list of values."""
    from pipestudio.executor import WorkflowExecutor
    from pipestudio.models import WorkflowDefinition, WorkflowNode, WorkflowEdge

    wf = WorkflowDefinition(
        nodes=[
            WorkflowNode(id="a", type="test_source_a", params={}),
            WorkflowNode(id="b", type="test_source_b", params={}),
            WorkflowNode(id="s", type="test_stacker", params={}),
        ],
        edges=[
            WorkflowEdge(source="a", source_port="out", target="s", target_port="items"),
            WorkflowEdge(source="b", source_port="out", target="s", target_port="items"),
        ],
    )

    results = {}
    executor = WorkflowExecutor()
    for event in executor.execute(wf):
        if event.get("event") == "node_complete":
            results[event["node_id"]] = event.get("outputs", {})

    stacker_result = results["s"]["result"]
    # Should be a list (or object array) of two numpy arrays
    assert isinstance(stacker_result, (list, np.ndarray))
    if isinstance(stacker_result, np.ndarray):
        assert stacker_result.dtype == object
        assert len(stacker_result) == 2
    else:
        assert len(stacker_result) == 2


def test_single_edge_no_wrapping():
    """Single edge into a port should NOT produce a list — just the value."""
    from pipestudio.executor import WorkflowExecutor
    from pipestudio.models import WorkflowDefinition, WorkflowNode, WorkflowEdge

    wf = WorkflowDefinition(
        nodes=[
            WorkflowNode(id="a", type="test_source_a", params={}),
            WorkflowNode(id="s", type="test_stacker", params={}),
        ],
        edges=[
            WorkflowEdge(source="a", source_port="out", target="s", target_port="items"),
        ],
    )

    results = {}
    executor = WorkflowExecutor()
    for event in executor.execute(wf):
        if event.get("event") == "node_complete":
            results[event["node_id"]] = event.get("outputs", {})

    stacker_input = results["s"]["result"]
    # Single edge → value passed directly, not wrapped in list
    assert isinstance(stacker_input, np.ndarray)
    assert len(stacker_input) == 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_multi_edge.py -v`
Expected: FAIL — `test_multi_edge_stacks_into_list` fails because second edge overwrites first

**Step 3: Modify `_get_node_inputs` to support stacking**

In `pipestudio/executor.py`, replace `_get_node_inputs`:

```python
def _get_node_inputs(self, node_id: str, edges: List[WorkflowEdge]) -> Dict[str, Any]:
    """Collect inputs for a node from upstream outputs.

    If multiple edges target the same port, values are collected into a list.
    Single-edge ports receive the value directly (no wrapping).
    """
    edge_stacks: Dict[str, list] = {}
    for e in edges:
        if e.is_back_edge:
            continue
        if e.target == node_id and e.source in self.node_outputs:
            source_outputs = self.node_outputs[e.source]
            if e.source_port in source_outputs:
                if e.target_port not in edge_stacks:
                    edge_stacks[e.target_port] = []
                edge_stacks[e.target_port].append(source_outputs[e.source_port])

    inputs: Dict[str, Any] = {}
    for port_name, values in edge_stacks.items():
        inputs[port_name] = values[0] if len(values) == 1 else values
    return inputs
```

**Step 4: Run tests to verify pass**

Run: `pytest tests/test_multi_edge.py -v`
Expected: PASS (both tests)

Run: `pytest tests/ -v`
Expected: ALL existing tests still pass (single-edge behavior unchanged)

**Step 5: Commit**

```bash
git add tests/test_multi_edge.py pipestudio/executor.py
git commit -m "feat: multi-edge stacking — multiple edges to same port produce list"
```

---

### Task 3: FUNCTION port data summary in executor

**Files:**
- Modify: `pipestudio/executor.py` (method `_summarize_data`)

Currently `_summarize_data` handles arrays and scalars. Callables will crash or display poorly. Need to handle them gracefully.

**Step 1: Write the failing test**

Add to `tests/test_multi_edge.py`:

```python
def test_function_port_passes_callable():
    """A FUNCTION port should pass callable objects between nodes."""
    from pipestudio.plugin_api import register_node

    FUNC_PRODUCER_INFO = {
        "type": "test_func_producer",
        "label": "Func Producer",
        "category": "TEST",
        "ports_in": [],
        "ports_out": [{"name": "func", "type": "FUNCTION", "required": True}],
    }

    FUNC_CONSUMER_INFO = {
        "type": "test_func_consumer",
        "label": "Func Consumer",
        "category": "TEST",
        "ports_in": [
            {"name": "func", "type": "FUNCTION", "required": True},
            {"name": "data", "type": "ARRAY", "required": True},
        ],
        "ports_out": [{"name": "result", "type": "ARRAY", "required": True}],
    }

    def my_transform(arr):
        return arr * 2

    def producer_exec(params, **inputs):
        return {"func": my_transform}

    def consumer_exec(params, **inputs):
        fn = inputs["func"]
        data = inputs["data"]
        return {"result": fn(data)}

    register_node(FUNC_PRODUCER_INFO, producer_exec)
    register_node(FUNC_CONSUMER_INFO, consumer_exec)

    try:
        from pipestudio.executor import WorkflowExecutor
        from pipestudio.models import WorkflowDefinition, WorkflowNode, WorkflowEdge

        wf = WorkflowDefinition(
            nodes=[
                WorkflowNode(id="a", type="test_source_a", params={}),
                WorkflowNode(id="fp", type="test_func_producer", params={}),
                WorkflowNode(id="fc", type="test_func_consumer", params={}),
            ],
            edges=[
                WorkflowEdge(source="fp", source_port="func", target="fc", target_port="func"),
                WorkflowEdge(source="a", source_port="out", target="fc", target_port="data"),
            ],
        )

        results = {}
        executor = WorkflowExecutor()
        for event in executor.execute(wf):
            if event.get("event") == "node_complete":
                results[event["node_id"]] = event.get("outputs", {})

        result = results["fc"]["result"]
        expected = np.array([2.0, 4.0, 6.0])
        np.testing.assert_array_equal(result, expected)
    finally:
        _NODE_REGISTRY.pop("test_func_producer", None)
        _EXECUTORS.pop("test_func_producer", None)
        _NODE_REGISTRY.pop("test_func_consumer", None)
        _EXECUTORS.pop("test_func_consumer", None)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_multi_edge.py::test_function_port_passes_callable -v`
Expected: May PASS already (since executor is type-erasing) OR fail on `_summarize_data` crash

**Step 3: Update `_summarize_data` to handle callables**

In `pipestudio/executor.py`, find `_summarize_data` and add callable handling:

```python
# Add at the beginning of _summarize_data:
if callable(value):
    name = getattr(value, '__name__', type(value).__name__)
    return {"_type": "function", "name": name}
```

**Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL pass

**Step 5: Commit**

```bash
git add pipestudio/executor.py tests/test_multi_edge.py
git commit -m "feat: FUNCTION port support — callables pass between nodes, summary display"
```

---

### Task 4: VRP plugin project scaffold

**Files:**
- Create: `plugins/vrp/manifest.json`
- Create: `plugins/vrp/nodes/` (empty directory with __init__.py placeholder)

**Step 1: Create manifest**

```json
{
  "name": "vrp",
  "label": "VRP Solver",
  "description": "Vehicle Routing Problem solver with modular constraints and ALNS optimization",
  "version": "0.1.0",
  "author": "PipeStudio",
  "categories": {
    "DATA": "#2563EB",
    "FLEET": "#0891B2",
    "CONSTRAINT": "#D97706",
    "ASSEMBLER": "#7C3AED",
    "DESTROY": "#DC2626",
    "REPAIR": "#10B981",
    "SOLVER": "#8B5CF6",
    "OUTPUT": "#6B7280"
  }
}
```

**Step 2: Verify plugin is discovered**

Run: `python -c "from pipestudio.plugin_loader import load_all_plugins; load_all_plugins(); print('OK')"`
Expected: No errors (empty nodes/ is fine)

**Step 3: Commit**

```bash
git add plugins/vrp/
git commit -m "feat: VRP plugin project scaffold with manifest"
```

---

### Task 5: Generate sample CVRP data node

**Files:**
- Create: `plugins/vrp/nodes/generate_cvrp.py`
- Test: `tests/test_vrp_generate.py` (CREATE)

This node generates random CVRP test data (customers with coordinates + demands, depot, fleet definition). Used for development and testing — replaces Load CSV for now.

**Step 1: Write the failing test**

```python
"""Tests for VRP Generate CVRP node."""
import numpy as np
import pytest
from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS


def test_generate_cvrp_registered():
    """Node should be discoverable after plugin load."""
    from pipestudio.plugin_loader import load_all_plugins
    load_all_plugins()
    assert "vrp_generate_cvrp" in _NODE_REGISTRY


def test_generate_cvrp_output_shapes():
    """Output arrays should have correct shapes."""
    from pipestudio.plugin_loader import load_all_plugins
    load_all_plugins()
    executor = _EXECUTORS["vrp_generate_cvrp"]

    result = executor({"num_customers": 20, "num_vehicles": 3}, )

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
    from pipestudio.plugin_loader import load_all_plugins
    load_all_plugins()
    executor = _EXECUTORS["vrp_generate_cvrp"]

    r1 = executor({"num_customers": 10, "num_vehicles": 2, "seed": 42})
    r2 = executor({"num_customers": 10, "num_vehicles": 2, "seed": 42})

    np.testing.assert_array_equal(r1["customers"], r2["customers"])
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_vrp_generate.py -v`
Expected: FAIL — node not registered

**Step 3: Implement generate_cvrp.py**

```python
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
        {"name": "customers", "type": "ARRAY", "required": True},
        {"name": "fleet", "type": "ARRAY", "required": True},
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
```

**Step 4: Run tests**

Run: `pytest tests/test_vrp_generate.py -v`
Expected: ALL pass

Run: `pytest tests/ -v`
Expected: ALL pass (no regressions)

**Step 5: Commit**

```bash
git add plugins/vrp/nodes/generate_cvrp.py tests/test_vrp_generate.py
git commit -m "feat: VRP Generate CVRP node — random test instance generator"
```

---

## Phase 2: Constraint System (Tasks 6-8)

### Task 6: Weight Constraint node

**Files:**
- Create: `plugins/vrp/nodes/weight_constraint.py`
- Test: `tests/test_vrp_constraints.py` (CREATE)

**Step 1: Write the failing test**

```python
"""Tests for VRP constraint nodes."""
import numpy as np
import pytest
from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS


@pytest.fixture(autouse=True)
def _load_plugins():
    from pipestudio.plugin_loader import load_all_plugins
    load_all_plugins()


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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_vrp_constraints.py::test_weight_constraint_registered -v`
Expected: FAIL

**Step 3: Implement weight_constraint.py**

```python
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
        {"name": "bundle", "type": "ARRAY", "required": True},
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
```

**Step 4: Run tests**

Run: `pytest tests/test_vrp_constraints.py -v`
Expected: ALL pass

**Step 5: Commit**

```bash
git add plugins/vrp/nodes/weight_constraint.py tests/test_vrp_constraints.py
git commit -m "feat: VRP Weight Constraint node — unary-add bundle"
```

---

### Task 7: Distance Cost node

**Files:**
- Create: `plugins/vrp/nodes/distance_cost.py`
- Modify: `tests/test_vrp_constraints.py` (add tests)

**Step 1: Write the failing test**

Add to `tests/test_vrp_constraints.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_vrp_constraints.py::test_distance_cost_registered -v`
Expected: FAIL

**Step 3: Implement distance_cost.py**

```python
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
        {"name": "bundle", "type": "ARRAY", "required": True},
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
```

**Step 4: Run tests**

Run: `pytest tests/test_vrp_constraints.py -v`
Expected: ALL pass

**Step 5: Commit**

```bash
git add plugins/vrp/nodes/distance_cost.py tests/test_vrp_constraints.py
git commit -m "feat: VRP Distance Cost node — binary-add bundle with Euclidean matrix"
```

---

### Task 8: Constraint Assembler node

**Files:**
- Create: `plugins/vrp/nodes/constraint_assembler.py`
- Test: `tests/test_vrp_assembler.py` (CREATE)

This is the performance-critical node that stacks bundles and JIT-compiles check_route / compute_cost.

**Step 1: Write the failing test**

```python
"""Tests for VRP Constraint Assembler."""
import numpy as np
import pytest
from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS


@pytest.fixture(autouse=True)
def _load_plugins():
    from pipestudio.plugin_loader import load_all_plugins
    load_all_plugins()


def test_assembler_registered():
    assert "vrp_constraint_assembler" in _NODE_REGISTRY


def test_assembler_with_weight_only():
    """Assembler with single weight constraint should produce working check_route."""
    assembler = _EXECUTORS["vrp_constraint_assembler"]

    n, k = 5, 2
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
        "num_vehicles": k,
        "depot": np.zeros(k, dtype=np.int64),
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

    n = 3
    k = 1
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

    fleet = {"num_vehicles": k, "depot": np.zeros(k, dtype=np.int64)}

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

    n, k = 3, 1
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

    fleet = {"num_vehicles": k, "depot": np.zeros(k, dtype=np.int64)}

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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_vrp_assembler.py -v`
Expected: FAIL

**Step 3: Implement constraint_assembler.py**

This is the most complex node. Implementation should:
1. Accept bundles (single or list) from each of 9 ports
2. Stack arrays
3. Generate `@njit` check_route and compute_cost

```python
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
        {"name": "check_route", "type": "FUNCTION", "required": True},
        {"name": "compute_cost", "type": "FUNCTION", "required": True},
        {"name": "data", "type": "ARRAY", "required": True},
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
    """Stack bundles into contiguous arrays."""
    if not bundles:
        if has_edges:
            return np.zeros((n, n, 0)), np.zeros((k, 0)), np.zeros((k, 0)), np.zeros((k, 0)), np.zeros((k, 0))
        return np.zeros((n, 0)), np.zeros((k, 0)), np.zeros((k, 0)), np.zeros((k, 0)), np.zeros((k, 0))

    if has_edges:
        values = np.stack([b["edge_values"] for b in bundles], axis=-1)
    else:
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
    for bundles_raw in [unary_add, unary_max, unary_scan, binary_add, binary_max, binary_scan]:
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

    nodes_add, upper_add, init_add, cost_w_add, pen_w_add = _stack_bundles(ua_bundles, n, k, False)
    dist_add, upper_dist, init_dist, cost_w_dist, pen_w_dist = _stack_bundles(ba_bundles, n, k, True)

    C_add = nodes_add.shape[1] if nodes_add.ndim == 2 else 0
    D_add = dist_add.shape[2] if dist_add.ndim == 3 else 0

    # Merge upper/init/cost_w/penalty_w across all dimension types
    all_upper = np.hstack([upper_add, upper_dist]) if C_add + D_add > 0 else np.zeros((k, 0))
    all_init = np.hstack([init_add, init_dist]) if C_add + D_add > 0 else np.zeros((k, 0))
    all_cost_w = np.hstack([cost_w_add, cost_w_dist]) if C_add + D_add > 0 else np.zeros((k, 0))
    all_pen_w = np.hstack([pen_w_add, pen_w_dist]) if C_add + D_add > 0 else np.zeros((k, 0))

    # Pack data tuple
    data = (depot, nodes_add, dist_add, all_upper, all_init, all_cost_w, all_pen_w)

    # Compile check_route
    _C_add = C_add
    _D_add = D_add

    @njit
    def check_route(route, route_len, vehicle_id, data_tuple):
        depot_arr, nodes_add_arr, dist_add_arr, upper, init, cost_w, pen_w = data_tuple

        total_dims = upper.shape[1]
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

    @njit
    def compute_cost(route, route_len, vehicle_id, data_tuple):
        depot_arr, nodes_add_arr, dist_add_arr, upper, init, cost_w, pen_w = data_tuple

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
```

**Step 4: Run tests**

Run: `pytest tests/test_vrp_assembler.py -v`
Expected: ALL pass

Run: `pytest tests/ -v`
Expected: ALL pass

**Step 5: Commit**

```bash
git add plugins/vrp/nodes/constraint_assembler.py tests/test_vrp_assembler.py
git commit -m "feat: VRP Constraint Assembler — stacks bundles, JIT-compiles check_route/compute_cost"
```

---

## Phase 3: Solver (Tasks 9-11)

### Task 9: Greedy Construction solver

**Files:**
- Create: `plugins/vrp/nodes/greedy_construction.py`
- Test: `tests/test_vrp_solver.py` (CREATE)

Greedy insertion: for each unassigned customer, find cheapest feasible insertion position across all routes.

**Step 1: Write the failing test**

```python
"""Tests for VRP solver nodes."""
import numpy as np
import pytest
from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS


@pytest.fixture(autouse=True)
def _load_plugins():
    from pipestudio.plugin_loader import load_all_plugins
    load_all_plugins()


def _make_simple_problem():
    """Create a small CVRP: 5 customers, 2 vehicles, capacity 30."""
    n, k = 5, 2
    # customers: depot + 5 customers
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_vrp_solver.py::test_greedy_construction_registered -v`
Expected: FAIL

**Step 3: Implement greedy_construction.py**

```python
"""Greedy construction — insert customers one by one at cheapest feasible position."""
import numpy as np
from numba import njit

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
        {"name": "route_nodes", "type": "ARRAY", "required": True},
        {"name": "route_len", "type": "ARRAY", "required": True},
        {"name": "cost", "type": "NUMBER", "required": True},
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
```

**Step 4: Run tests**

Run: `pytest tests/test_vrp_solver.py -v`
Expected: ALL pass

**Step 5: Commit**

```bash
git add plugins/vrp/nodes/greedy_construction.py tests/test_vrp_solver.py
git commit -m "feat: VRP Greedy Construction solver — initial solution builder"
```

---

### Task 10: Route Map visualization node

**Files:**
- Create: `plugins/vrp/nodes/route_map.py`
- Modify: `tests/test_vrp_solver.py` (add test)

**Step 1: Write the failing test**

Add to `tests/test_vrp_solver.py`:

```python
def test_route_map_registered():
    assert "vrp_route_map" in _NODE_REGISTRY


def test_route_map_produces_svg():
    assembled, customers, fleet = _make_simple_problem()
    solver = _EXECUTORS["vrp_greedy_construction"]
    sol = solver(
        {},
        check_route=assembled["check_route"],
        compute_cost=assembled["compute_cost"],
        data=assembled["data"],
        fleet=fleet,
        customers=customers,
    )

    viz = _EXECUTORS["vrp_route_map"]
    result = viz(
        {},
        customers=customers,
        route_nodes=sol["route_nodes"],
        route_len=sol["route_len"],
        fleet=fleet,
    )

    svg = result["svg"]
    assert isinstance(svg, str)
    assert "<svg" in svg
    assert "</svg>" in svg
```

**Step 2: Run test, verify fail, implement, verify pass**

Implementation generates SVG with colored routes, customer dots, depot marker.

**Step 3: Commit**

```bash
git add plugins/vrp/nodes/route_map.py tests/test_vrp_solver.py
git commit -m "feat: VRP Route Map visualization — SVG route display"
```

---

### Task 11: End-to-end integration test

**Files:**
- Test: `tests/test_vrp_e2e.py` (CREATE)

**Step 1: Write the integration test**

```python
"""End-to-end VRP test: Generate → Weight → Distance → Assembler → Greedy → Map."""
import numpy as np
import pytest
from pipestudio.plugin_api import _EXECUTORS
from pipestudio.plugin_loader import load_all_plugins
from pipestudio.executor import WorkflowExecutor
from pipestudio.models import WorkflowDefinition, WorkflowNode, WorkflowEdge


@pytest.fixture(autouse=True)
def _load():
    load_all_plugins()


def test_cvrp_pipeline_via_executor():
    """Full CVRP pipeline running through PipeStudio executor."""
    wf = WorkflowDefinition(
        nodes=[
            WorkflowNode(id="gen", type="vrp_generate_cvrp",
                         params={"num_customers": 15, "num_vehicles": 3, "seed": 42}),
            WorkflowNode(id="wt", type="vrp_weight_constraint", params={}),
            WorkflowNode(id="dist", type="vrp_distance_cost", params={}),
            WorkflowNode(id="asm", type="vrp_constraint_assembler", params={}),
            WorkflowNode(id="solve", type="vrp_greedy_construction", params={}),
            WorkflowNode(id="map", type="vrp_route_map", params={}),
        ],
        edges=[
            # gen → weight constraint
            WorkflowEdge(source="gen", source_port="customers", target="wt", target_port="customers"),
            WorkflowEdge(source="gen", source_port="fleet", target="wt", target_port="fleet"),
            # gen → distance cost
            WorkflowEdge(source="gen", source_port="customers", target="dist", target_port="customers"),
            WorkflowEdge(source="gen", source_port="fleet", target="dist", target_port="fleet"),
            # constraints → assembler
            WorkflowEdge(source="wt", source_port="bundle", target="asm", target_port="unary_add"),
            WorkflowEdge(source="dist", source_port="bundle", target="asm", target_port="binary_add"),
            WorkflowEdge(source="gen", source_port="fleet", target="asm", target_port="fleet"),
            # assembler → solver
            WorkflowEdge(source="asm", source_port="check_route", target="solve", target_port="check_route"),
            WorkflowEdge(source="asm", source_port="compute_cost", target="solve", target_port="compute_cost"),
            WorkflowEdge(source="asm", source_port="data", target="solve", target_port="data"),
            WorkflowEdge(source="gen", source_port="fleet", target="solve", target_port="fleet"),
            WorkflowEdge(source="gen", source_port="customers", target="solve", target_port="customers"),
            # solver → map
            WorkflowEdge(source="gen", source_port="customers", target="map", target_port="customers"),
            WorkflowEdge(source="gen", source_port="fleet", target="map", target_port="fleet"),
            WorkflowEdge(source="solve", source_port="route_nodes", target="map", target_port="route_nodes"),
            WorkflowEdge(source="solve", source_port="route_len", target="map", target_port="route_len"),
        ],
    )

    events = []
    executor = WorkflowExecutor()
    for event in executor.execute(wf):
        events.append(event)

    # Check all nodes completed
    completed = [e["node_id"] for e in events if e.get("event") == "node_complete"]
    assert "gen" in completed
    assert "wt" in completed
    assert "dist" in completed
    assert "asm" in completed
    assert "solve" in completed
    assert "map" in completed

    # Check final output
    map_event = [e for e in events if e.get("node_id") == "map" and e.get("event") == "node_complete"][0]
    assert "svg" in str(map_event.get("outputs", {}).keys())

    # Check no errors
    errors = [e for e in events if e.get("event") == "error"]
    assert len(errors) == 0
```

**Step 2: Run test**

Run: `pytest tests/test_vrp_e2e.py -v`
Expected: PASS — full pipeline works end-to-end

**Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL pass

**Step 4: Commit**

```bash
git add tests/test_vrp_e2e.py
git commit -m "test: end-to-end CVRP pipeline — generate → constrain → assemble → solve → visualize"
```

---

## Summary

| Task | Component | Type | Files |
|------|-----------|------|-------|
| 1 | FUNCTION port color | Frontend | constants.ts |
| 2 | Multi-edge stacking | Backend core | executor.py, test_multi_edge.py |
| 3 | FUNCTION port summary | Backend core | executor.py |
| 4 | VRP plugin scaffold | Plugin | manifest.json |
| 5 | Generate CVRP node | Plugin (DATA) | generate_cvrp.py |
| 6 | Weight Constraint | Plugin (CONSTRAINT) | weight_constraint.py |
| 7 | Distance Cost | Plugin (CONSTRAINT) | distance_cost.py |
| 8 | Constraint Assembler | Plugin (ASSEMBLER) | constraint_assembler.py |
| 9 | Greedy Construction | Plugin (SOLVER) | greedy_construction.py |
| 10 | Route Map | Plugin (OUTPUT) | route_map.py |
| 11 | E2E integration test | Test | test_vrp_e2e.py |

**After Milestone 2**: Working CVRP solver on canvas. User can:
1. Drop Generate CVRP → Fleet + Customers
2. Drop Weight → bundle
3. Drop Distance Cost → bundle
4. Drop Assembler → check_route + compute_cost
5. Drop Greedy Construction → solution
6. Drop Route Map → SVG visualization

**Next milestones** (separate plans):
- Milestone 3: ALNS loop + destroy/repair operators
- Milestone 4: Scan constraints (Time Window, Battery, Hub)
- Milestone 5: More operators + visualization + RL operator selection
