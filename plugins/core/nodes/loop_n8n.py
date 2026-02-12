"""Loop node (n8n style) — single node with back-edge feedback."""

NODE_INFO = {
    "type": "loop_node",
    "label": "Loop",
    "category": "CONTROL",
    "description": "Loop with back-edge feedback (n8n style).",
    "doc": (
        "Single loop control node. Initial data enters via init_1/init_2/init_3. "
        "Each iteration outputs from loop_1/loop_2/loop_3 to the processing chain. "
        "Connect the last processing node back to feedback_1/feedback_2/feedback_3 "
        "(these are back-edges shown as dashed orange lines). After all iterations, "
        "done_1/done_2/done_3 emit the final values to downstream nodes."
    ),
    "ports_in": [
        {"name": "init_1", "type": "ARRAY"},
        {"name": "init_2", "type": "ARRAY", "required": False},
        {"name": "init_3", "type": "ARRAY", "required": False},
        {"name": "feedback_1", "type": "ARRAY", "required": False},
        {"name": "feedback_2", "type": "ARRAY", "required": False},
        {"name": "feedback_3", "type": "ARRAY", "required": False},
        {"name": "iterations", "type": "NUMBER", "default": 10},
    ],
    "ports_out": [
        {"name": "loop_1", "type": "ARRAY"},
        {"name": "loop_2", "type": "ARRAY"},
        {"name": "loop_3", "type": "ARRAY"},
        {"name": "done_1", "type": "ARRAY"},
        {"name": "done_2", "type": "ARRAY"},
        {"name": "done_3", "type": "ARRAY"},
    ],
}


def run(init_1=None, init_2=None, init_3=None,
        feedback_1=None, feedback_2=None, feedback_3=None,
        iterations=10):
    """Pass-through — actual looping is handled by the executor."""
    return init_1, init_2, init_3, init_1, init_2, init_3
