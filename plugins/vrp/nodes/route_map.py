"""Route Map visualization — SVG of VRP routes with colored vehicle paths."""
import numpy as np
from pipestudio.plugin_api import logger

NODE_INFO = {
    "type": "vrp_route_map",
    "label": "Route Map",
    "category": "OUTPUT",
    "description": "Generate SVG map of VRP routes with colored vehicle paths.",
    "ports_in": [
        {"name": "customers", "type": "ARRAY", "required": True},
        {"name": "route_nodes", "type": "ARRAY", "required": True},
        {"name": "route_len", "type": "ARRAY", "required": True},
        {"name": "fleet", "type": "ARRAY", "required": True},
    ],
    "ports_out": [
        {"name": "svg", "type": "STRING"},
    ],
}

# 10 distinct route colors
ROUTE_COLORS = [
    "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
    "#ec4899", "#06b6d4", "#f97316", "#84cc16", "#6366f1",
]


def run(customers, route_nodes, route_len, fleet):
    k = fleet["num_vehicles"]
    depot_ids = fleet["depot"]
    coords = customers[:, :2]

    W, H = 600, 600
    PAD = 30

    xs, ys = coords[:, 0], coords[:, 1]
    x_min, x_max = float(xs.min()), float(xs.max())
    y_min, y_max = float(ys.min()), float(ys.max())
    x_range = x_max - x_min or 1.0
    y_range = y_max - y_min or 1.0

    def tx(x):
        return PAD + (x - x_min) / x_range * (W - 2 * PAD)

    def ty(y):
        return PAD + (y - y_min) / y_range * (H - 2 * PAD)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="background:#1a1a2e;border-radius:8px">',
    ]

    # Draw routes
    total_customers = 0
    for r in range(k):
        rl = int(route_len[r])
        if rl == 0:
            continue
        total_customers += rl
        color = ROUTE_COLORS[r % len(ROUTE_COLORS)]
        depot = int(depot_ids[r])

        # Build path: depot → customers → depot
        path_points = [f"{tx(coords[depot, 0]):.1f},{ty(coords[depot, 1]):.1f}"]
        for pos in range(rl):
            node = int(route_nodes[r, pos])
            path_points.append(f"{tx(coords[node, 0]):.1f},{ty(coords[node, 1]):.1f}")
        # Return to depot
        path_points.append(f"{tx(coords[depot, 0]):.1f},{ty(coords[depot, 1]):.1f}")

        lines.append(
            f'  <polyline points="{" ".join(path_points)}" '
            f'fill="none" stroke="{color}" stroke-width="1.5" opacity="0.8"/>'
        )

    # Draw customer dots
    for i in range(1, len(customers)):
        cx, cy = tx(coords[i, 0]), ty(coords[i, 1])
        lines.append(
            f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="#10b981"/>'
        )

    # Draw depot(s)
    unique_depots = set(int(d) for d in depot_ids)
    for d in unique_depots:
        dx, dy = tx(coords[d, 0]), ty(coords[d, 1])
        lines.append(
            f'  <rect x="{dx - 5:.1f}" y="{dy - 5:.1f}" '
            f'width="10" height="10" fill="#ef4444" rx="2"/>'
        )
        lines.append(
            f'  <text x="{dx + 8:.1f}" y="{dy + 4:.1f}" '
            f'fill="#ef4444" font-size="10" font-family="monospace">depot</text>'
        )

    # Legend
    y_legend = H - 12
    for r in range(k):
        rl = int(route_len[r])
        if rl == 0:
            continue
        color = ROUTE_COLORS[r % len(ROUTE_COLORS)]
        lx = 10 + r * 100
        lines.append(
            f'  <rect x="{lx}" y="{y_legend - 8}" width="8" height="8" '
            f'fill="{color}" rx="1"/>'
        )
        lines.append(
            f'  <text x="{lx + 12}" y="{y_legend}" '
            f'fill="#888" font-size="9" font-family="monospace">'
            f'R{r + 1}({rl})</text>'
        )

    # Info text
    lines.append(
        f'  <text x="{W - 10}" y="15" text-anchor="end" '
        f'fill="#555" font-size="9" font-family="monospace">'
        f'{total_customers} customers | {k} vehicles</text>'
    )

    lines.append('</svg>')
    svg = "\n".join(lines)

    logger.info(f"Route Map: {total_customers} customers, {k} vehicles")
    return svg
