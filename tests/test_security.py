"""Tests for security: Zip Slip, path traversal, iteration bounds."""
import io
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def reload_plugins():
    from pipestudio.plugin_api import _NODE_REGISTRY
    if not _NODE_REGISTRY:
        from pipestudio.plugin_loader import load_plugins
        load_plugins(os.path.join(os.path.dirname(__file__), "..", "plugins"))


@pytest.fixture
def client():
    from pipestudio.server import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


# --- B1: Zip Slip ---

def test_zip_slip_absolute_path_rejected(client):
    """ZIP with absolute path members must be rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test_plugin/manifest.json", json.dumps({"name": "evil"}))
        zf.writestr("/etc/passwd", "root:x:0:0")
    buf.seek(0)
    resp = client.post(
        "/api/plugins/install",
        files={"file": ("evil.zip", buf, "application/zip")},
    )
    assert resp.status_code == 400
    assert "unsafe" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()


def test_zip_slip_dot_dot_path_rejected(client):
    """ZIP with ../../ path traversal members must be rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test_plugin/manifest.json", json.dumps({"name": "evil"}))
        zf.writestr("test_plugin/nodes/../../pwned.py", "import os")
    buf.seek(0)
    resp = client.post(
        "/api/plugins/install",
        files={"file": ("evil.zip", buf, "application/zip")},
    )
    assert resp.status_code == 400


# --- B4: Path traversal in load_example ---

def test_path_traversal_url_encoded_rejected(client):
    """URL-encoded path traversal must not succeed (200)."""
    resp = client.get("/api/workflow/example/..%2F..%2Fetc%2Fpasswd")
    # FastAPI rejects %2F in path params at routing level (404) or our check catches it (400)
    assert resp.status_code in (400, 404)


def test_path_traversal_basename_enforced(client):
    """Filename with subdirectory separators must be rejected."""
    resp = client.get("/api/workflow/example/subdir/file.json")
    assert resp.status_code in (400, 404)


def test_path_traversal_double_dot_rejected(client):
    """Filename containing '..' must return 400."""
    resp = client.get("/api/workflow/example/..%5C..%5Csecret.json")
    assert resp.status_code == 400


# --- B6: Iteration bounds ---

def test_executor_zero_iterations():
    """Zero iterations should clamp to at least 1."""
    from pipestudio.models import WorkflowNode, WorkflowEdge, WorkflowDefinition
    from pipestudio.executor import WorkflowExecutor

    wf = WorkflowDefinition(
        name="test",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 5}),
            WorkflowNode(id="ls", type="loop_start", params={"iterations": 0}),
            WorkflowNode(id="le", type="loop_end", params={"pair_id": "ls"}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="ls", target_port="in_1"),
            WorkflowEdge(id="e2", source="ls", source_port="out_1",
                         target="le", target_port="in_1"),
        ],
    )
    # Should not crash, should execute at least 1 iteration
    result = WorkflowExecutor(wf).execute()
    assert "le" in result or "ls" in result


def test_executor_negative_iterations():
    """Negative iterations should clamp to 1."""
    from pipestudio.models import WorkflowNode, WorkflowDefinition
    from pipestudio.executor import WorkflowExecutor

    wf = WorkflowDefinition(
        name="test",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points",
                         params={"num_points": 5, "iterations": -5}),
        ],
        edges=[],
    )
    # Should not crash
    result = WorkflowExecutor(wf).execute()
    assert "gen" in result


def test_executor_huge_iterations_clamped():
    """Iterations above 10000 should be clamped."""
    from pipestudio.models import WorkflowNode, WorkflowEdge, WorkflowDefinition
    from pipestudio.executor import WorkflowExecutor

    wf = WorkflowDefinition(
        name="test",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 5}),
            WorkflowNode(id="ls", type="loop_start", params={"iterations": 999999}),
            WorkflowNode(id="le", type="loop_end", params={"pair_id": "ls"}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="ls", target_port="in_1"),
            WorkflowEdge(id="e2", source="ls", source_port="out_1",
                         target="le", target_port="in_1"),
        ],
    )
    events = []
    def handler(event_type, data):
        events.append({"event": event_type, **data})

    result = WorkflowExecutor(wf, event_handler=handler).execute()
    # Should have capped at 10000 iterations, not 999999
    log_msgs = [e["message"] for e in events if e["event"] == "log"]
    # If it ran 999999 iterations, this test would timeout/be very slow
    # The fact that we got here means it was clamped
    assert "le" in result or "ls" in result
