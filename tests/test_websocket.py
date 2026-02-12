"""Tests for server endpoints and WebSocket streaming."""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def reload_plugins():
    """Ensure plugins are loaded before each test."""
    from pipestudio.plugin_api import _NODE_REGISTRY
    if not _NODE_REGISTRY:
        from pipestudio.plugin_loader import load_plugins
        load_plugins(os.path.join(os.path.dirname(__file__), "..", "plugins"))


@pytest.fixture
def client():
    """Create a FastAPI test client with lifespan (loads plugins via server)."""
    from pipestudio.server import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    """Health endpoint returns status and version."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"


def test_nodes_endpoint(client):
    """Nodes endpoint returns registry from loaded plugins."""
    resp = client.get("/api/workflow/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert "tsp_generate_points" in data
    assert "tsp_greedy" in data
    assert data["tsp_generate_points"]["category"] == "INPUT"


def test_execute_simple_workflow(client):
    """Execute a simple generate -> distance_matrix workflow via REST."""
    payload = {
        "name": "test",
        "nodes": [
            {"id": "gen", "type": "tsp_generate_points", "params": {"num_points": 10}},
            {"id": "dm", "type": "tsp_distance_matrix"},
        ],
        "edges": [
            {"id": "e1", "source": "gen", "source_port": "points",
             "target": "dm", "target_port": "points"},
        ],
    }
    resp = client.post("/api/workflow/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "gen" in data
    assert "dm" in data
    assert "dist_matrix" in data["dm"]


def test_websocket_connects_and_disconnects(client):
    """WebSocket endpoint accepts connections and handles disconnect."""
    with client.websocket_connect("/ws/execution") as ws:
        # Connection successful - just verify it connects
        pass
    # Disconnect should not raise


def test_execution_emits_events():
    """Executor event_handler receives start, node_start, node_complete, complete."""
    from pipestudio.models import WorkflowNode, WorkflowEdge, WorkflowDefinition
    from pipestudio.executor import WorkflowExecutor

    events = []

    def handler(event_type, data):
        events.append({"event": event_type, **data})

    wf = WorkflowDefinition(
        name="test",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="dm", target_port="points"),
        ],
    )
    WorkflowExecutor(wf, event_handler=handler).execute()

    event_types = [e["event"] for e in events]
    assert "start" in event_types
    assert "node_start" in event_types
    assert "node_complete" in event_types
    assert "complete" in event_types

    # Check log events from plugin logger
    assert "log" in event_types
    log_events = [e for e in events if e["event"] == "log"]
    assert len(log_events) > 0

    # Check complete event has total_ms
    complete_evt = [e for e in events if e["event"] == "complete"][0]
    assert "total_ms" in complete_evt
    assert complete_evt["total_ms"] >= 0


def test_execution_events_include_duration():
    """node_complete events include duration_ms."""
    from pipestudio.models import WorkflowNode, WorkflowDefinition
    from pipestudio.executor import WorkflowExecutor

    events = []
    def handler(event_type, data):
        events.append({"event": event_type, **data})

    wf = WorkflowDefinition(
        name="test",
        nodes=[WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10})],
        edges=[],
    )
    WorkflowExecutor(wf, event_handler=handler).execute()

    complete_events = [e for e in events if e["event"] == "node_complete"]
    assert len(complete_events) == 1
    assert "duration_ms" in complete_events[0]
    assert complete_events[0]["duration_ms"] >= 0


def test_examples_endpoint(client):
    """Examples endpoint lists available example workflows."""
    resp = client.get("/api/workflow/examples")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    names = [e["filename"] for e in data]
    assert "tsp_basic.json" in names


def test_load_example(client):
    """Load a specific example workflow."""
    resp = client.get("/api/workflow/example/tsp_basic.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "TSP Pipeline (100 Points)"
    assert len(data["nodes"]) == 6


def test_load_example_not_found(client):
    """Loading non-existent example returns 404."""
    resp = client.get("/api/workflow/example/nonexistent.json")
    assert resp.status_code == 404


def test_load_example_path_traversal(client):
    """Path traversal in example filename is rejected."""
    resp = client.get("/api/workflow/example/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)


def test_plugins_endpoint(client):
    """Plugins endpoint lists loaded plugins."""
    resp = client.get("/api/plugins")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    tsp = [p for p in data if p["project"] == "tsp"]
    assert len(tsp) == 1
    assert tsp[0]["status"] == "ok"
