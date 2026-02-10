"""TSP node: Log tour details on demand."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="tsp_log_tour",
    label="Log Tour",
    category="UTILITY",
    description="Print tour sequence and per-edge distances to log",
    doc="Logs the full tour order and each edge distance. Connect when you need to inspect the tour details.",
    ports_in=[
        Port("tour", "ARRAY"),
        Port("dist_matrix", "ARRAY"),
    ],
    ports_out=[
        Port("tour", "ARRAY"),
        Port("tour_length", "NUMBER"),
    ],
)
def tsp_log_tour(params, **inputs):
    tour = inputs["tour"]
    dist_matrix = inputs["dist_matrix"]
    n = len(tour)

    edges = []
    total = 0.0
    for i in range(n):
        a, b = int(tour[i]), int(tour[(i + 1) % n])
        d = float(dist_matrix[a, b])
        total += d
        edges.append(f"  {a} -> {b}: {d:.1f}")

    logger.info(f"Tour ({n} cities, length={total:.2f}):")
    logger.info(f"  Order: {' -> '.join(str(int(x)) for x in tour)} -> {int(tour[0])}")

    # Log edges in chunks to avoid huge single messages
    chunk = 20
    for i in range(0, len(edges), chunk):
        logger.info("\n".join(edges[i:i + chunk]))

    return {
        "tour": tour,
        "tour_length": total,
    }
