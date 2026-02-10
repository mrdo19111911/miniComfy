"""TSP node: Compute Euclidean distance matrix."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="tsp_distance_matrix",
    label="Distance Matrix",
    category="COMPUTE",
    description="Compute Euclidean distance matrix from points",
    doc="Takes (N,2) point coordinates, outputs N x N distance matrix.",
    ports_in=[Port("points", "ARRAY")],
    ports_out=[Port("dist_matrix", "ARRAY")],
)
def tsp_distance_matrix(params, **inputs):
    points = inputs["points"]
    n = len(points)
    diff = points[:, np.newaxis, :] - points[np.newaxis, :, :]
    dist_matrix = np.sqrt(np.sum(diff ** 2, axis=2))
    logger.info(f"{n}x{n} matrix")
    return {"dist_matrix": dist_matrix}
