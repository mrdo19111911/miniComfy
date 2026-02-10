"""Sorting node: Bubble Pass."""
from pipestudio.plugin_api import node, Port, logger


@node(
    type="bubble_pass",
    label="Bubble Pass",
    category="REPAIR",
    description="One pass of bubble sort",
    doc="Performs a single left-to-right pass of bubble sort, swapping adjacent out-of-order pairs. Lightweight repair operator.",
    ports_in=[Port("array", "ARRAY")],
    ports_out=[Port("array", "ARRAY")],
)
def bubble_pass(params, **inputs):
    arr = inputs["array"].copy()
    swaps = 0
    for i in range(len(arr) - 1):
        if arr[i] > arr[i + 1]:
            arr[i], arr[i + 1] = arr[i + 1], arr[i]
            swaps += 1
    logger.info(f"Bubble pass: {swaps} swaps")
    return {"array": arr}
