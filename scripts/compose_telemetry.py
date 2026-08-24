#!/usr/bin/env python3
"""Compose the 3D contribution graph and the contribution snake into ONE
component (assets/telemetry-unit.svg): the snake is re-projected onto the
isometric floor of the 3D graph, so it crawls between the towers.

Usage: compose_telemetry.py <3d.svg> <snake.svg> <out.svg>

How it works: both generators share the same 53x7 week/day grid. The snake
SVG's body is 4 rects animated by CSS translate keyframes in 16px steps;
the 3D floor tile for (col,row) sits at ORIGIN + col*WEEK + row*DAY. A
single linear map converts 16px snake-space into the isometric basis, and
the snake's keyframe translations compose through it, so the crawl itself
becomes isometric. The flat grid, progress bar, and cell-fade animations
from the snake SVG are dropped; only the snake body (recolored to match
the HUD palette) is injected into the 3D document.
"""

import re
import sys

# 3D floor geometry (from github-profile-3d-contrib output, 1280x850 canvas)
ORIGIN = (140.0, 154.18)     # tile (col=0,row=0) north corner
WEEK = (20.0, 11.545)        # +1 column (week)
DAY = (-20.0, 11.545)        # +1 row (day)
PITCH = 16.0                 # snake grid pixel pitch

SNAKE_COLOR = "#00F0FF"


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


def snake_overlay(snake_svg: str) -> str:
    style = re.search(r"<style>(.*?)</style>", snake_svg, re.S).group(1)
    style = style.replace("--cs:purple", f"--cs:{SNAKE_COLOR}")
    segments = re.findall(r'<rect class="s s[^>]*/>', snake_svg)
    if not segments:
        raise SystemExit("no snake body rects found in snake svg")
    a = WEEK[0] / PITCH
    b = WEEK[1] / PITCH
    c = DAY[0] / PITCH
    d = DAY[1] / PITCH
    iso = f"matrix({a:g},{b:g},{c:g},{d:g},{ORIGIN[0]:g},{ORIGIN[1]:g})"
    return f'<style>{style}</style><g transform="{iso}">{"".join(segments)}</g>'


def main() -> None:
    iso_path, snake_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    iso, iso_w, iso_h = load(iso_path)
    snk, _, _ = load(snake_path)

    iso = iso.replace("</svg>", snake_overlay(snk) + "</svg>", 1)

    W = 900
    content_x, content_w = 25, 850
    iso_hs = content_w * iso_h / iso_w

    title_h, foot_h = 58, 46
    y_iso = title_h + 6
    y_foot = y_iso + iso_hs + 8
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

    parts.append(
        f'<line x1="30" y1="{y_foot:g}" x2="{W - 30}" y2="{y_foot:g}" '
        f'stroke="url(#tcNeon)" stroke-width="0.8" opacity="0.5"/>'
    )
    parts.append(
        f'<text x="{W / 2:g}" y="{y_foot + 28:g}" text-anchor="middle" class="tcMono tcPulse" '
        f'font-size="12" letter-spacing="3" fill="#00FF41">'
        f"ORGANISM ACTIVE ON GRID · SIGNAL: NOMINAL · REFRESH: 24H</text>"
    )

    parts.append("</svg>")
    open(out_path, "w", encoding="utf-8").write("\n".join(parts))
    print(f"wrote {out_path} ({W}x{H:g})")


if __name__ == "__main__":
    main()
