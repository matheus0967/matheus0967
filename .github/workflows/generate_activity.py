#!/usr/bin/env python3
"""Generate a monochrome particle-terrain contribution graph from GitHub GraphQL."""
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ["GITHUB_USERNAME"]
TOKEN = os.environ["GH_TOKEN"]
OUTPUT = Path("src/activity.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

def fetch_calendar():
    payload = json.dumps({
        "query": QUERY,
        "variables": {"login": USERNAME}
    }).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "github-contribution-visual"
        },
        method="POST"
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode())
    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL error: " + str(result["errors"]))
    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {USERNAME}")
    return user["contributionsCollection"]["contributionCalendar"]

def generate_svg(calendar):
    days = [
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ][-364:]
    if not days:
        raise RuntimeError("No contribution data returned.")

    values = [int(day["contributionCount"]) for day in days]
    max_value = max(values) or 1
    total = int(calendar["totalContributions"])

    # 52 weekly columns, seven daily rows; missing days are padded with zero.
    values = ([0] * max(0, 364 - len(values))) + values
    weeks = [values[i:i + 7] for i in range(0, 364, 7)]
    weekly = [sum(week) for week in weeks]
    peak = max(weekly) or 1

    width, height = 1000, 560
    center_x, base_y = 500, 310
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub contribution activity for {escape(USERNAME)}">',
        '<defs><radialGradient id="glow"><stop offset="0" stop-color="#fff" stop-opacity=".95"/><stop offset="1" stop-color="#fff" stop-opacity=".05"/></radialGradient></defs>',
        '<rect width="100%" height="100%" fill="#050505"/>',
        '<g fill="#bdbdbd" font-family="monospace">',
        '<text x="34" y="38" font-size="15" letter-spacing="3">CONTRIBUTION ANALYTICS</text>',
        f'<text x="966" y="38" text-anchor="end" font-size="12">{escape(USERNAME.upper())} / LAST 52 WEEKS</text>',
        '</g>',
        '<g stroke="#777" stroke-opacity=".18" stroke-width="1">'
    ]

    # Subtle technical grid.
    for x in range(60, 961, 75):
        parts.append(f'<path d="M{x} 85 V475"/>')
    for y in range(110, 476, 45):
        parts.append(f'<path d="M35 {y} H965"/>')
    parts.append('</g>')

    # Particle terrain: a perspective surface whose height is driven by weekly commits.
    # Dense secondary particles add the atmospheric, data-visualization look.
    for row in range(25):
        depth = row / 24
        for col in range(104):
            week_index = min(51, int(col / 2))
            activity = weekly[week_index] / peak
            neighbor = weekly[max(0, week_index - 1)] / peak
            next_neighbor = weekly[min(51, week_index + 1)] / peak
            smooth = (neighbor + 2 * activity + next_neighbor) / 4
            ridge = (smooth ** 0.72) * (1 - depth * 0.28)
            ripple = 0.035 * (1 + __import__("math").sin(col * .43 + row * .31))
            z = ridge + ripple
            x = 55 + col * 8.65 + (depth - .5) * 30
            y = base_y + depth * 142 - z * 205 + (col - 52) * (depth - .5) * .23
            radius = 0.65 + smooth * 1.25
            opacity = min(.92, .22 + smooth * .68)
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.2f}" '
                f'fill="#f2f2f2" opacity="{opacity:.2f}"/>'
            )

    # Fine point-cloud traces on the front edge.
    for col in range(104):
        week_index = min(51, int(col / 2))
        activity = weekly[week_index] / peak
        x = 55 + col * 8.65
        y = 455 - activity * 78
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.1" fill="#fff" opacity=".42"/>')

    # Compact lower contribution strip (daily activity intensity).
    parts.append('<g transform="translate(55 495)">')
    for index, value in enumerate(values):
        intensity = value / max_value
        opacity = .12 + intensity * .82
        x = (index % 52) * 17
        y = (index // 52) * 7
        parts.append(
            f'<rect x="{x}" y="{y}" width="11" height="4" rx="1" '
            f'fill="#fff" opacity="{opacity:.2f}"/>'
        )
    parts.append('</g>')

    parts.extend([
        '<g font-family="monospace" fill="#d8d8d8">',
        f'<text x="55" y="465" font-size="30" font-weight="bold">{total:,}</text>',
        '<text x="55" y="483" font-size="10" letter-spacing="2" fill="#888">TOTAL CONTRIBUTIONS</text>',
        f'<text x="965" y="465" text-anchor="end" font-size="12" fill="#888">PEAK WEEK: {peak}</text>',
        '<text x="965" y="545" text-anchor="end" font-size="10" fill="#777">SOURCE: GITHUB CONTRIBUTION CALENDAR</text>',
        '</g>',
        '</svg>'
    ])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(parts), encoding="utf-8")

if __name__ == "__main__":
    generate_svg(fetch_calendar())
    print(f"Generated {OUTPUT}")
