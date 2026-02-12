"""PipeStudio FastAPI server."""
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipestudio import __version__
from pipestudio.models import WorkflowNode, WorkflowEdge, WorkflowDefinition
from pipestudio.plugin_loader import (
    load_plugins, reload_plugins, get_full_registry,
    activate_plugin, deactivate_plugin, delete_plugin,
    _read_state_file, _write_state_file, _get_plugin_state,
)
from pipestudio.executor import WorkflowExecutor
from pipestudio.hooks import run_hook

# --- State ---

PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "plugins")
_manifests: List[Dict] = []
_start_time = time.time()


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _manifests
    abs_plugins = os.path.abspath(PLUGINS_DIR)
    print(f"Loading plugins from: {abs_plugins}")
    _manifests = reload_plugins(abs_plugins)
    loaded = [m["name"] for m in _manifests if m.get("_loaded")]
    failed = [m["name"] for m in _manifests if not m.get("_loaded")]
    print(f"Plugins loaded: {loaded}")
    if failed:
        print(f"Plugins FAILED: {failed}")
    yield


# --- App setup ---

app = FastAPI(title="PipeStudio", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- WebSocket manager ---

class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: dict):
        for ws in list(self.connections):
            try:
                await ws.send_json(message)
            except Exception:
                pass


ws_manager = ConnectionManager()


@app.websocket("/ws/execution")
async def ws_execution(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            # Breakpoint commands will be handled in Phase 5
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# --- Serialization ---

def serialize_outputs(outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Convert numpy arrays and types to JSON-safe format."""
    result = {}
    for node_id, node_out in outputs.items():
        if node_id.startswith("__"):
            continue
        serialized = {}
        for key, val in node_out.items():
            if isinstance(val, np.ndarray):
                if len(val) > 100:
                    serialized[key] = {
                        "_type": "array",
                        "length": len(val),
                        "first_10": val[:10].tolist(),
                        "last_10": val[-10:].tolist(),
                        "min": float(val.min()),
                        "max": float(val.max()),
                        "mean": float(val.mean()),
                        "sorted_ratio": float(
                            1.0 - sum(1 for i in range(len(val) - 1) if val[i] > val[i + 1])
                            / max(len(val) - 1, 1)
                        ),
                    }
                else:
                    serialized[key] = val.tolist()
            elif isinstance(val, (np.integer,)):
                serialized[key] = int(val)
            elif isinstance(val, (np.floating,)):
                serialized[key] = float(val)
            else:
                serialized[key] = val
        result[node_id] = serialized
    return result


def serialize_event(event: dict) -> dict:
    """Make an event dict JSON-safe (strip numpy from outputs)."""
    safe = {}
    for k, v in event.items():
        if k == "outputs" and isinstance(v, dict):
            safe[k] = {}
            for ok, ov in v.items():
                if isinstance(ov, np.ndarray):
                    safe[k][ok] = {"_type": "array", "length": len(ov)}
                elif isinstance(ov, (np.integer,)):
                    safe[k][ok] = int(ov)
                elif isinstance(ov, (np.floating,)):
                    safe[k][ok] = float(ov)
                else:
                    safe[k][ok] = ov
        elif isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            safe[k] = str(v)
        else:
            safe[k] = v
    return safe


# --- Endpoints ---

@app.get("/api/workflow/nodes")
def get_nodes():
    """Return node registry from all loaded plugins."""
    return get_full_registry()


class ExecuteRequest(BaseModel):
    name: str = "workflow"
    description: str = ""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


@app.post("/api/workflow/execute")
async def execute_workflow(req: ExecuteRequest):
    """Execute a workflow and return results."""
    try:
        nodes = [WorkflowNode(**n) for n in req.nodes]
        edges = [WorkflowEdge(**e) for e in req.edges]
        wf = WorkflowDefinition(name=req.name, nodes=nodes, edges=edges)

        events = []

        def event_handler(event_type, data):
            events.append({"event": event_type, **data})

        executor = WorkflowExecutor(wf, event_handler=event_handler)
        raw = executor.execute()

        # Broadcast events to WebSocket clients
        for evt in events:
            await ws_manager.broadcast(serialize_event(evt))

        return serialize_outputs(raw)
    except Exception as e:
        await ws_manager.broadcast({"event": "error", "message": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflow/validate")
def validate_workflow_endpoint(req: ExecuteRequest):
    """Validate a workflow and return issues."""
    from pipestudio.validator import validate_workflow
    nodes = [WorkflowNode(**n) for n in req.nodes]
    edges = [WorkflowEdge(**e) for e in req.edges]
    wf = WorkflowDefinition(name=req.name, nodes=nodes, edges=edges)
    return validate_workflow(wf)


@app.get("/api/workflow/examples")
def list_examples():
    """List available example workflows with availability info."""
    examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    if not os.path.exists(examples_dir):
        return []
    registry = get_full_registry()
    result = []
    for f in sorted(os.listdir(examples_dir)):
        if f.endswith(".json"):
            path = os.path.join(examples_dir, f)
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Check which node types in the workflow are missing from registry
            missing_nodes = set()
            for node in data.get("nodes", []):
                node_type = node.get("type", "")
                if node_type and node_type not in registry and node_type != "loop_group":
                    missing_nodes.add(node_type)
            entry = {
                "filename": f,
                "name": data.get("name", f),
                "available": len(missing_nodes) == 0,
            }
            if missing_nodes:
                entry["missing_nodes"] = sorted(missing_nodes)
            result.append(entry)
    return result


@app.get("/api/workflow/example/{filename}")
def load_example(filename: str):
    """Load a specific example workflow."""
    safe_name = os.path.basename(filename)
    if safe_name != filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = os.path.join(os.path.dirname(__file__), "..", "examples", safe_name)
    if not os.path.exists(path):
        raise HTTPException(404, "Example not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/plugins")
def list_plugins():
    """List plugins in hierarchical project → plugins format."""
    return [
        {
            "project": m.get("name", "unknown"),
            "manifest": {
                "name": m.get("name", "unknown"),
                "version": m.get("version", "0.0.0"),
                "description": m.get("description", ""),
                "categories": m.get("categories", {}),
            },
            "status": "ok" if m.get("_loaded") else "error",
            "error": m.get("_error"),
            "plugins": m.get("_plugins", []),
        }
        for m in _manifests
    ]


def _plugin_dir(project: str, plugin: str) -> str:
    """Resolve plugin directory path for hooks."""
    nodes_dir = os.path.join(os.path.abspath(PLUGINS_DIR), project, "nodes")
    dir_path = os.path.join(nodes_dir, plugin)
    if os.path.isdir(dir_path):
        return dir_path
    return nodes_dir


# --- Plugin lifecycle: activate / deactivate / delete ---

@app.post("/api/plugins/{project}/{plugin}/activate")
def activate_single_plugin(project: str, plugin: str):
    """Activate a single plugin."""
    global _manifests
    plugin_id = f"{project}/{plugin}"
    abs_plugins = os.path.abspath(PLUGINS_DIR)
    try:
        activate_plugin(abs_plugins, plugin_id)
        run_hook(_plugin_dir(project, plugin), "on_activate")
        _manifests = reload_plugins(abs_plugins)
        return {"status": "activated", "id": plugin_id}
    except FileNotFoundError:
        raise HTTPException(404, f"Plugin '{plugin_id}' not found")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/plugins/{project}/{plugin}/deactivate")
def deactivate_single_plugin(project: str, plugin: str):
    """Deactivate a single plugin."""
    global _manifests
    plugin_id = f"{project}/{plugin}"
    abs_plugins = os.path.abspath(PLUGINS_DIR)
    try:
        run_hook(_plugin_dir(project, plugin), "on_deactivate")
        deactivate_plugin(abs_plugins, plugin_id)
        _manifests = reload_plugins(abs_plugins)
        return {"status": "deactivated", "id": plugin_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/plugins/{project}/activate")
def activate_project(project: str):
    """Activate all plugins in a project."""
    global _manifests
    abs_plugins = os.path.abspath(PLUGINS_DIR)
    state = _read_state_file(abs_plugins)
    # Remove inactive entries for this project
    keys_to_remove = [k for k in state if k.startswith(f"{project}/")]
    for k in keys_to_remove:
        state.pop(k)
    _write_state_file(abs_plugins, state)
    _manifests = reload_plugins(abs_plugins)
    return {"status": "activated", "project": project}


@app.post("/api/plugins/{project}/deactivate")
def deactivate_project(project: str):
    """Deactivate all plugins in a project."""
    global _manifests
    abs_plugins = os.path.abspath(PLUGINS_DIR)
    # Find all plugins in this project from current manifests
    project_manifest = [m for m in _manifests if m.get("name") == project]
    if not project_manifest:
        raise HTTPException(404, f"Project '{project}' not found")
    plugin_ids = [p["id"] for p in project_manifest[0].get("_plugins", [])]
    state = _read_state_file(abs_plugins)
    for pid in plugin_ids:
        state[pid] = "inactive"
    _write_state_file(abs_plugins, state)
    _manifests = reload_plugins(abs_plugins)
    return {"status": "deactivated", "project": project}


@app.delete("/api/plugins/{project}/{plugin}")
def delete_single_plugin(project: str, plugin: str):
    """Delete a plugin from disk. Must be inactive first."""
    global _manifests
    plugin_id = f"{project}/{plugin}"
    abs_plugins = os.path.abspath(PLUGINS_DIR)
    try:
        run_hook(_plugin_dir(project, plugin), "on_uninstall")
        delete_plugin(abs_plugins, plugin_id)
        _manifests = reload_plugins(abs_plugins)
        return {"status": "deleted", "id": plugin_id}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, f"Plugin '{plugin_id}' not found on disk")


@app.post("/api/plugins/install")
async def install_plugin(file: UploadFile = File(...)):
    """Install a plugin from a ZIP file."""
    import zipfile
    import io

    content = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid ZIP file")

    # Find manifest.json to determine plugin name
    manifest_path = None
    for name in zf.namelist():
        if name.endswith("manifest.json") and name.count("/") <= 1:
            manifest_path = name
            break

    if not manifest_path:
        raise HTTPException(400, "No manifest.json found in ZIP")

    manifest = json.loads(zf.read(manifest_path))
    plugin_name = manifest.get("name", "unknown")

    # Zip Slip protection: reject ZIPs with absolute or traversal paths
    plugins_root = os.path.normpath(os.path.abspath(PLUGINS_DIR))
    for member in zf.namelist():
        if member.startswith("/") or member.startswith("\\") or ".." in member:
            raise HTTPException(400, f"Unsafe path in ZIP: {member}")

    # Extract to plugins directory
    plugin_dir = os.path.normpath(os.path.join(plugins_root, plugin_name))
    os.makedirs(plugin_dir, exist_ok=True)

    prefix = manifest_path.rsplit("manifest.json", 1)[0]
    for member in zf.namelist():
        if member.startswith(prefix) and not member.endswith("/"):
            rel_path = member[len(prefix):]
            target = os.path.normpath(os.path.join(plugin_dir, rel_path))
            if not target.startswith(plugin_dir + os.sep) and target != plugin_dir:
                raise HTTPException(400, f"Unsafe path in ZIP: {member}")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(zf.read(member))

    # Hot-reload: reload all plugins so new nodes are available immediately
    global _manifests
    _manifests = reload_plugins(os.path.abspath(PLUGINS_DIR))

    return {"status": "installed", "name": plugin_name, "message": f"Plugin '{plugin_name}' installed and loaded."}



@app.post("/api/plugins/reload")
def reload_all_plugins():
    """Reload all plugins (hot-reload)."""
    global _manifests
    _manifests = reload_plugins(os.path.abspath(PLUGINS_DIR))
    loaded = [m["name"] for m in _manifests if m.get("_loaded")]
    return {"status": "reloaded", "plugins": loaded, "node_count": len(get_full_registry())}


@app.get("/api/health")
def health():
    """Health check with system metrics."""
    mem_mb = 0
    try:
        import psutil
        mem_mb = round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except ImportError:
        pass

    return {
        "status": "healthy",
        "version": __version__,
        "uptime_seconds": round(time.time() - _start_time),
        "plugins_loaded": len([m for m in _manifests if m.get("_loaded")]),
        "plugins": [
            {
                "name": m.get("name", "unknown"),
                "status": "ok" if m.get("_loaded") else "error",
                "error": m.get("_error"),
            }
            for m in _manifests
        ],
        "memory_mb": mem_mb,
        "websocket_clients": len(ws_manager.connections),
    }
