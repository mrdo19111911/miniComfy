"""Loop End node (ComfyUI style) — marks end of a loop pair."""

NODE_INFO = {
    "type": "loop_end",
    "label": "Loop End",
    "category": "CONTROL",
    "description": "End of a loop. Pair with Loop Start.",
    "doc": (
        "Marks the end of a ComfyUI-style loop. Collects results from the loop body "
        "via in_1/in_2/in_3 and feeds them back to the paired Loop Start for the next "
        "iteration. After the final iteration, outputs flow to downstream nodes. "
        "Set 'pair_id' in params to the ID of the corresponding Loop Start node."
    ),
    "ports_in": [
        {"name": "in_1", "type": "ARRAY", "required": False},
        {"name": "in_2", "type": "ARRAY", "required": False},
        {"name": "in_3", "type": "ARRAY", "required": False},
    ],
    "ports_out": [
        {"name": "out_1", "type": "ARRAY"},
        {"name": "out_2", "type": "ARRAY"},
        {"name": "out_3", "type": "ARRAY"},
    ],
}


def run(in_1=None, in_2=None, in_3=None):
    """Pass-through — actual looping is handled by the executor."""
    return in_1, in_2, in_3
