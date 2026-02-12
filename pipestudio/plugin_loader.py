"""Scans plugins/ directory and loads node definitions.

Two-tier structure:
  plugins/
    plugins_state.json           <- active/inactive state per plugin
    {project}/                   <- project folder (grouping)
      manifest.json              <- group manifest (defaults)
      nodes/
        {name}.py                <- simple plugin (1 file)
        {name}/                  <- complex plugin (folder)
          __init__.py            <- entry point with NODE_INFO + run()
          manifest.json          <- optional override manifest
          hooks.py               <- optional lifecycle hooks
          ...                    <- internal helpers

Also supports legacy layout for backwards compatibility:
  plugins/{name}/manifest.json + plugins/{name}/nodes/*.py
  plugins/{name}/manifest.json + plugins/{name}/nodes.py
"""
import importlib.util
import json
import os
import sys
from typing import Any, Dict, List

from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS, unregister_node, register_node


# --- State file ---

def _read_state_file(plugins_dir: str) -> Dict[str, str]:
    """Read plugins_state.json. Returns {} if file doesn't exist."""
    state_path = os.path.join(plugins_dir, "plugins_state.json")
    if not os.path.exists(state_path):
        return {}
    with open(state_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_state_file(plugins_dir: str, state: Dict[str, str]) -> None:
    """Write plugins_state.json. Removes default ('active') entries to keep file clean."""
    clean = {k: v for k, v in state.items() if v != "active"}
    state_path = os.path.join(plugins_dir, "plugins_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)


def _get_plugin_state(state: Dict[str, str], plugin_id: str) -> str:
    """Get state for a plugin. Default is 'active'."""
    return state.get(plugin_id, "active")


# --- Manifest merge ---

def _merge_manifests(base: Dict, override: Dict) -> Dict:
    """Shallow merge: override's keys replace base's keys."""
    merged = dict(base)
    merged.update(override)
    return merged


# --- Convention-based executor wrapper ---

def _make_executor(module):
    """Create an executor that bridges (params, **inputs) to module.run(*positional).

    The wrapper:
    1. Merges defaults, edge inputs, and config params
    2. Builds a positional arg list matching ports_in order
    3. Calls run(*args)
    4. Wraps the return value (single or tuple) into a dict matching ports_out
    """
    run_fn = module.run
    node_info = module.NODE_INFO
    in_names = [p["name"] for p in node_info.get("ports_in", [])]
    out_names = [p["name"] for p in node_info.get("ports_out", [])]
    defaults = {}
    for p in node_info.get("ports_in", []):
        if p.get("default") is not None:
            defaults[p["name"]] = p["default"]

    def executor(params, **inputs):
        merged = dict(defaults)
        merged.update(inputs)
        merged.update(params)
        positional = [merged.get(name) for name in in_names]
        result = run_fn(*positional)
        if len(out_names) == 1:
            return {out_names[0]: result}
        return dict(zip(out_names, result))

    return executor


# --- Module import ---

def _import_module(name: str, path: str):
    """Import a Python file as a module. Supports both convention (NODE_INFO + run)
    and legacy (@node decorator) registration."""
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

    # Convention-based registration
    if hasattr(module, "NODE_INFO"):
        if hasattr(module, "run"):
            register_node(module.NODE_INFO, _make_executor(module))
        else:
            register_node(module.NODE_INFO, None)

    return module


# --- Single plugin loading ---

def _load_single_plugin(plugin_path: str, project_name: str, plugin_name: str) -> Dict[str, Any]:
    """Load a single plugin (file or folder). Returns info dict with node types added."""
    before = set(_NODE_REGISTRY.keys())

    if os.path.isfile(plugin_path) and plugin_path.endswith(".py"):
        # Simple plugin: single .py file
        module_name = f"pipestudio_plugin_{project_name}_{plugin_name}"
        _import_module(module_name, plugin_path)
    elif os.path.isdir(plugin_path):
        init_path = os.path.join(plugin_path, "__init__.py")
        if os.path.exists(init_path):
            # Complex plugin: folder with __init__.py
            module_name = f"pipestudio_plugin_{project_name}_{plugin_name}"
            _import_module(module_name, init_path)
        else:
            # Check for .py files directly (legacy-style nodes dir)
            for fname in sorted(os.listdir(plugin_path)):
                if not fname.endswith(".py") or fname.startswith("_"):
                    continue
                fpath = os.path.join(plugin_path, fname)
                mod_name = f"pipestudio_plugin_{project_name}_{fname[:-3]}"
                _import_module(mod_name, fpath)

    after = set(_NODE_REGISTRY.keys())
    new_nodes = after - before
    return {
        "node_types": sorted(new_nodes),
        "node_count": len(new_nodes),
    }


# --- Project loading ---

def _load_project(project_dir: str, project_name: str, state: Dict[str, str]) -> Dict[str, Any]:
    """Load all plugins from a project folder. Returns project manifest with plugin info."""
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return {"name": project_name, "_loaded": False, "_error": "No manifest.json"}

    with open(manifest_path, "r", encoding="utf-8") as f:
        base_manifest = json.load(f)

    nodes_dir = os.path.join(project_dir, "nodes")
    nodes_file = os.path.join(project_dir, "nodes.py")

    all_node_types = set()
    plugins_info = []

    if os.path.isdir(nodes_dir):
        for entry in sorted(os.listdir(nodes_dir)):
            entry_path = os.path.join(nodes_dir, entry)

            # Determine plugin name and type
            if os.path.isfile(entry_path) and entry.endswith(".py") and not entry.startswith("_"):
                plugin_name = entry[:-3]  # strip .py
                plugin_type = "file"
            elif os.path.isdir(entry_path) and not entry.startswith("_"):
                plugin_name = entry
                plugin_type = "directory"
            else:
                continue

            plugin_id = f"{project_name}/{plugin_name}"

            # Check state
            if _get_plugin_state(state, plugin_id) == "inactive":
                plugins_info.append({
                    "id": plugin_id,
                    "type": plugin_type,
                    "state": "inactive",
                    "node_types": [],
                })
                continue

            # Load child manifest for folder plugins
            child_manifest = {}
            if plugin_type == "directory":
                child_manifest_path = os.path.join(entry_path, "manifest.json")
                if os.path.exists(child_manifest_path):
                    with open(child_manifest_path, "r", encoding="utf-8") as f:
                        child_manifest = json.load(f)

            try:
                info = _load_single_plugin(entry_path, project_name, plugin_name)
                all_node_types.update(info["node_types"])
                plugins_info.append({
                    "id": plugin_id,
                    "type": plugin_type,
                    "state": "active",
                    "node_types": info["node_types"],
                    "manifest_override": child_manifest if child_manifest else None,
                })
            except Exception as e:
                plugins_info.append({
                    "id": plugin_id,
                    "type": plugin_type,
                    "state": "error",
                    "error": str(e),
                    "node_types": [],
                })

    elif os.path.exists(nodes_file):
        # Legacy: single nodes.py in project root
        plugin_id = f"{project_name}/nodes"
        if _get_plugin_state(state, plugin_id) != "inactive":
            module_name = f"pipestudio_plugin_{project_name}"
            before = set(_NODE_REGISTRY.keys())
            _import_module(module_name, nodes_file)
            after = set(_NODE_REGISTRY.keys())
            new_nodes = after - before
            all_node_types.update(new_nodes)

    result = dict(base_manifest)
    result["_loaded"] = True
    result["_path"] = project_dir
    result["_node_count"] = len(all_node_types)
    result["_node_types"] = sorted(all_node_types)
    result["_plugins"] = plugins_info
    return result


# --- Main API ---

def load_plugins(plugins_dir: str) -> List[Dict[str, Any]]:
    """Scan plugins directory and load all project folders. Returns list of manifests."""
    results = []
    if not os.path.exists(plugins_dir):
        return results

    state = _read_state_file(plugins_dir)

    for entry in sorted(os.listdir(plugins_dir)):
        project_path = os.path.join(plugins_dir, entry)
        if not os.path.isdir(project_path):
            continue
        # Skip hidden/internal dirs
        if entry.startswith(".") or entry.startswith("_"):
            continue
        manifest_path = os.path.join(project_path, "manifest.json")
        if not os.path.exists(manifest_path):
            continue

        try:
            result = _load_project(project_path, entry, state)
            results.append(result)
            total = len(_NODE_REGISTRY)
            print(f"  Project '{result.get('name', entry)}' loaded: {total} total nodes")
        except Exception as e:
            results.append({
                "name": entry,
                "_loaded": False,
                "_error": str(e),
                "_path": project_path,
            })
            print(f"  Project '{entry}' FAILED: {e}")

    return results


def reload_plugins(plugins_dir: str) -> List[Dict[str, Any]]:
    """Clear registries and reload all plugins. Used for hot-reload."""
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    return load_plugins(plugins_dir)


def activate_plugin(plugins_dir: str, plugin_id: str) -> None:
    """Activate a plugin: update state file and load its module."""
    state = _read_state_file(plugins_dir)
    state.pop(plugin_id, None)  # Remove entry (default is active)
    _write_state_file(plugins_dir, state)

    # Parse plugin_id: "project/plugin_name"
    parts = plugin_id.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid plugin_id: {plugin_id}")
    project_name, plugin_name = parts

    # Find and load the plugin
    nodes_dir = os.path.join(plugins_dir, project_name, "nodes")
    py_path = os.path.join(nodes_dir, f"{plugin_name}.py")
    dir_path = os.path.join(nodes_dir, plugin_name)

    if os.path.isfile(py_path):
        _load_single_plugin(py_path, project_name, plugin_name)
    elif os.path.isdir(dir_path):
        _load_single_plugin(dir_path, project_name, plugin_name)
    else:
        raise FileNotFoundError(f"Plugin not found: {plugin_id}")


def deactivate_plugin(plugins_dir: str, plugin_id: str) -> None:
    """Deactivate a plugin: update state file and unregister its nodes."""
    state = _read_state_file(plugins_dir)
    state[plugin_id] = "inactive"
    _write_state_file(plugins_dir, state)

    # Find which node types belong to this plugin and unregister them
    # We need to check what's currently registered by re-scanning
    parts = plugin_id.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid plugin_id: {plugin_id}")
    project_name, plugin_name = parts

    # Try to determine node types from the plugin file/folder
    nodes_dir = os.path.join(plugins_dir, project_name, "nodes")
    py_path = os.path.join(nodes_dir, f"{plugin_name}.py")
    dir_path = os.path.join(nodes_dir, plugin_name)

    # Simple heuristic: unregister nodes that match the plugin name
    # For a more robust approach, we'd track which plugin registered which nodes
    # For now, reload everything to get clean state
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    load_plugins(plugins_dir)


def delete_plugin(plugins_dir: str, plugin_id: str) -> None:
    """Delete a plugin from disk. Must be inactive first."""
    state = _read_state_file(plugins_dir)
    if _get_plugin_state(state, plugin_id) == "active":
        raise ValueError(
            f"Plugin '{plugin_id}' must be deactivated before deletion."
        )

    parts = plugin_id.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid plugin_id: {plugin_id}")
    project_name, plugin_name = parts

    nodes_dir = os.path.join(plugins_dir, project_name, "nodes")
    py_path = os.path.join(nodes_dir, f"{plugin_name}.py")
    dir_path = os.path.join(nodes_dir, plugin_name)

    import shutil
    if os.path.isfile(py_path):
        os.remove(py_path)
    elif os.path.isdir(dir_path):
        shutil.rmtree(dir_path)
    else:
        raise FileNotFoundError(f"Plugin not found on disk: {plugin_id}")

    # Clean up state entry
    state.pop(plugin_id, None)
    _write_state_file(plugins_dir, state)


def get_full_registry() -> Dict[str, Any]:
    """Return merged registry from all loaded plugins."""
    return dict(_NODE_REGISTRY)


def get_full_executors() -> Dict[str, Any]:
    """Return merged executors from all loaded plugins."""
    return dict(_EXECUTORS)
