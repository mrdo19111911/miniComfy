"""Loop Start node (ComfyUI style) — marks beginning of a loop pair."""
from pipestudio.plugin_api import node, Port


@node(
    type="loop_start",
    label="Loop Start",
    category="CONTROL",
    description="Start of a loop. Pair with Loop End.",
    doc=(
        "Marks the beginning of a ComfyUI-style loop. Data enters via in_1/in_2/in_3 "
        "and passes to the loop body via out_1/out_2/out_3. After each iteration, the "
        "paired Loop End feeds results back so the next iteration receives improved data. "
        "Set 'iterations' to control how many times the loop body executes."
    ),
    ports_in=[
        Port("in_1", "ARRAY"),
        Port("in_2", "ARRAY", required=False),
        Port("in_3", "ARRAY", required=False),
        Port("iterations", "NUMBER", default=10),
    ],
    ports_out=[
        Port("out_1", "ARRAY"),
        Port("out_2", "ARRAY"),
        Port("out_3", "ARRAY"),
    ],
)
def loop_start(params, **inputs):
    """Pass-through — actual looping is handled by the executor."""
    return {
        "out_1": inputs.get("in_1"),
        "out_2": inputs.get("in_2"),
        "out_3": inputs.get("in_3"),
    }
