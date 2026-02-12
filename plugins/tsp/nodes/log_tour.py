"""TSP node: Log tour details on demand."""
from pipestudio.plugin_api import logger

NODE_INFO = {
    "type": "tsp_log_tour",
    "label": "Log Tour",
    "category": "UTILITY",
    "description": "Print tour sequence and per-edge distances to log",
    "doc": "Logs the full tour order and each edge distance. Connect when you need to inspect the tour details.",
    "ports_in": [
        {"name": "tour", "type": "ARRAY"},
        {"name": "dist_matrix", "type": "ARRAY"},
    ],
    "ports_out": [
        {"name": "tour", "type": "ARRAY"},
        {"name": "tour_length", "type": "NUMBER"},
    ],
}


def run(tour, dist_matrix):
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

    return tour, total
