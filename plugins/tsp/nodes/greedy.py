"""TSP node: Nearest-neighbor greedy solver."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="tsp_greedy",
    label="Greedy TSP",
    category="SOLVER",
    description="Nearest-neighbor greedy TSP solver",
    doc="Builds a tour using nearest-neighbor heuristic starting from node 0.",
    ports_in=[
        Port("dist_matrix", "ARRAY"),
    ],
    ports_out=[
        Port("tour", "ARRAY"),
        Port("tour_length", "NUMBER"),
    ],
)
def tsp_greedy(params, **inputs):
    dist_matrix = inputs["dist_matrix"]
    n = len(dist_matrix)

    visited = np.zeros(n, dtype=np.bool_)
    tour = np.zeros(n, dtype=np.int64)
    tour[0] = 0
    visited[0] = True

    for step in range(1, n):
        current = tour[step - 1]
        dists = dist_matrix[current].copy()
        dists[visited] = np.inf
        nearest = np.argmin(dists)
        tour[step] = nearest
        visited[nearest] = True

    tour_length = 0.0
    for i in range(n):
        tour_length += dist_matrix[tour[i], tour[(i + 1) % n]]

    logger.info(f"Tour: {tour_length:.2f} ({n} cities)")
    return {
        "tour": tour,
        "tour_length": float(tour_length),
    }
