"""TSP node: Map visualization — outputs SVG of points and tour."""
import numpy as np
from pipestudio.plugin_api import node, Port, logger


@node(
    type="tsp_map_visualize",
    label="Map Visualize",
    category="EVALUATION",
    description="Generate SVG map of points and tour route",
    doc="Creates an SVG visualization showing all points and the tour path. Output is an SVG string viewable in the result panel.",
    ports_in=[
        Port("points", "ARRAY"),
        Port("tour", "ARRAY"),
    ],
    ports_out=[
        Port("svg", "STRING"),
        Port("tour_length", "NUMBER"),
    ],
)
def tsp_map_visualize(params, **inputs):
    points = inputs["points"]
    tour = inputs["tour"]
    n = len(tour)

    # Compute tour length
    total = 0.0
    for i in range(n):
        a, b = int(tour[i]), int(tour[(i + 1) % n])
        dx = points[a, 0] - points[b, 0]
        dy = points[a, 1] - points[b, 1]
        total += float(np.sqrt(dx * dx + dy * dy))

    # Normalize points to SVG viewport
    W, H = 600, 600
    PAD = 30
    xs = points[:, 0]
    ys = points[:, 1]
    x_min, x_max = float(xs.min()), float(xs.max())
    y_min, y_max = float(ys.min()), float(ys.max())
    x_range = x_max - x_min or 1.0
    y_range = y_max - y_min or 1.0

    def tx(x):
        return PAD + (x - x_min) / x_range * (W - 2 * PAD)

    def ty(y):
        return PAD + (y - y_min) / y_range * (H - 2 * PAD)

    # Build SVG
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="background:#1a1a2e;border-radius:8px">',
    ]

    # Tour path
    path_points = []
    for i in range(n):
        idx = int(tour[i])
        path_points.append(f"{tx(points[idx, 0]):.1f},{ty(points[idx, 1]):.1f}")
    # Close the loop
    idx0 = int(tour[0])
    path_points.append(f"{tx(points[idx0, 0]):.1f},{ty(points[idx0, 1]):.1f}")
    lines.append(
        f'  <polyline points="{" ".join(path_points)}" '
        f'fill="none" stroke="#3b82f6" stroke-width="1.5" opacity="0.7"/>'
    )

    # Points
    for i in range(len(points)):
        cx = tx(points[i, 0])
        cy = ty(points[i, 1])
        color = "#ef4444" if i == int(tour[0]) else "#10b981"
        r = "4" if i == int(tour[0]) else "2.5"
        lines.append(
            f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}"/>'
        )

    # Start label
    sx = tx(points[int(tour[0]), 0])
    sy = ty(points[int(tour[0]), 1])
    lines.append(
        f'  <text x="{sx + 6:.1f}" y="{sy - 6:.1f}" '
        f'fill="#ef4444" font-size="11" font-family="monospace">start</text>'
    )

    # Info text
    lines.append(
        f'  <text x="10" y="{H - 10}" fill="#888" font-size="11" '
        f'font-family="monospace">{n} cities | length: {total:.1f}</text>'
    )

    lines.append('</svg>')
    svg = "\n".join(lines)

    logger.info(f"Map: {n} cities, tour={total:.2f}")
    return {
        "svg": svg,
        "tour_length": total,
    }
