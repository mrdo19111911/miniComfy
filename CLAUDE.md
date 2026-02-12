# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

miniComfy (internally "PipeStudio") is a visual node-based workflow builder. Python/FastAPI backend with a React/TypeScript/ReactFlow frontend. Users create data-processing workflows by dragging nodes onto a canvas, connecting ports, and executing the graph.

## Commands

### Running the Application

```bash
# Full stack (Windows) — kills old processes, sets up venv, installs deps, starts both servers
start.bat

# Backend only (port 8500, with hot-reload, auto-opens browser)
python run.py
# or directly:
uvicorn pipestudio.server:app --host 127.0.0.1 --port 8500 --reload

# Frontend only (port 5173)
cd frontend && npm run dev
```

### Building

```bash
cd frontend && npm run build    # TypeScript check (tsc) + Vite production build
cd frontend && npm run preview  # Preview production build
```

### Testing

```bash
pytest tests/                    # All tests (92 tests)
pytest tests/test_executor.py    # Single test file
pytest tests/test_executor.py -k "test_simple"  # Single test by name
```

Test deps not in requirements.txt: `pip install pytest httpx`

### Dependencies

```bash
pip install -r requirements.txt          # Python deps (fastapi, uvicorn, numpy, numba, psutil)
cd frontend && npm install               # Frontend deps
```

## Architecture

### Dual-Server Stack

- **Backend**: FastAPI on `127.0.0.1:8500` — REST API + WebSocket for real-time execution events. Swagger docs at `/docs`
- **Frontend**: Vite dev server on `localhost:5173` — React + ReactFlow canvas
- CORS configured in `pipestudio/server.py`. WebSocket URL derived from `API_BASE` in frontend constants

### Backend (`pipestudio/`)

| File | Role |
|------|------|
| `server.py` | FastAPI app: REST endpoints (`/api/workflow/*`, `/api/plugins/*`), WebSocket (`/ws/execution`), plugin management |
| `executor.py` | DAG executor with topological sort, supports 3 loop styles (loop_group container, ComfyUI start/end pair, n8n back-edge) |
| `plugin_loader.py` | 2-tier plugin loader: discovers projects → plugins, manages `plugins_state.json`, wraps `run()` functions into executor-compatible callables via `_make_executor()` |
| `plugin_api.py` | Public API for plugin authors: `register_node()`, `logger`, `unregister_node()` |
| `models.py` | Pydantic models: `WorkflowNode`, `WorkflowEdge`, `WorkflowDefinition`, `NodeUnavailableError` |
| `validator.py` | Workflow validation: cycle detection, missing connections, node type checks, loop pairing |
| `hooks.py` | Plugin lifecycle hook runner: calls `on_activate`/`on_deactivate`/`on_uninstall` from plugin's `hooks.py` |

### Frontend (`frontend/src/`)

- `WorkflowCanvas.tsx` — Main component (~1400 lines): ReactFlow canvas, drag-and-drop, save/load, undo/redo, execution dispatch. Uses refs for stable callback references in `applySnapshot` to avoid stale closures.
- `WorkflowNode.tsx` — Node renderer with inline config widgets per port type. SVG content sanitized with DOMPurify.
- `Loop*.tsx` — Loop node variants (LoopGroupNode, LoopStartNode, LoopEndNode, LoopN8nNode)
- `hooks/useWebSocket.ts` — WebSocket connection with auto-reconnect, supports multiple handlers per event via `Map<string, Set<handler>>`, wildcard `*` event
- `hooks/useUndoRedo.ts` — Undo/redo history stack with callback stripping on snapshot
- `constants.ts` — `API_BASE` URL, port-type colors, category colors, `NODE_STATE_STYLES`
- `types.ts` — TypeScript interfaces (`PortSpec`, `PaletteNode`, `NodeVisualState`, `PluginInfo`, `ProjectInfo`)
- `components/` — UI panels: Toolbar, LogPanel, DataInspector, ErrorTracePanel, StatusBar, HelpPanel, PluginManager, ValidationPanel, ContextMenu

### TypeScript Configuration

`noUnusedLocals` and `noUnusedParameters` are enabled in tsconfig.json. All `any` types have been replaced with `Record<string, unknown>` and explicit casts. The build command runs `tsc` before Vite.

### Plugin System (WordPress-style lifecycle)

**2-tier architecture**: `plugins/{project}/nodes/{plugin}` where each project groups related plugins.

```
plugins/
├── plugins_state.json          ← centralized state (auto-created)
├── core/                       ← project: flow-control nodes
│   ├── manifest.json
│   └── nodes/
│       ├── loop_group.py       ← NODE_INFO only (no run function)
│       ├── loop_start.py
│       ├── loop_end.py
│       └── loop_n8n.py
└── tsp/                        ← project: TSP solver algorithms
    ├── manifest.json
    └── nodes/
        ├── generate_points.py
        ├── distance_matrix.py
        ├── greedy.py
        ├── two_opt.py
        ├── evaluate.py
        ├── log_tour.py
        ├── map_visualize.py
        └── view_text.py
```

**Plugin identity**: `"project/plugin_name"` (e.g. `"tsp/greedy"`)

**Lifecycle states**: Active (default) → Inactive ↔ Active, Inactive → Deleted

**State file** (`plugins_state.json`): only stores non-default states. Plugins not listed default to active.

**Node definition** (convention-based, numba-compatible):

```python
# plugins/my_project/nodes/my_node.py
from pipestudio.plugin_api import logger  # optional, only if you need logging

NODE_INFO = {
    "type": "my_node",
    "label": "My Node",
    "category": "PROCESSING",
    "description": "Short description",
    "doc": "Longer documentation string.",
    "ports_in": [{"name": "input", "type": "ARRAY"}],
    "ports_out": [{"name": "output", "type": "ARRAY"}],
}

def run(input):
    # Positional args match ports_in order; return matches ports_out order
    result = input * 2
    logger.info(f"Processed {len(result)} items")
    return result  # single output → return value; multiple → return tuple
```

**Convention rules**:
- `NODE_INFO` dict at module level with `type`, `label`, `category`, `ports_in`, `ports_out`
- `run()` receives positional args in `ports_in` order (use defaults for optional params: `def run(x, window=50)`)
- `run()` returns a tuple in `ports_out` order (single output → return value directly, not a 1-tuple)
- Never return a dict from `run()` — the loader wraps the result automatically
- Compatible with numba `@njit` — can decorate `run()` directly since it uses positional args only
- Only import from `pipestudio.plugin_api` is `logger` (optional)
- `NODE_INFO` without `run()` = spec-only registration (e.g. `loop_group` container node)

**Canvas node visual states**: Normal, Disabled (inactive plugin, grey dashed border), Broken (deleted plugin, red dashed border), Muted (user action).

**Execution**: does not block upfront. Runs until hitting an inactive/missing node, then raises `NodeUnavailableError`.

### Plugin API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/plugins` | List projects with plugins (hierarchical) |
| `POST` | `/api/plugins/{project}/{plugin}/activate` | Activate a plugin |
| `POST` | `/api/plugins/{project}/{plugin}/deactivate` | Deactivate a plugin |
| `POST` | `/api/plugins/{project}/activate` | Activate all in project |
| `POST` | `/api/plugins/{project}/deactivate` | Deactivate all in project |
| `POST` | `/api/plugins/install` | Upload .zip plugin |
| `POST` | `/api/plugins/reload` | Hot-reload all plugins |

### Workflow Data Model

Workflows are JSON files (`examples/` directory) with `nodes` (id, type, position, params, parent_id, muted) and `edges` (source, source_port, target, target_port, is_back_edge). The executor builds a DAG from this, runs topological sort, and streams events over WebSocket.

### Three Loop Styles

1. **loop_group**: Container node; children have `parent_id` pointing to it
2. **ComfyUI style**: `loop_start` + `loop_end` node pair linked by `pair_id` config
3. **n8n style**: Single `loop_node` with back-edges (`is_back_edge: true`) for feedback

### Test Structure

| File | Coverage |
|------|----------|
| `test_executor.py` | DAG execution, all 3 loop styles, muted nodes, event handlers |
| `test_validator.py` | Cycle detection, missing connections, loop pairing, n8n back-edges |
| `test_plugin_lifecycle.py` | Registration, activation/deactivation, deletion, hooks, `NodeUnavailableError` |
| `test_plugin_loader.py` | TSP plugin discovery, executor wrappers, spec field validation |
| `test_convention_loader.py` | NODE_INFO + run() convention: positional args, tuple returns, defaults |
| `test_api_plugins.py` | REST endpoints for plugin management, example availability |
| `test_websocket.py` | Health endpoint, WebSocket connect/disconnect, execution events, path traversal protection |

Tests use inline plugin definitions (NODE_INFO + run()) registered directly into `_NODE_REGISTRY`/`_EXECUTORS` for isolation.
