"""Sorting node: Shuffle Segment."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="shuffle_segment",
    label="Shuffle Segment",
    category="DESTROY",
    description="Randomly shuffle a segment of the array",
    doc="Selects a random contiguous segment (10%-50% of array length) and shuffles it in-place. Simulates destroying order in part of the solution.",
    ports_in=[Port("array", "ARRAY")],
    ports_out=[Port("array", "ARRAY")],
)
def shuffle_segment(params, **inputs):
    arr = inputs["array"].copy()
    n = len(arr)
    seg_len = np.random.randint(n // 10, n // 2)
    start = np.random.randint(0, n - seg_len)
    logger.debug(f"Shuffling segment [{start}:{start + seg_len}] ({seg_len} elements)")
    segment = arr[start : start + seg_len]
    np.random.shuffle(segment)
    arr[start : start + seg_len] = segment
    return {"array": arr}
