"""TSP node: Evaluate and summarize tour quality."""
import numpy as np
from pipestudio.plugin_api import logger

NODE_INFO = {
    "type": "tsp_evaluate",
    "label": "Evaluate Tour",
    "category": "EVALUATION",
    "description": "Evaluate and summarize TSP tour quality",
    "doc": "Computes tour length, average/longest/shortest edge statistics.",
    "ports_in": [
        {"name": "dist_matrix", "type": "ARRAY"},
        {"name": "tour", "type": "ARRAY"},
    ],
    "ports_out": [
        {"name": "tour_length", "type": "NUMBER"},
        {"name": "avg_edge", "type": "NUMBER"},
        {"name": "longest_edge", "type": "NUMBER"},
        {"name": "shortest_edge", "type": "NUMBER"},
    ],
}


def run(dist_matrix, tour):
    n = len(tour)

    edge_lengths = np.array([
        dist_matrix[tour[i], tour[(i + 1) % n]] for i in range(n)
    ])
    total = float(np.sum(edge_lengths))
    avg = float(np.mean(edge_lengths))
    longest = float(np.max(edge_lengths))
    shortest = float(np.min(edge_lengths))

    logger.info(f"Length={total:.2f}, avg={avg:.2f}, max={longest:.2f}, min={shortest:.2f}")
    return total, avg, longest, shortest
