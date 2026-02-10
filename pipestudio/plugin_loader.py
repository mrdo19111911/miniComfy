"""Scans plugins/ directory and loads node definitions.

Supports two plugin layouts:
  - Modern: plugins/{name}/manifest.json + plugins/{name}/nodes/*.py  (1 node per file)
  - Legacy: plugins/{name}/manifest.json + plugins/{name}/nodes.py    (all nodes in 1 file)
"""
import importlib.util
import json
import os
import sys
from typing import Any, Dict, List

from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS


def _import_module(name: str, path: str):
    """Import a Python file as a module, executing @node decorators."""
    # Remove stale module if reloading
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_plugin(plugin_dir: str) -> Dict[str, Any]:
    """Load a single plugin from its directory. Returns manifest dict."""
    manifest_path = os.path.join(plugin_dir, "manifest.json")
    nodes_dir = os.path.join(plugin_dir, "nodes")
    nodes_file = os.path.join(plugin_dir, "nodes.py")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No manifest.json in {plugin_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    plugin_name = manifest.get("name", os.path.basename(plugin_dir))

    # Count nodes before loading to track what this plugin adds
    before = set(_NODE_REGISTRY.keys())

    if os.path.isdir(nodes_dir):
        # Modern layout: nodes/ directory with one .py per node
        for fname in sorted(os.listdir(nodes_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            fpath = os.path.join(nodes_dir, fname)
            module_name = f"pipestudio_plugin_{plugin_name}_{fname[:-3]}"
            _import_module(module_name, fpath)
    elif os.path.exists(nodes_file):
        # Legacy layout: single nodes.py
        module_name = f"pipestudio_plugin_{plugin_name}"
        _import_module(module_name, nodes_file)
    else:
        raise FileNotFoundError(
            f"No nodes/ directory or nodes.py in {plugin_dir}"
        )

    after = set(_NODE_REGISTRY.keys())
    new_nodes = after - before

    manifest["_loaded"] = True
    manifest["_path"] = plugin_dir
    manifest["_node_count"] = len(new_nodes)
    manifest["_node_types"] = sorted(new_nodes)
    return manifest


def load_plugins(plugins_dir: str) -> List[Dict[str, Any]]:
    """Scan plugins directory and load all plugins. Returns list of manifests."""
    results = []
    if not os.path.exists(plugins_dir):
        return results

    for entry in sorted(os.listdir(plugins_dir)):
        plugin_path = os.path.join(plugins_dir, entry)
        if not os.path.isdir(plugin_path):
            continue
        manifest_path = os.path.join(plugin_path, "manifest.json")
        if not os.path.exists(manifest_path):
            continue
        try:
            manifest = load_plugin(plugin_path)
            results.append(manifest)
            total = len(_NODE_REGISTRY)
            print(f"  Plugin '{manifest['name']}' loaded: {total} nodes")
        except Exception as e:
            results.append({
                "name": entry,
                "_loaded": False,
                "_error": str(e),
                "_path": plugin_path,
            })
            print(f"  Plugin '{entry}' FAILED: {e}")
    return results


def reload_plugins(plugins_dir: str) -> List[Dict[str, Any]]:
    """Clear registries and reload all plugins. Used for hot-reload."""
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    return load_plugins(plugins_dir)


def get_full_registry() -> Dict[str, Any]:
    """Return merged registry from all loaded plugins."""
    return dict(_NODE_REGISTRY)


def get_full_executors() -> Dict[str, Any]:
    """Return merged executors from all loaded plugins."""
    return dict(_EXECUTORS)
