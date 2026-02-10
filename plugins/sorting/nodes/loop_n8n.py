"""Loop node (n8n style) — single node with back-edge feedback."""
from pipestudio.plugin_api import node, Port


@node(
    type="loop_node",
    label="Loop",
    category="CONTROL",
    description="Loop with back-edge feedback (n8n style).",
    doc=(
        "Single loop control node. Initial data enters via init_1/init_2/init_3. "
        "Each iteration outputs from loop_1/loop_2/loop_3 to the processing chain. "
        "Connect the last processing node back to feedback_1/feedback_2/feedback_3 "
        "(these are back-edges shown as dashed orange lines). After all iterations, "
        "done_1/done_2/done_3 emit the final values to downstream nodes."
    ),
    ports_in=[
        Port("init_1", "ARRAY"),
        Port("init_2", "ARRAY", required=False),
        Port("init_3", "ARRAY", required=False),
        Port("feedback_1", "ARRAY", required=False),
        Port("feedback_2", "ARRAY", required=False),
        Port("feedback_3", "ARRAY", required=False),
        Port("iterations", "NUMBER", default=10),
    ],
    ports_out=[
        Port("loop_1", "ARRAY"),
        Port("loop_2", "ARRAY"),
        Port("loop_3", "ARRAY"),
        Port("done_1", "ARRAY"),
        Port("done_2", "ARRAY"),
        Port("done_3", "ARRAY"),
    ],
)
def loop_node(params, **inputs):
    """Pass-through — actual looping is handled by the executor."""
    return {
        "loop_1": inputs.get("init_1"),
        "loop_2": inputs.get("init_2"),
        "loop_3": inputs.get("init_3"),
        "done_1": inputs.get("init_1"),
        "done_2": inputs.get("init_2"),
        "done_3": inputs.get("init_3"),
    }
