"""Public API for PipeStudio plugin developers.

Plugin authors only need to import from this module:
    from pipestudio.plugin_api import node, Port, logger
"""
from dataclasses import dataclass
from typing import Any, Callable, List, Optional


# --- Port definition ---

@dataclass
class Port:
    """Defines an input or output port on a node."""
    name: str
    type: str  # "ARRAY", "NUMBER", "STRING", etc.
    required: bool = True
    default: Any = None

    def __post_init__(self):
        if self.default is not None:
            self.required = False


# --- Node registry (filled by @node decorator) ---

_NODE_REGISTRY: dict = {}
_EXECUTORS: dict = {}


def node(
    type: str,
    label: str,
    category: str,
    description: str = "",
    doc: str = "",
    ports_in: List[Port] = None,
    ports_out: List[Port] = None,
    mode: str = "python",
):
    """Decorator to register a function as a PipeStudio node.

    Usage:
        @node(
            type="my_node",
            label="My Node",
            category="PROCESSING",
            ports_in=[Port("input", "ARRAY")],
            ports_out=[Port("output", "ARRAY")],
        )
        def my_node(params, **inputs):
            return {"output": inputs["input"] * 2}
    """
    ports_in = ports_in or []
    ports_out = ports_out or []

    def decorator(func: Callable) -> Callable:
        spec = {
            "type": type,
            "label": label,
            "category": category,
            "description": description,
            "doc": doc,
            "mode": mode,
            "inputs": [
                {"name": p.name, "type": p.type, "required": p.required, "default": p.default}
                for p in ports_in
            ],
            "outputs": [
                {"name": p.name, "type": p.type, "required": True, "default": None}
                for p in ports_out
            ],
        }
        _NODE_REGISTRY[type] = spec
        _EXECUTORS[type] = func
        func._node_spec = spec
        return func

    return decorator


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
