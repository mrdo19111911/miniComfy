"""Public API for PipeStudio plugin developers.

Plugin authors only need to import from this module:
    from pipestudio.plugin_api import logger
"""
import warnings
from typing import Callable, Optional


# --- Node registry (filled by plugin loader via register_node) ---

_NODE_REGISTRY: dict = {}
_EXECUTORS: dict = {}


def register_node(node_info: dict, executor_fn: Callable = None) -> None:
    """Register a node from a NODE_INFO dict and an optional executor function.

    If executor_fn is None, only the spec is registered (e.g. loop_group
    which is handled entirely by the executor engine).
    """
    node_type = node_info["type"]
    if node_type in _NODE_REGISTRY:
        warnings.warn(f"Duplicate node type '{node_type}' — overwriting previous registration")
    spec = {
        "type": node_type,
        "label": node_info.get("label", node_type),
        "category": node_info.get("category", "UNCATEGORIZED"),
        "description": node_info.get("description", ""),
        "doc": node_info.get("doc", ""),
        "mode": node_info.get("mode", "python"),
        "inputs": [
            {
                "name": p["name"],
                "type": p.get("type", "ANY"),
                "required": p.get("default") is None and p.get("required", True),
                "default": p.get("default"),
            }
            for p in node_info.get("ports_in", [])
        ],
        "outputs": [
            {
                "name": p["name"],
                "type": p.get("type", "ANY"),
                "required": True,
                "default": None,
            }
            for p in node_info.get("ports_out", [])
        ],
    }
    _NODE_REGISTRY[node_type] = spec
    if executor_fn is not None:
        _EXECUTORS[node_type] = executor_fn


def unregister_node(node_type: str) -> None:
    """Remove a node type from registry and executors. Silent if not found."""
    _NODE_REGISTRY.pop(node_type, None)
    _EXECUTORS.pop(node_type, None)


def get_registry() -> dict:
    """Return a copy of the node registry."""
    return dict(_NODE_REGISTRY)


def get_executors() -> dict:
    """Return a copy of the executor functions."""
    return dict(_EXECUTORS)


# --- Logger ---

class NodeLogger:
    """Logger that tags messages with node context.

    Executor sets context before each node runs, clears after.
    Plugin authors just call logger.info(), logger.debug(), etc.
    """

    def __init__(self):
        self._handler: Optional[Callable] = None
        self._node_id: Optional[str] = None
        self._node_type: Optional[str] = None

    def _set_context(self, node_id: str, node_type: str, handler: Callable):
        self._node_id = node_id
        self._node_type = node_type
        self._handler = handler

    def _clear_context(self):
        self._node_id = None
        self._node_type = None
        self._handler = None

    def _emit(self, level: str, message: str):
        if self._handler:
            self._handler(level, self._node_id, self._node_type, message)
        else:
            print(f"[{level}] [{self._node_type}:{self._node_id}] {message}")

    def debug(self, message: str):
        self._emit("DEBUG", message)

    def info(self, message: str):
        self._emit("INFO", message)

    def warn(self, message: str):
        self._emit("WARN", message)

    def error(self, message: str):
        self._emit("ERROR", message)


# Singleton logger instance - plugins import and use this directly
logger = NodeLogger()
