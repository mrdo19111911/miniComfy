"""Tests for plugin lifecycle API endpoints."""
import json
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "plugins")


@pytest.fixture
def client():
    """Create a FastAPI test client. Cleans up plugin state after each test."""
    from pipestudio.server import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
        # Cleanup: remove any leftover state and reload to pristine
        state_path = os.path.join(PLUGINS_DIR, "plugins_state.json")
        if os.path.exists(state_path):
            with open(state_path, "w") as f:
                json.dump({}, f)
        c.post("/api/plugins/reload")


# ------------------------------------------------------------------
# GET /api/plugins --- hierarchical response
# ------------------------------------------------------------------

def test_plugins_endpoint_returns_hierarchical(client):
    """GET /api/plugins returns project -> plugins hierarchy."""
    resp = client.get("/api/plugins")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1

    # Find tsp project
    tsp = [p for p in data if p["project"] == "tsp"]
    assert len(tsp) == 1
    assert "plugins" in tsp[0]
    assert "manifest" in tsp[0]

    # Plugins should have id, type, state, node_types
    plugins = tsp[0]["plugins"]
    assert len(plugins) >= 1
    for plugin in plugins:
        assert "id" in plugin
        assert "state" in plugin
        assert "node_types" in plugin


def test_plugins_endpoint_shows_core_project(client):
    """GET /api/plugins includes the core project with loop nodes."""
    resp = client.get("/api/plugins")
    data = resp.json()
    core = [p for p in data if p["project"] == "core"]
    assert len(core) == 1
    all_node_types = []
    for plugin in core[0]["plugins"]:
        all_node_types.extend(plugin["node_types"])
    assert "loop_start" in all_node_types
    assert "loop_end" in all_node_types


# ------------------------------------------------------------------
# POST /api/plugins/{project}/{plugin}/deactivate
# ------------------------------------------------------------------

def test_deactivate_plugin(client):
    """POST deactivate removes node from registry."""
    # First verify the node exists
    resp = client.get("/api/workflow/nodes")
    assert "tsp_generate_points" in resp.json()

    # Deactivate (plugin ID is filename-based: tsp/generate_points)
    resp = client.post("/api/plugins/tsp/generate_points/deactivate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deactivated"
    assert data["id"] == "tsp/generate_points"

    # Node should be gone from registry
    resp = client.get("/api/workflow/nodes")
    assert "tsp_generate_points" not in resp.json()

    # Re-activate for other tests
    client.post("/api/plugins/tsp/generate_points/activate")


# ------------------------------------------------------------------
# POST /api/plugins/{project}/{plugin}/activate
# ------------------------------------------------------------------

def test_activate_plugin(client):
    """POST activate restores node to registry."""
    # Deactivate first (plugin ID is filename-based: tsp/generate_points)
    client.post("/api/plugins/tsp/generate_points/deactivate")
    resp = client.get("/api/workflow/nodes")
    assert "tsp_generate_points" not in resp.json()

    # Activate
    resp = client.post("/api/plugins/tsp/generate_points/activate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "activated"
    assert data["id"] == "tsp/generate_points"

    # Node should be back
    resp = client.get("/api/workflow/nodes")
    assert "tsp_generate_points" in resp.json()


# ------------------------------------------------------------------
# DELETE /api/plugins/{project}/{plugin} --- requires inactive
# ------------------------------------------------------------------

def test_delete_active_plugin_returns_400(client):
    """DELETE on active plugin returns 400."""
    resp = client.delete("/api/plugins/tsp/generate_points")
    assert resp.status_code == 400
    assert "deactivat" in resp.json()["detail"].lower()


def test_delete_inactive_plugin(client):
    """DELETE on inactive plugin removes from disk and returns 200."""
    # Create a temp plugin to delete
    nodes_dir = os.path.join(PLUGINS_DIR, "tsp", "nodes")
    temp_file = os.path.join(nodes_dir, "temp_delete_test.py")
    with open(temp_file, "w") as f:
        f.write('''
NODE_INFO = {
    "type": "temp_delete_test",
    "label": "Temp",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "NUMBER"}],
}

def run():
    return 1
''')

    try:
        # Reload to pick up the new plugin
        client.post("/api/plugins/reload")

        # Deactivate first
        resp = client.post("/api/plugins/tsp/temp_delete_test/deactivate")
        assert resp.status_code == 200

        # Now delete
        resp = client.delete("/api/plugins/tsp/temp_delete_test")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # File should be gone
        assert not os.path.exists(temp_file)
    finally:
        # Cleanup in case test fails
        if os.path.exists(temp_file):
            os.remove(temp_file)
        client.post("/api/plugins/reload")


def test_delete_nonexistent_plugin_returns_404(client):
    """DELETE on non-existent plugin returns 404."""
    # Write state manually so the state check passes
    state_path = os.path.join(PLUGINS_DIR, "plugins_state.json")
    state = {}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
    state["tsp/nonexistent_xyz"] = "inactive"
    with open(state_path, "w") as f:
        json.dump(state, f)

    try:
        resp = client.delete("/api/plugins/tsp/nonexistent_xyz")
        assert resp.status_code == 404
    finally:
        # Cleanup state
        state.pop("tsp/nonexistent_xyz", None)
        with open(state_path, "w") as f:
            json.dump(state, f)


# ------------------------------------------------------------------
# POST /api/plugins/{project}/activate and /deactivate (bulk)
# ------------------------------------------------------------------

def test_deactivate_all_in_project(client):
    """POST deactivate all plugins in a project."""
    resp = client.post("/api/plugins/tsp/deactivate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deactivated"
    assert data["project"] == "tsp"

    # TSP nodes should be gone
    nodes = client.get("/api/workflow/nodes").json()
    assert "tsp_generate_points" not in nodes
    assert "tsp_greedy" not in nodes

    # Re-activate all
    client.post("/api/plugins/tsp/activate")

    # Nodes should be back
    nodes = client.get("/api/workflow/nodes").json()
    assert "tsp_generate_points" in nodes


# ------------------------------------------------------------------
# GET /api/workflow/examples --- availability info
# ------------------------------------------------------------------

def test_examples_include_availability(client):
    """GET /api/workflow/examples includes 'available' field."""
    resp = client.get("/api/workflow/examples")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for example in data:
        assert "available" in example
        assert "filename" in example


def test_examples_unavailable_when_plugin_inactive(client):
    """Examples using inactive plugin nodes are marked unavailable."""
    # Deactivate tsp plugin
    client.post("/api/plugins/tsp/deactivate")

    resp = client.get("/api/workflow/examples")
    data = resp.json()
    tsp_examples = [e for e in data if "tsp" in e["filename"]]
    for ex in tsp_examples:
        assert ex["available"] is False
        assert "missing_plugins" in ex or "missing_nodes" in ex

    # Re-activate
    client.post("/api/plugins/tsp/activate")
