"""Render numeric capture observations as an SVG, without external resources."""

from math import isfinite


def render_chart(points):
    """Three independent unit-labelled axes; never interpolate missing samples."""
    safe = [
        p
        for p in points[:600]
        if len(p) == 4 and all(isinstance(v, int | float) and isfinite(v) for v in p)
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 510" role="img">',
        "<title>WENDOUGEE DATA S captured shot observations</title>",
        '<rect width="800" height="510" rx="20" fill="#202124"/>',
        '<g font-family="sans-serif" fill="#faf6f2" font-size="17">',
        '<text x="24" y="30">Captured shot · observations, not final cup yield</text>',
    ]
    if len(safe) < 2:
        parts.append(
            '<text x="24" y="85">No detailed captured shot yet.</text>'
            '<text x="24" y="115">Routine polling is not a shot curve.</text>'
        )
    else:
        duration = max(1, max(p[0] for p in safe))
        for index, label, color in (
            (1, "Pressure (bar)", "#83c5ff"),
            (2, "Pumped water (mL)", "#d5a58e"),
            (3, "Scale reading (g)", "#c6afd9"),
        ):
            top = 64 + (index - 1) * 140
            low = min(0, min(p[index] for p in safe))
            high = max(low + 1, max(p[index] for p in safe))
            parts.append(f'<text x="24" y="{top}">{label} · {low:g} to {high:g}</text>')
            parts.append(
                f'<path d="M 50 {top + 12} V {top + 105} H 775" '
                'fill="none" stroke="#777"/>'
            )
            segments = [[]]
            previous = None
            for point in safe:
                if previous is not None and not 0 <= point[0] - previous <= 2:
                    segments.append([])
                x = 50 + point[0] / duration * 725
                y = top + 105 - (point[index] - low) / (high - low) * 88
                segments[-1].append(f"{x:.2f},{y:.2f}")
                previous = point[0]
            for segment in segments:
                coords = " ".join(segment)
                parts.append(
                    f'<polyline points="{coords}" fill="none" '
                    f'stroke="{color}" stroke-width="2.5"/>'
                )
        parts.append(
            f'<text x="24" y="492">0 to {duration:g} seconds since first retained '
            "active sample · gaps left open</text>"
        )
    return ("".join(parts) + "</g></svg>").encode()
