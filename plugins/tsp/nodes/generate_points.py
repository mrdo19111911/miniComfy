"""TSP node: Generate random 2D points."""
import numpy as np
from pipestudio.plugin_api import logger

NODE_INFO = {
    "type": "tsp_generate_points",
    "label": "Generate Points",
    "category": "INPUT",
    "description": "Generate random 2D points on a plane",
    "doc": "Creates N random points with x,y coordinates in [0, 1000].",
    "ports_in": [{"name": "num_points", "type": "NUMBER", "default": 100}],
    "ports_out": [{"name": "points", "type": "ARRAY"}],
}


def run(num_points=100):
    n = int(num_points)
    points = np.random.uniform(0, 1000, size=(n, 2))
    logger.info(f"Generated {n} points in [0,1000]x[0,1000]")
    return points
