"""Sorting node: Reverse Segment."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="reverse_segment",
    label="Reverse Segment",
    category="DESTROY",
    description="Reverse a random segment of the array",
    doc="Selects a random contiguous segment and reverses it. A targeted destroy operator that creates localized disorder.",
    ports_in=[Port("array", "ARRAY")],
    ports_out=[Port("array", "ARRAY")],
)
def reverse_segment(params, **inputs):
    arr = inputs["array"].copy()
    n = len(arr)
    seg_len = np.random.randint(n // 10, n // 2)
    start = np.random.randint(0, n - seg_len)
    logger.debug(f"Reversing segment [{start}:{start + seg_len}]")
    arr[start : start + seg_len] = arr[start : start + seg_len][::-1]
    return {"array": arr}
