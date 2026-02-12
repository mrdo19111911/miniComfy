"""End-to-end VRP test: Generate → Weight → Distance → Assembler → Greedy → Map."""
import numpy as np
import pytest
from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS
from pipestudio.plugin_loader import load_plugins
from pipestudio.executor import WorkflowExecutor
from pipestudio.models import WorkflowDefinition, WorkflowNode, WorkflowEdge

PLUGINS_DIR = "plugins"


@pytest.fixture(autouse=True)
def _load():
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    load_plugins(PLUGINS_DIR)


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
            WorkflowEdge(id="e1", source="gen", source_port="customers",
                         target="wt", target_port="customers"),
            WorkflowEdge(id="e2", source="gen", source_port="fleet",
                         target="wt", target_port="fleet"),
            # gen → distance cost
            WorkflowEdge(id="e3", source="gen", source_port="customers",
                         target="dist", target_port="customers"),
            WorkflowEdge(id="e4", source="gen", source_port="fleet",
                         target="dist", target_port="fleet"),
            # constraints → assembler
            WorkflowEdge(id="e5", source="wt", source_port="bundle",
                         target="asm", target_port="unary_add"),
            WorkflowEdge(id="e6", source="dist", source_port="bundle",
                         target="asm", target_port="binary_add"),
            WorkflowEdge(id="e7", source="gen", source_port="fleet",
                         target="asm", target_port="fleet"),
            # assembler → solver
            WorkflowEdge(id="e8", source="asm", source_port="check_route",
                         target="solve", target_port="check_route"),
            WorkflowEdge(id="e9", source="asm", source_port="compute_cost",
                         target="solve", target_port="compute_cost"),
            WorkflowEdge(id="e10", source="asm", source_port="data",
                         target="solve", target_port="data"),
            WorkflowEdge(id="e11", source="gen", source_port="fleet",
                         target="solve", target_port="fleet"),
            WorkflowEdge(id="e12", source="gen", source_port="customers",
                         target="solve", target_port="customers"),
            # solver → map
            WorkflowEdge(id="e13", source="gen", source_port="customers",
                         target="map", target_port="customers"),
            WorkflowEdge(id="e14", source="gen", source_port="fleet",
                         target="map", target_port="fleet"),
            WorkflowEdge(id="e15", source="solve", source_port="route_nodes",
                         target="map", target_port="route_nodes"),
            WorkflowEdge(id="e16", source="solve", source_port="route_len",
                         target="map", target_port="route_len"),
        ],
    )

    events = []

    def handler(event_type, data):
        events.append({"event": event_type, **data})

    executor = WorkflowExecutor(wf, event_handler=handler)
    results = executor.execute()

    # Check all nodes produced output
    assert "gen" in results
    assert "wt" in results
    assert "dist" in results
    assert "asm" in results
    assert "solve" in results
    assert "map" in results

    # Check node_complete events fired for all
    completed = [e["node_id"] for e in events if e.get("event") == "node_complete"]
    assert "gen" in completed
    assert "wt" in completed
    assert "dist" in completed
    assert "asm" in completed
    assert "solve" in completed
    assert "map" in completed

    # Check final SVG output
    svg = results["map"]["svg"]
    assert isinstance(svg, str)
    assert "<svg" in svg
    assert "</svg>" in svg

    # Check solver output validity
    route_nodes = results["solve"]["route_nodes"]
    route_len = results["solve"]["route_len"]
    cost = results["solve"]["cost"]
    assert cost > 0

    # All 15 customers assigned
    assigned = set()
    for r in range(3):
        for pos in range(int(route_len[r])):
            assigned.add(int(route_nodes[r, pos]))
    assert assigned == set(range(1, 16))

    # Check no error events
    errors = [e for e in events if e.get("event") == "node_error"]
    assert len(errors) == 0
