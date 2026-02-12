"""Loop Group container node (handled by executor engine, not a normal executor)."""

NODE_INFO = {
    "type": "loop_group",
    "label": "Loop Group",
    "category": "CONTROL",
    "description": "Loops child nodes N times",
    "doc": (
        "Container node that repeats its child nodes for N iterations. "
        "Wire data into a slot, then wire that SAME slot to the child "
        "node inside. After each iteration the child's output feeds "
        "back to the matching slot for the next round. "
        "Output ports mirror inputs — connect downstream from the same slot."
    ),
    "ports_in": [
        {"name": "slot_1", "type": "ARRAY", "required": False},
        {"name": "slot_2", "type": "ARRAY", "required": False},
        {"name": "slot_3", "type": "ARRAY", "required": False},
        {"name": "slot_4", "type": "NUMBER", "required": False},
    ],
    "ports_out": [
        {"name": "slot_1", "type": "ARRAY", "required": False},
        {"name": "slot_2", "type": "ARRAY", "required": False},
        {"name": "slot_3", "type": "ARRAY", "required": False},
        {"name": "slot_4", "type": "NUMBER", "required": False},
    ],
}
