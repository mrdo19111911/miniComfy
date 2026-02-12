"""Loop Start node (ComfyUI style) — marks beginning of a loop pair."""

NODE_INFO = {
    "type": "loop_start",
    "label": "Loop Start",
    "category": "CONTROL",
    "description": "Start of a loop. Pair with Loop End.",
    "doc": (
        "Marks the beginning of a ComfyUI-style loop. Data enters via in_1/in_2/in_3 "
        "and passes to the loop body via out_1/out_2/out_3. After each iteration, the "
        "paired Loop End feeds results back so the next iteration receives improved data. "
        "Set 'iterations' to control how many times the loop body executes."
    ),
    "ports_in": [
        {"name": "in_1", "type": "ARRAY"},
        {"name": "in_2", "type": "ARRAY", "required": False},
        {"name": "in_3", "type": "ARRAY", "required": False},
        {"name": "iterations", "type": "NUMBER", "default": 10},
    ],
    "ports_out": [
        {"name": "out_1", "type": "ARRAY"},
        {"name": "out_2", "type": "ARRAY"},
        {"name": "out_3", "type": "ARRAY"},
    ],
}


def run(in_1=None, in_2=None, in_3=None, iterations=10):
    """Pass-through — actual looping is handled by the executor."""
    return in_1, in_2, in_3
