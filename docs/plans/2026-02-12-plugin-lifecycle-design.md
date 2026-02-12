# Plugin Lifecycle Management — Design Document

## Overview

Redesign PipeStudio's plugin system to support WordPress-style lifecycle management (Activate/Deactivate/Delete), nested plugin architecture with 2-tier folder structure, and graceful handling of missing/inactive nodes on the canvas.

## Plugin Architecture

### Folder Structure

```
plugins/
├── plugins_state.json                  ← state file (auto-created)
├── core/                               ← project folder: flow-control
│   ├── manifest.json                   ← group manifest (defaults)
│   └── nodes/
│       ├── loop_group.py               ← simple plugin: 1 file
│       ├── loop_start.py
│       ├── loop_end.py
│       └── loop_n8n.py
├── sorting/                            ← project folder: sorting algorithms
│   ├── manifest.json
│   └── nodes/
│       ├── generate_array.py           ← simple plugin: 1 file
│       ├── shuffle_segment.py
│       └── bubble_pass/                ← complex plugin: folder
│           ├── manifest.json           ← overrides group manifest
│           ├── __init__.py             ← @node entry point
│           ├── algorithm.py
│           └── helpers.py
└── tsp/
    ├── manifest.json
    └── nodes/
        ├── generate_points.py
        └── two_opt/
            ├── __init__.py
            └── optimizer.py
```

### Key Concepts

- **Tier 1** (`plugins/sorting/`) — project folder for grouping related plugins. Not a plugin itself.
- **Tier 2** (items inside `nodes/`) — actual plugins. Can be:
  - A single `.py` file with `@node` decorator
  - A folder with `__init__.py` containing `@node` decorator, plus internal helper files
- **Plugin identity**: path-based, e.g. `"sorting/generate_array"`, `"core/loop_start"`
- **Manifest merge**: plugin folder's `manifest.json` shallow-merges onto parent group's `manifest.json`. Plugin without its own manifest inherits 100% from parent.

### plugins_state.json

```json
{
  "sorting/bubble_pass": "inactive"
}
```

- Plugins not listed default to `"active"` (backwards compatible)
- Only entries with non-default state need to be stored
- Auto-created on first state change

### Loader Logic

For each subfolder in `plugins/`:
1. Read group `manifest.json` → base manifest
2. Scan `nodes/` directory:
   - `.py` file (not `__init__.py`, not `_` prefix) → simple plugin, use base manifest
   - Folder with `__init__.py` → complex plugin, shallow merge its `manifest.json` onto base
3. Check `plugins_state.json` — if `"inactive"` then skip import
4. Import module, `@node` decorators register into `_NODE_REGISTRY`

## Plugin Lifecycle

### State Transitions

```
[Install / Upload .zip]
        ↓
     ACTIVE  ←→  INACTIVE
                    ↓
                 DELETED (removed from disk)
```

### Activate

- Write `"active"` to `plugins_state.json` (or remove entry since active is default)
- Import module, register `@node` into registry
- Run `hooks.py:on_activate()` if present
- Frontend: refresh palette, re-check canvas nodes → previously disabled/broken nodes with matching type auto-restore to normal state

### Deactivate

- Write `"inactive"` to `plugins_state.json`
- Remove node types from `_NODE_REGISTRY` and `_EXECUTORS`
- Run `hooks.py:on_deactivate()` if present
- Frontend: scan canvas → nodes of deactivated plugin types become disabled (grey, dimmed)
- **Files stay on disk** — nothing deleted

### Delete

- **Requires inactive state first** (like WordPress: must deactivate before delete button appears)
- Show confirm dialog with options:
  - "Keep nodes on canvas (marked as broken)"
  - "Remove nodes and connected edges from canvas"
- Run `hooks.py:on_uninstall()` if present
- Delete plugin file/folder from disk
- Remove entry from `plugins_state.json`

### Lifecycle Hooks (optional)

Complex plugins (folder-based) may include `hooks.py`:

```python
def on_activate():
    """Runs when plugin is activated. E.g. check dependencies."""
    pass

def on_deactivate():
    """Runs when plugin is deactivated. E.g. cleanup cache."""
    pass

def on_uninstall():
    """Runs when plugin is deleted. E.g. remove generated data."""
    pass
```

No `hooks.py` → silently skip.

## Canvas Node States

### 4 Visual States

| State | When | Visual | Execute | Tooltip |
|---|---|---|---|---|
| **Normal** | Plugin active | Category-colored border, 100% opacity | Yes | Normal doc |
| **Disabled** | Plugin deactivated | Grey dashed border, 50% opacity, "Inactive" badge | No — executor stops here | "Plugin 'sorting/bubble_pass' is inactive. Activate to use." |
| **Broken** | Plugin deleted, node remains on canvas | Red border, warning icon, 60% opacity, "Missing" badge | No — executor stops here | "Plugin 'sorting/bubble_pass' not installed." |
| **Muted** | User manually muted (existing feature) | Grey border, reduced opacity | Skip (pass-through) | "Muted — will pass inputs through" |

### Re-check Logic

Whenever registry changes (activate, deactivate, delete, install, reload):
1. Frontend fetches updated registry from `GET /api/workflow/nodes`
2. Frontend fetches plugin states from `GET /api/plugins`
3. Scans all canvas nodes:
   - Node type in registry + plugin active → **Normal**
   - Node type in registry + plugin inactive → **Disabled**
   - Node type not in registry → **Broken**
4. Updates visual state accordingly

Same check runs when **loading a workflow from JSON** — if workflow uses nodes from missing/inactive plugins, show warning banner:
```
⚠ Workflow uses nodes from missing plugins: sorting/bubble_pass, sorting/measure_disorder
  [Install plugins]  [Continue anyway]
```

### Toolbar Actions for Broken/Inactive Nodes

In **ValidationPanel**:
- List all inactive/broken nodes
- **"Remove all broken nodes"** button — batch remove broken nodes + connected edges
- **"Activate"** button next to each inactive plugin — activate directly from panel
- **"Install plugin"** suggestion next to broken nodes

## Execution Behavior

Executor **does not block upfront**. Runs normally in topological order. When reaching an inactive or broken node:

1. Emits `node_error` event with clear message:
   - Inactive: `"Plugin 'sorting/bubble_pass' is inactive. Activate to continue."`
   - Broken: `"Plugin 'sorting/bubble_pass' is not installed."`
2. **Stops execution** at that node (downstream nodes not reached)
3. Node flashes red border on canvas
4. LogPanel displays error
5. Nodes **before** the stuck node keep their results — user can inspect outputs

### Backend Change

In `executor.py`, before calling `self.executors[node_def.type]`:

```python
if node_def.type not in self.executors:
    raise NodeUnavailableError(
        node_id=node_id,
        node_type=node_def.type,
        reason="inactive"  # or "not_installed"
    )
```

Replaces current `KeyError` crash with meaningful error.

## API Changes

### New Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/plugins/{project}/{plugin}/activate` | Activate a single plugin |
| `POST` | `/api/plugins/{project}/{plugin}/deactivate` | Deactivate a single plugin |
| `DELETE` | `/api/plugins/{project}/{plugin}` | Delete plugin (must be inactive) |
| `POST` | `/api/plugins/{project}/activate` | Activate all plugins in project |
| `POST` | `/api/plugins/{project}/deactivate` | Deactivate all plugins in project |

### Modified Endpoints

**`GET /api/plugins`** — returns hierarchical structure with state:

```json
[
  {
    "project": "sorting",
    "manifest": { "name": "sorting", "version": "1.0.0", "categories": {} },
    "plugins": [
      {
        "id": "sorting/generate_array",
        "type": "file",
        "state": "active",
        "node_types": ["generate_array"]
      },
      {
        "id": "sorting/bubble_pass",
        "type": "directory",
        "state": "inactive",
        "node_types": ["bubble_pass"],
        "manifest_override": { "version": "2.0.0" }
      }
    ]
  }
]
```

**`GET /api/workflow/nodes`** — unchanged, only returns nodes from active plugins.

**`GET /api/workflow/examples`** — adds availability info:

```json
[
  {
    "filename": "sorting_basic.json",
    "name": "Basic Sorting Demo",
    "available": true
  },
  {
    "filename": "sorting_loop.json",
    "name": "Sorting Loop Demo",
    "available": false,
    "missing_plugins": ["sorting/bubble_pass"]
  }
]
```

Unavailable examples shown dimmed in UI with tooltip explaining which plugins to install/activate.

### Response Examples

**Activate:**
```json
{ "status": "activated", "id": "sorting/bubble_pass", "node_types": ["bubble_pass"] }
```

**Deactivate:**
```json
{ "status": "deactivated", "id": "sorting/bubble_pass", "node_types_removed": ["bubble_pass"] }
```

**Delete (plugin still active):**
```json
// 400 Bad Request
{ "detail": "Plugin must be deactivated before deletion." }
```

**Delete (plugin inactive):**
```json
{ "status": "deleted", "id": "sorting/bubble_pass" }
```

## PluginManager UI

### Layout — Hierarchical Project → Plugin

```
┌─────────────────────────────────────────────────────┐
│  Plugin Manager                                   x │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ▼ sorting  (v1.0.0)                [Deactivate All]│
│    Sorting algorithm operators                      │
│                                                     │
│    ● generate_array         Active    [Deactivate]  │
│    ● shuffle_segment        Active    [Deactivate]  │
│    ○ bubble_pass            Inactive  [Activate] [Delete] │
│                                                     │
│  ▼ tsp  (v1.0.0)                    [Deactivate All]│
│    Traveling Salesman Problem                       │
│                                                     │
│    ● generate_points        Active    [Deactivate]  │
│    ● greedy                 Active    [Deactivate]  │
│                                                     │
├─────────────────────────────────────────────────────┤
│  [Install Plugin]  Upload a .zip file               │
└─────────────────────────────────────────────────────┘
```

- **●** green = active, **○** grey = inactive
- Project folders collapsible (▼ / ▶)
- **[Delete]** only visible when plugin is inactive
- **[Deactivate All] / [Activate All]** operates on entire project folder
- Each plugin shows canvas usage count if > 0: `"3 on canvas"`

### Delete Confirm Dialog

```
┌─────────────────────────────────────────────┐
│  Delete "sorting/bubble_pass"?              │
│                                             │
│  3 nodes on canvas use this plugin.         │
│                                             │
│  ○ Keep nodes on canvas (marked broken)     │
│  ○ Remove nodes and 5 connected edges       │
│                                             │
│               [Cancel]  [Delete]            │
└─────────────────────────────────────────────┘
```

## Files to Change

### Backend

| File | Change |
|---|---|
| `pipestudio/plugin_loader.py` | Rewrite: 2-tier scanning, `__init__.py` support, manifest merge, read `plugins_state.json` to skip inactive |
| `pipestudio/plugin_api.py` | Add `unregister_node(type)` to remove nodes from registry on deactivate |
| `pipestudio/server.py` | Add 5 new endpoints. Modify `GET /api/plugins` for hierarchical response. Modify `GET /api/workflow/examples` for availability info |
| `pipestudio/executor.py` | Add check for missing node types, raise `NodeUnavailableError` instead of `KeyError` |
| `pipestudio/models.py` | Add `NodeUnavailableError` exception |
| `pipestudio/hooks.py` | **New file** — load and run plugin lifecycle hooks |

### Frontend

| File | Change |
|---|---|
| `components/PluginManager.tsx` | Rewrite: hierarchical layout, activate/deactivate/delete, confirm dialog |
| `WorkflowNode.tsx` | Add visual states (inactive: grey dimmed, broken: red border + warning icon) |
| `WorkflowCanvas.tsx` | Add re-check logic on registry change, warning banner on workflow load |
| `components/ValidationPanel.tsx` | List inactive/broken nodes, "Remove all broken nodes" button, inline "Activate" button |
| `types.ts` | Add interfaces for plugin state, hierarchical plugin info |
| `constants.ts` | Add colors/styles for inactive and broken states |

### New Files

| File | Description |
|---|---|
| `plugins/plugins_state.json` | State file — auto-created, default `{}` |
| `pipestudio/hooks.py` | Hook runner for plugin lifecycle |
| `tests/test_plugin_lifecycle.py` | Tests for activate/deactivate/delete flow |

### No Changes Needed

- `pipestudio/validator.py` — "Unknown node type" check already works
- `run.py` — unchanged
- Existing plugins — backwards compatible, no migration needed
