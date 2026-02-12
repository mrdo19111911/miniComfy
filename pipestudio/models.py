"""Shared Pydantic models for PipeStudio."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class WorkflowNode(BaseModel):
    id: str
    type: str
    position: Dict[str, float] = {"x": 0, "y": 0}
    params: Dict[str, Any] = {}
    parent_id: Optional[str] = None
    muted: bool = False


class WorkflowEdge(BaseModel):
    id: str
    source: str
    source_port: str
    target: str
    target_port: str
    is_back_edge: bool = False


class WorkflowDefinition(BaseModel):
    name: str = "workflow"
    nodes: List[WorkflowNode] = []
    edges: List[WorkflowEdge] = []


class NodeUnavailableError(Exception):
    """Raised when executor encounters a node whose plugin is inactive or not installed."""

    def __init__(self, node_id: str, node_type: str, reason: str):
        self.node_id = node_id
        self.node_type = node_type
        self.reason = reason
        super().__init__(
            f"Node '{node_id}' uses type '{node_type}' which is {reason}"
        )
