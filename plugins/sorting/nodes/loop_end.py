"""Loop End node (ComfyUI style) — marks end of a loop pair."""
from pipestudio.plugin_api import node, Port


@node(
    type="loop_end",
    label="Loop End",
    category="CONTROL",
    description="End of a loop. Pair with Loop Start.",
    doc=(
        "Marks the end of a ComfyUI-style loop. Collects results from the loop body "
        "via in_1/in_2/in_3 and feeds them back to the paired Loop Start for the next "
        "iteration. After the final iteration, outputs flow to downstream nodes. "
        "Set 'pair_id' in params to the ID of the corresponding Loop Start node."
    ),
    ports_in=[
        Port("in_1", "ARRAY", required=False),
        Port("in_2", "ARRAY", required=False),
        Port("in_3", "ARRAY", required=False),
    ],
    ports_out=[
        Port("out_1", "ARRAY"),
        Port("out_2", "ARRAY"),
        Port("out_3", "ARRAY"),
    ],
)
def loop_end(params, **inputs):
    """Pass-through — actual looping is handled by the executor."""
    return {
        "out_1": inputs.get("in_1"),
        "out_2": inputs.get("in_2"),
        "out_3": inputs.get("in_3"),
    }
