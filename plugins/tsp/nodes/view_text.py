"""TSP node: View any data as text."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


def _format_value(key, val):
    """Format a single input value as readable text lines."""
    lines = []
    if isinstance(val, np.ndarray):
        if val.ndim == 1:
            lines.append(f"[{key}] {len(val)} items")
            lines.append(", ".join(str(int(x) if x == int(x) else round(float(x), 2)) for x in val[:50]))
            if len(val) > 50:
                lines.append(f"  ... ({len(val) - 50} more)")
        elif val.ndim == 2:
            rows, cols = val.shape
            lines.append(f"[{key}] {rows}x{cols} matrix")
            for r in range(min(rows, 10)):
                row_str = "  " + " ".join(f"{val[r, c]:7.1f}" for c in range(min(cols, 8)))
                if cols > 8:
                    row_str += " ..."
                lines.append(row_str)
            if rows > 10:
                lines.append(f"  ... ({rows - 10} more rows)")
        else:
            lines.append(f"[{key}] ndarray shape={val.shape}")
    elif isinstance(val, (int, float, np.integer, np.floating)):
        lines.append(f"[{key}] {float(val):.6f}")
    else:
        lines.append(f"[{key}] {val}")
    return lines


@node(
    type="tsp_view_text",
    label="View Text",
    category="UTILITY",
    description="Display any connected data as text",
    doc="Connect any port(s) to view contents. Has multiple input slots for arrays, numbers, and text.",
    ports_in=[
        Port("data_1", "ARRAY", required=False),
        Port("data_2", "ARRAY", required=False),
        Port("value_1", "NUMBER", required=False),
        Port("value_2", "NUMBER", required=False),
        Port("text_in", "STRING", required=False),
    ],
    ports_out=[
        Port("text", "STRING"),
    ],
)
def tsp_view_text(params, **inputs):
    lines = []
    for key in sorted(inputs.keys()):
        lines.extend(_format_value(key, inputs[key]))

    text = "\n".join(lines) if lines else "(no inputs connected)"
    logger.info(text)
    return {"text": text}
