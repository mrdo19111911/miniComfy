"""TSP node: Generate random 2D points."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="tsp_generate_points",
    label="Generate Points",
    category="INPUT",
    description="Generate random 2D points on a plane",
    doc="Creates N random points with x,y coordinates in [0, 1000].",
    ports_in=[Port("num_points", "NUMBER", default=100)],
    ports_out=[Port("points", "ARRAY")],
)
def tsp_generate_points(params, **inputs):
    n = int(params.get("num_points", 100))
    points = np.random.uniform(0, 1000, size=(n, 2))
    logger.info(f"Generated {n} points in [0,1000]x[0,1000]")
    return {"points": points}
