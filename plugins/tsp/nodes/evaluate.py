"""TSP node: Evaluate and summarize tour quality."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="tsp_evaluate",
    label="Evaluate Tour",
    category="EVALUATION",
    description="Evaluate and summarize TSP tour quality",
    doc="Computes tour length, average/longest/shortest edge statistics.",
    ports_in=[
        Port("dist_matrix", "ARRAY"),
        Port("tour", "ARRAY"),
    ],
    ports_out=[
        Port("tour_length", "NUMBER"),
        Port("avg_edge", "NUMBER"),
        Port("longest_edge", "NUMBER"),
        Port("shortest_edge", "NUMBER"),
    ],
)
def tsp_evaluate(params, **inputs):
    dist_matrix = inputs["dist_matrix"]
    tour = inputs["tour"]
    n = len(tour)

    edge_lengths = np.array([
        dist_matrix[tour[i], tour[(i + 1) % n]] for i in range(n)
    ])
    total = float(np.sum(edge_lengths))
    avg = float(np.mean(edge_lengths))
    longest = float(np.max(edge_lengths))
    shortest = float(np.min(edge_lengths))

    logger.info(f"Length={total:.2f}, avg={avg:.2f}, max={longest:.2f}, min={shortest:.2f}")
    return {
        "tour_length": total,
        "avg_edge": avg,
        "longest_edge": longest,
        "shortest_edge": shortest,
    }
