# Plugin Lifecycle — Implementation Plan

Reference: [2026-02-12-plugin-lifecycle-design.md](./2026-02-12-plugin-lifecycle-design.md)

## Phase 1: Backend Core — Plugin Loader Rewrite

### Step 1.1: Add `NodeUnavailableError` to models

File: `pipestudio/models.py`

- Add `NodeUnavailableError(Exception)` with `node_id`, `node_type`, `reason` fields

### Step 1.2: Add `unregister_node()` to plugin_api

File: `pipestudio/plugin_api.py`

- Add function `unregister_node(node_type: str)` that removes from `_NODE_REGISTRY` and `_EXECUTORS`
- Add function `get_registered_types() -> list[str]` for introspection

### Step 1.3: Rewrite plugin_loader for 2-tier structure

File: `pipestudio/plugin_loader.py`

- Add `_read_state_file(plugins_dir) -> dict` to read `plugins_state.json`
- Add `_write_state_file(plugins_dir, state: dict)` to write state
- Add `_merge_manifests(base: dict, override: dict) -> dict` for shallow merge
- Modify `load_plugin()` to handle:
  - Simple plugin: `.py` file → import directly
  - Complex plugin: folder with `__init__.py` → import `__init__.py`
  - Check state file → skip if inactive
- Modify `load_plugins()` to scan 2 tiers:
  - Tier 1: project folders in `plugins/`
  - Tier 2: items inside each project's `nodes/` directory
- Add `activate_plugin(plugins_dir, plugin_id)` and `deactivate_plugin(plugins_dir, plugin_id)`
- Add `delete_plugin(plugins_dir, plugin_id)` — verifies inactive before deleting
- Keep backwards compatibility: existing plugin structure still works

### Step 1.4: Create hooks runner

File: `pipestudio/hooks.py` (new)

- `run_hook(plugin_dir: str, hook_name: str)` — imports `hooks.py` from plugin folder, calls named function if it exists
- Hook names: `on_activate`, `on_deactivate`, `on_uninstall`
- Silent skip if no `hooks.py` or function not found
- Catch and log exceptions from hooks (don't let them crash the server)

### Step 1.5: Fix executor for missing nodes

File: `pipestudio/executor.py`

- Before `self.executors[node_def.type]` call, check if type exists
- If not, raise `NodeUnavailableError` instead of letting `KeyError` propagate
- Error message includes whether plugin is inactive vs not installed

### Step 1.6: Tests for Phase 1

File: `tests/test_plugin_lifecycle.py` (new)

- Test 2-tier loading (project folder → plugins inside)
- Test simple plugin (file) and complex plugin (folder with `__init__.py`)
- Test manifest merge (base + override)
- Test `plugins_state.json` read/write
- Test activate/deactivate toggles registry correctly
- Test delete requires inactive state
- Test executor raises `NodeUnavailableError` for missing node types
- Test hooks execution (mock hooks.py)

Update: `tests/test_plugin_loader.py`, `tests/test_executor.py`

- Adapt existing tests to new 2-tier structure
- Verify backwards compatibility

---

## Phase 2: Backend API — New Endpoints

### Step 2.1: Add new plugin management endpoints

File: `pipestudio/server.py`

- `POST /api/plugins/{project}/{plugin}/activate`
  - Call `activate_plugin()` from loader
  - Run `on_activate` hook
  - Return activated plugin info with node types
- `POST /api/plugins/{project}/{plugin}/deactivate`
  - Call `deactivate_plugin()` from loader
  - Run `on_deactivate` hook
  - Return deactivated info with removed node types
- `DELETE /api/plugins/{project}/{plugin}`
  - Check inactive → 400 if still active
  - Run `on_uninstall` hook
  - Call `delete_plugin()` from loader
  - Return deleted confirmation
- `POST /api/plugins/{project}/activate` — activate all in project
- `POST /api/plugins/{project}/deactivate` — deactivate all in project

### Step 2.2: Modify existing endpoints

File: `pipestudio/server.py`

- `GET /api/plugins` — return hierarchical structure: project → plugins with state
- `GET /api/workflow/examples` — scan example JSONs, check node types against registry, add `available` and `missing_plugins` fields
- Keep old `DELETE /api/plugins/{plugin_name}` working for backwards compatibility (deprecate)

### Step 2.3: Tests for Phase 2

File: `tests/test_websocket.py` (update)

- Test new endpoints: activate, deactivate, delete
- Test hierarchical `GET /api/plugins` response
- Test example availability info
- Test delete-while-active returns 400

---

## Phase 3: Frontend — Node Visual States

### Step 3.1: Add types and constants

File: `frontend/src/types.ts`

- Add `PluginState = "active" | "inactive"`
- Add `NodeVisualState = "normal" | "disabled" | "broken" | "muted"`
- Add `PluginInfo` interface (hierarchical)
- Add `ProjectInfo` interface

File: `frontend/src/constants.ts`

- Add colors/styles for inactive state (grey dashed border, 50% opacity)
- Add colors/styles for broken state (red border, warning icon, 60% opacity)

### Step 3.2: Update WorkflowNode visual states

File: `frontend/src/WorkflowNode.tsx`

- Accept `visualState` prop or derive from registry context
- Render different border/opacity/badge based on state:
  - Normal: existing behavior
  - Disabled: grey dashed border, 50% opacity, "Inactive" badge
  - Broken: red border, warning icon, 60% opacity, "Missing" badge
  - Muted: existing behavior
- Tooltip changes per state

### Step 3.3: Canvas re-check logic

File: `frontend/src/WorkflowCanvas.tsx`

- Add `checkNodeStates()` function:
  - Fetch registry + plugin states
  - Scan canvas nodes, determine visual state for each
  - Update node data with state
- Call `checkNodeStates()` after: plugin activate/deactivate/delete/install/reload
- Call `checkNodeStates()` when loading workflow from JSON
- Show warning banner when loading workflow with missing/inactive plugins

### Step 3.4: ValidationPanel updates

File: `frontend/src/components/ValidationPanel.tsx`

- List inactive and broken nodes with details
- "Remove all broken nodes" button — removes broken nodes + connected edges
- "Activate" button next to each inactive plugin
- "Install plugin" suggestion next to broken nodes

---

## Phase 4: Frontend — PluginManager UI Rewrite

### Step 4.1: Hierarchical layout

File: `frontend/src/components/PluginManager.tsx`

- Fetch `GET /api/plugins` (new hierarchical format)
- Render project folders (collapsible) with plugins inside
- Show state indicator: ● green (active), ○ grey (inactive)
- Show canvas usage count per plugin (if > 0)

### Step 4.2: Action buttons

- Active plugin: [Deactivate] button
- Inactive plugin: [Activate] and [Delete] buttons
- Project level: [Deactivate All] / [Activate All]
- Call corresponding API endpoints
- After each action: refresh plugin list + trigger canvas re-check

### Step 4.3: Delete confirm dialog

- Only shown when clicking [Delete] on inactive plugin
- Display: number of nodes on canvas using this plugin
- Two options: "Keep nodes (marked broken)" / "Remove nodes and edges"
- On confirm: call DELETE endpoint, then clean up canvas if selected

---

## Phase 5: Verification & Cleanup

### Step 5.1: Run all tests

- `pytest tests/` — all existing + new tests pass
- Manual test: full activate → deactivate → delete flow
- Manual test: load workflow with missing plugin → warning banner
- Manual test: execute workflow with inactive node → stops at node with clear error

### Step 5.2: Update CLAUDE.md

- Document new plugin structure
- Document new API endpoints
- Update architecture section

## Execution Order

Phases 1 → 2 → 3 → 4 → 5 (sequential, each depends on previous).

Within phases, steps can be done in order listed. Steps within the same phase that don't depend on each other (e.g. 3.1 and 3.2) can be parallelized.
