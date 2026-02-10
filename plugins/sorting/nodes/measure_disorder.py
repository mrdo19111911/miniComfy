"""Sorting node: Measure Disorder."""
from pipestudio.plugin_api import node, Port, logger


@node(
    type="measure_disorder",
    label="Measure Disorder",
    category="EVALUATION",
    description="Count inversions and compute sorted ratio",
    doc="Counts the number of adjacent inversions (arr[i] > arr[i+1]) and computes a sorted ratio from 0.0 (random) to 1.0 (fully sorted).",
    ports_in=[Port("array", "ARRAY")],
    ports_out=[
        Port("score", "NUMBER"),
    ],
)
def measure_disorder(params, **inputs):
    arr = inputs["array"]
    n = len(arr)
    inversions = sum(1 for i in range(n - 1) if arr[i] > arr[i + 1])
    score = 1.0 - (inversions / max(n - 1, 1))
    logger.info(f"{inversions} inversions, score={score:.4f}")
    return {"score": float(score)}
