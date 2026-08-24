#!/usr/bin/env python3
"""Post-process the 3D contribution graph into the HUD-framed telemetry
component (assets/telemetry-unit.svg) with sky-drop towers, glow pulse,
light sweep and digital rain.

Usage: compose_telemetry.py <3d.svg> <out.svg> [stats.json]

The generator's built-in SMIL rise animation is stripped and replaced
with staggered CSS animations keyed off the isometric grid basis.
"""

import json
import re
import sys
from datetime import date, timedelta

# 3D floor geometry (from github-profile-3d-contrib output, 1280x850 canvas)
ORIGIN = (140.0, 154.18)     # tile (col=0,row=0) north corner
WEEK = (20.0, 11.545)        # +1 column (week)
DAY = (-20.0, 11.545)        # +1 row (day)


def load(path: str):
    s = open(path, encoding="utf-8").read()
    s = re.sub(r"<\?xml[^>]*\?>", "", s)
    s = re.sub(r"<!DOCTYPE[^>]*>", "", s).strip()
    tag = re.search(r"<svg[^>]*>", s).group(0)
    vb = re.search(r'viewBox="([^"]+)"', tag)
    if vb:
        _, _, w, h = (float(v) for v in vb.group(1).replace(",", " ").split())
    else:
        w = float(re.search(r'width="([0-9.]+)', tag).group(1))
        h = float(re.search(r'height="([0-9.]+)', tag).group(1))
        s = s.replace(tag, tag[:-1] + f' viewBox="0 0 {w} {h}">', 1)
    return s, w, h


def place(svg: str, x: float, y: float, w: float, h: float) -> str:
    tag = re.search(r"<svg[^>]*>", svg).group(0)
    new = re.sub(r'\s(?:width|height|x|y)="[^"]*"', "", tag)
    new = new[:-1] + f' x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}">'
    return svg.replace(tag, new, 1)


FLOOR_FILLS = {"rgb(68, 68, 68)", "rgb(57, 57, 57)", "rgb(48, 48, 48)"}
GROUP_RE = re.compile(r'<g transform="translate\(([0-9.\- ]+)\)">(.*?)</g>', re.S)


def animate_towers(iso_svg: str) -> str:
    """Replace the generator's SMIL rise animation on contribution towers
    with a staggered sky-drop (CSS), and add a glow pulse to the tallest."""
    heights = []
    for _, body in GROUP_RE.findall(iso_svg):
        fills = set(re.findall(r'fill="(rgb\([^)]*\))"', body))
        if fills and not fills <= FLOOR_FILLS:
            heights.append(max(float(h) for h in re.findall(r'height="([0-9.]+)"', body)))
    glow_h = sorted(heights)[max(0, len(heights) - max(3, len(heights) // 4))] if heights else 1e9

    def repl(m):
        pos, body = m.group(1), m.group(2)
        fills = set(re.findall(r'fill="(rgb\([^)]*\))"', body))
        if not fills or fills <= FLOOR_FILLS:
            return m.group(0)
        body = re.sub(r"<animate(?:Transform)?[^>]*>.*?</animate(?:Transform)?>", "", body, flags=re.S)
        body = re.sub(r"<animate(?:Transform)?[^>]*/>", "", body)
        x, y = (float(v) for v in pos.split())
        col = ((x - ORIGIN[0]) / WEEK[0] + (y - ORIGIN[1]) / WEEK[1]) / 2
        row = ((y - ORIGIN[1]) / DAY[1] - (x - ORIGIN[0]) / WEEK[0]) / 2
        delay = 0.2 + col * 0.03 + row * 0.06
        tall = max(float(h) for h in re.findall(r'height="([0-9.]+)"', body)) >= glow_h
        cls = "twr twrGlow" if tall else "twr"
        return (
            f'<g transform="translate({pos})">'
            f'<g class="{cls}" style="animation-delay:{delay:.2f}s">{body}</g></g>'
        )

    return GROUP_RE.sub(repl, iso_svg)


def ambient_overlay() -> str:
    """Light sweep across the scene plus sparse digital rain (injected into
    the 3D document; rain goes behind the graph, sweep above it)."""
    rain = []
    for i in range(16):
        rx = (i * 271 + 97) % 1240 + 20
        ry = (i * 113) % 220 + 30
        dur = 3.2 + (i * 7 % 10) * 0.35
        dly = (i * 131 % 100) / 25.0
        rain.append(
            f'<line class="tcRain" x1="{rx}" y1="{ry}" x2="{rx}" y2="{ry + 14}" '
            f'style="animation-duration:{dur:.2f}s;animation-delay:{dly:.2f}s"/>'
        )
    return "".join(rain)


IN_ISO_STYLE = """<style>
.twr{animation:twrDrop .9s cubic-bezier(.3,1.35,.45,1) backwards;}
@keyframes twrDrop{from{transform:translateY(-680px);opacity:0}18%{opacity:1}to{transform:translateY(0);opacity:1}}
.twrGlow{animation:twrDrop .9s cubic-bezier(.3,1.35,.45,1) backwards,twrPulse 3.4s 2s ease-in-out infinite;}
@keyframes twrPulse{0%,100%{filter:drop-shadow(0 0 2px #00FF41)}50%{filter:drop-shadow(0 0 9px #00FF41)}}
.tcRain{stroke:#00F0FF;stroke-width:1.5;opacity:0;animation:tcFall 4s linear infinite;}
@keyframes tcFall{0%{transform:translateY(0);opacity:0}12%{opacity:.3}80%{opacity:.2}100%{transform:translateY(430px);opacity:0}}
.tcSweepG{animation:tcSweep 9s 2.5s linear infinite;}
@keyframes tcSweep{from{transform:translateX(0)}to{transform:translateX(1900px)}}
@media (prefers-reduced-motion:reduce){*{animation:none !important;}}
</style>"""

def heat_color(n: int) -> str:
    if n == 0:
        return "#0E1A22"
    if n <= 2:
        return "#01441F"
    if n <= 5:
        return "#0F8C3A"
    if n <= 9:
        return "#00C647"
    return "#00FF41"


def stats_panel(stats_path: str, y: float, w: int):
    """Render a stats strip (mini heatmap + counters) from a GitHub GraphQL
    contributionsCollection JSON dump. Returns (svg, height); ("", 0) when
    no stats file is available so the composition degrades gracefully."""
    try:
        data = json.load(open(stats_path))["data"]["user"]
    except (OSError, KeyError, ValueError):
        return "", 0

    cal = data["contributionsCollection"]["contributionCalendar"]
    total = cal["totalContributions"]
    followers = data["followers"]["totalCount"]
    days = [d for wk in cal["weeks"] for d in wk["contributionDays"]]
    days.sort(key=lambda d: d["date"])

    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    current = 0
    idx = len(days) - 1
    if days and days[idx]["contributionCount"] == 0 and days[idx]["date"] == date.today().isoformat():
        idx -= 1  # today hasn't been committed on yet; streak not broken
    while idx >= 0 and days[idx]["contributionCount"] > 0:
        current += 1
        idx -= 1

    parts = [f'<line x1="30" y1="{y:g}" x2="{w - 30}" y2="{y:g}" stroke="url(#tcNeon)" stroke-width="0.8" opacity="0.5"/>']
    hx, hy = 42, y + 14
    for wi, wk in enumerate(cal["weeks"]):
        for d in wk["contributionDays"]:
            di = (date.fromisoformat(d["date"]).weekday() + 1) % 7
            parts.append(
                f'<rect x="{hx + wi * 6}" y="{hy + di * 6:g}" width="5" height="5" '
                f'fill="{heat_color(d["contributionCount"])}"/>'
            )
    tx = hx + 53 * 6 + 40
    rows = [
        ("CONTRIBUTIONS [1Y]", str(total), "#00FF41"),
        ("CURRENT STREAK", f"{current}d", "#00F0FF"),
        ("LONGEST STREAK", f"{longest}d", "#00F0FF"),
        ("FOLLOWERS", str(followers), "#B44CFF"),
    ]
    for i, (label, val, color) in enumerate(rows):
        ry = hy + 10 + i * 15
        parts.append(f'<text x="{tx}" y="{ry:g}" class="tcMono" font-size="12" letter-spacing="1" fill="#7A8B99">{label}</text>')
        parts.append(f'<text x="{tx + 220}" y="{ry:g}" class="tcMono" font-size="12" letter-spacing="1" fill="{color}" font-weight="bold">{val}</text>')
    return "".join(parts), 72


SWEEP = (
    '<linearGradient id="tcSweepFill" x1="0" y1="0" x2="1" y2="0">'
    '<stop offset="0" stop-color="#00F0FF" stop-opacity="0"/>'
    '<stop offset="0.5" stop-color="#00F0FF" stop-opacity="0.05"/>'
    '<stop offset="1" stop-color="#00F0FF" stop-opacity="0"/></linearGradient>'
    '<g class="tcSweepG"><rect x="-420" y="0" width="300" height="850" '
    'fill="url(#tcSweepFill)" transform="skewX(-10)"/></g>'
)


def main() -> None:
    iso_path, out_path = sys.argv[1], sys.argv[2]
    stats_path = sys.argv[3] if len(sys.argv) > 3 else ""

    iso, iso_w, iso_h = load(iso_path)

    iso = animate_towers(iso)
    bg_tag = re.search(r'<rect x="0" y="0" width="\d+" height="\d+" fill="#00000f">\s*</rect>|<rect x="0" y="0" width="\d+" height="\d+" fill="#00000f"/>', iso).group(0)
    iso = iso.replace(bg_tag, bg_tag + ambient_overlay(), 1)
    iso = iso.replace("</svg>", IN_ISO_STYLE + SWEEP + "</svg>", 1)

    W = 900
    content_x, content_w = 25, 850
    iso_hs = content_w * iso_h / iso_w

    title_h, foot_h = 58, 46
    y_iso = title_h + 6
    y_stats = y_iso + iso_hs + 8
    stats_svg, stats_h = stats_panel(stats_path, y_stats, W) if stats_path else ("", 0)
    y_foot = y_stats + stats_h + 8
    H = y_foot + foot_h + 12

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:g}" '
        f'viewBox="0 0 {W} {H:g}" role="img" aria-label="telemetry unit">'
    )
    parts.append(
        """<defs>
<linearGradient id="tcNeon" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="#00F0FF"/><stop offset="0.5" stop-color="#00FF41"/><stop offset="1" stop-color="#B44CFF"/>
</linearGradient>
<style>
.tcMono{font-family:'Courier New',Courier,monospace;}
@keyframes tcBlink{0%,49%{opacity:1}50%,100%{opacity:0}}
.tcBlink{animation:tcBlink 1s step-end infinite;}
@keyframes tcDash{to{stroke-dashoffset:-560;}}
.tcStream{stroke-dasharray:8 10;animation:tcDash 8s linear infinite;}
@keyframes tcPulse{0%,100%{opacity:.5}50%{opacity:1}}
.tcPulse{animation:tcPulse 2.3s ease-in-out infinite;}
@media (prefers-reduced-motion:reduce){*{animation:none !important;}}
</style>
</defs>"""
    )

    parts.append(f'<rect width="{W}" height="{H:g}" fill="#050A0F"/>')
    parts.append(
        f'<rect x="10" y="10" width="{W - 20}" height="{H - 20:g}" fill="none" '
        f'stroke="url(#tcNeon)" stroke-width="1.6"/>'
    )
    parts.append(
        f'<rect x="10" y="10" width="{W - 20}" height="{H - 20:g}" fill="none" '
        f'stroke="#00F0FF" stroke-width="1" opacity="0.45" class="tcStream"/>'
    )
    for d in (
        "M10 44V10H44",
        f"M{W - 44} 10H{W - 10}V44",
        f"M{W - 10} {H - 44:g}V{H - 10:g}H{W - 44}",
        f"M44 {H - 10:g}H10V{H - 44:g}",
    ):
        parts.append(f'<path d="{d}" fill="none" stroke="#00FF41" stroke-width="3"/>')

    parts.append('<circle cx="46" cy="40" r="5" fill="#FF3B3B" class="tcBlink"/>')
    parts.append(
        '<text x="60" y="45" class="tcMono" font-size="14" letter-spacing="3" '
        'fill="url(#tcNeon)" font-weight="bold">TELEMETRY.CONSOLE — UNIFIED FEED</text>'
    )
    parts.append(
        f'<text x="{W - 30}" y="45" text-anchor="end" class="tcMono tcPulse" '
        f'font-size="12" letter-spacing="2" fill="#00FF41">SIGNAL: LIVE ⌁</text>'
    )

    parts.append(place(iso, content_x, y_iso, content_w, iso_hs))

    if stats_svg:
        parts.append(stats_svg)

    parts.append(
        f'<line x1="30" y1="{y_foot:g}" x2="{W - 30}" y2="{y_foot:g}" '
        f'stroke="url(#tcNeon)" stroke-width="0.8" opacity="0.5"/>'
    )
    parts.append(
        f'<text x="{W / 2:g}" y="{y_foot + 28:g}" text-anchor="middle" class="tcMono tcPulse" '
        f'font-size="12" letter-spacing="3" fill="#00FF41">'
        f"SKYLINE ONLINE · SIGNAL: NOMINAL · REFRESH: 24H</text>"
    )

    parts.append("</svg>")
    open(out_path, "w", encoding="utf-8").write("\n".join(parts))
    print(f"wrote {out_path} ({W}x{H:g})")


if __name__ == "__main__":
    main()
