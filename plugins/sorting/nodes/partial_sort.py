"""Sorting node: Partial Sort."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="partial_sort",
    label="Partial Sort",
    category="REPAIR",
    description="Sort using a sliding window",
    doc="Applies sorted() to overlapping windows of the given size across the array. Gradually improves order without full sort.",
    ports_in=[
        Port("array", "ARRAY"),
        Port("window", "NUMBER", default=50),
    ],
    ports_out=[Port("array", "ARRAY")],
)
def partial_sort(params, **inputs):
    arr = inputs["array"].copy()
    window = int(params.get("window", 50))
    n = len(arr)
    swaps = 0
    for i in range(0, n - window + 1, window // 2):
        old = arr[i : i + window].copy()
        arr[i : i + window] = np.sort(arr[i : i + window])
        swaps += int(np.sum(old != arr[i : i + window]))
    logger.info(f"window={window}: {swaps} elements moved")
    return {"array": arr}
