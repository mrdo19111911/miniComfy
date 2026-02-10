"""TSP node: 2-opt local search improvement."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="tsp_2opt",
    label="2-Opt Local Search",
    category="SOLVER",
    description="Improve tour with 2-opt swaps",
    doc="Iteratively reverses tour segments to reduce total length.",
    ports_in=[
        Port("dist_matrix", "ARRAY"),
        Port("tour", "ARRAY"),
        Port("max_iterations", "NUMBER", default=100),
    ],
    ports_out=[
        Port("tour", "ARRAY"),
        Port("tour_length", "NUMBER"),
        Port("improvement", "NUMBER"),
    ],
)
def tsp_2opt(params, **inputs):
    dist_matrix = inputs["dist_matrix"]
    tour = inputs["tour"].copy()
    max_iter = int(params.get("max_iterations", 100))
    n = len(tour)

    def tour_length(t):
        length = 0.0
        for i in range(n):
            length += dist_matrix[t[i], t[(i + 1) % n]]
        return length

    initial_length = tour_length(tour)
    best_length = initial_length

    for iteration in range(max_iter):
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                d1 = dist_matrix[tour[i - 1], tour[i]] + dist_matrix[tour[j], tour[(j + 1) % n]]
                d2 = dist_matrix[tour[i - 1], tour[j]] + dist_matrix[tour[i], tour[(j + 1) % n]]
                if d2 < d1 - 1e-10:
                    tour[i:j + 1] = tour[i:j + 1][::-1]
                    best_length -= (d1 - d2)
                    improved = True
        if not improved:
            break

    improvement = initial_length - best_length
    pct = (improvement / initial_length) * 100 if initial_length > 0 else 0
    logger.info(f"{initial_length:.2f} -> {best_length:.2f} (-{pct:.1f}%, {iteration + 1} iters)")
    return {
        "tour": tour,
        "tour_length": float(best_length),
        "improvement": float(improvement),
    }
