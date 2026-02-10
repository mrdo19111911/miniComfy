"""Sorting node: Generate Array."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="generate_array",
    label="Generate Array",
    category="INPUT",
    description="Generate a random numpy array of integers",
    doc="Creates an array of N random integers between 0 and 9999. Use as the starting input for any sorting workflow.",
    ports_in=[Port("size", "NUMBER", default=1000)],
    ports_out=[Port("array", "ARRAY")],
)
def generate_array(params, **inputs):
    size = int(params.get("size", 1000))
    arr = np.random.randint(0, 10000, size=size)
    logger.info(f"{size} elements, range [{arr.min()}, {arr.max()}]")
    return {"array": arr}
