from __future__ import annotations

from pathlib import Path

from dep_age.scoring.summary import HealthSummary

BADGE_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="a">
    <rect width="{width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#a)">
    <rect width="50" height="20" fill="#555"/>
    <rect x="50" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{width}" height="20" fill="url(#b)"/>
  </g>
  <g fill="#fff" text-anchor="middle"
     font-family="Verdana,Geneva,DejaVu Sans,sans-serif"
     font-size="11">
    <text x="25" y="15" fill="#010101" fill-opacity=".3">deps</text>
    <text x="25" y="14">deps</text>
    <text x="{text_x}" y="15" fill="#010101" fill-opacity=".3">{text}</text>
    <text x="{text_x}" y="14">{text}</text>
  </g>
</svg>"""


def render_badge(summary: HealthSummary, output_file: str | None = None) -> str:
    score = summary.score
    fresh_pct = (summary.fresh * 100 // summary.total) if summary.total > 0 else 100
    text = f"{fresh_pct}% fresh"

    if score >= 80:
        color = "#4c1"  # green
    elif score >= 60:
        color = "#dfb317"  # yellow
    elif score >= 40:
        color = "#fe7d37"  # orange
    else:
        color = "#e05d44"  # red

    value_width = max(len(text) * 7 + 10, 60)
    width = 50 + value_width
    text_x = 50 + value_width // 2

    svg = BADGE_TEMPLATE.format(
        width=width,
        value_width=value_width,
        color=color,
        text=text,
        text_x=text_x,
    )

    if output_file:
        Path(output_file).write_text(svg, encoding="utf-8")
    return svg
