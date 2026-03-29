#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
OBJ_PATH = ROOT / "th-d75-desk-holder-v2.obj"
OUT_DIR = ROOT / "images"


RADIO_W = 56.0
RADIO_H = 121.95
RADIO_D = 32.5
CLEAR = 1.2
POCKET_W = RADIO_W + 2 * CLEAR
POCKET_H = RADIO_H + 2 * CLEAR
BASE_MARGIN_X = 18.0
BASE_MARGIN_Y = 20.0
BASE_T = 6.0
WALL_H = 18.0
WALL_T = 6.0
BASE_W = POCKET_W + 2 * BASE_MARGIN_X
BASE_H = POCKET_H + 2 * BASE_MARGIN_Y
HOLDER_H = BASE_T + WALL_H


def load_obj(path: Path) -> tuple[np.ndarray, np.ndarray]:
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("v "):
            _, x, y, z = line.split()
            vertices.append([float(x), float(y), float(z)])
        elif line.startswith("f "):
            parts = line.split()[1:]
            idxs = [int(part.split("/")[0]) - 1 for part in parts]
            for i in range(1, len(idxs) - 1):
                faces.append([idxs[0], idxs[i], idxs[i + 1]])
    return np.array(vertices, dtype=float), np.array(faces, dtype=int)


def make_box(extents: tuple[float, float, float], center: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray]:
    ex, ey, ez = [d / 2 for d in extents]
    cx, cy, cz = center
    vertices = np.array(
        [
            [cx - ex, cy - ey, cz - ez],
            [cx + ex, cy - ey, cz - ez],
            [cx + ex, cy + ey, cz - ez],
            [cx - ex, cy + ey, cz - ez],
            [cx - ex, cy - ey, cz + ez],
            [cx + ex, cy - ey, cz + ez],
            [cx + ex, cy + ey, cz + ez],
            [cx - ex, cy + ey, cz + ez],
        ],
        dtype=float,
    )
    faces = np.array(
        [
            [0, 1, 2], [0, 2, 3],
            [4, 5, 6], [4, 6, 7],
            [0, 1, 5], [0, 5, 4],
            [1, 2, 6], [1, 6, 5],
            [2, 3, 7], [2, 7, 6],
            [3, 0, 4], [3, 4, 7],
        ],
        dtype=int,
    )
    return vertices, faces


def rotation_matrix(rx: float, ry: float, rz: float = 0.0) -> np.ndarray:
    rx, ry, rz = [math.radians(v) for v in (rx, ry, rz)]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


def shade_color(base_rgb: tuple[int, int, int], intensity: float) -> str:
    value = 0.45 + 0.55 * max(0.0, intensity)
    rgb = [max(0, min(255, int(channel * value))) for channel in base_rgb]
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def project_points(points: np.ndarray, width: int, height: int, scale: float, center: tuple[float, float]) -> np.ndarray:
    screen = np.empty((len(points), 2), dtype=float)
    screen[:, 0] = center[0] + points[:, 0] * scale
    screen[:, 1] = center[1] - points[:, 1] * scale
    return screen


def render_mesh_svg(
    vertices: np.ndarray,
    faces: np.ndarray,
    out_path: Path,
    *,
    title: str,
    subtitle: str,
    rx: float,
    ry: float,
    rz: float = 0.0,
    width: int = 1600,
    height: int = 1200,
    background_top: str = "#f8f5ef",
    background_bottom: str = "#ebe2d1",
    mesh_rgb: tuple[int, int, int] = (198, 160, 93),
    extra_meshes: list[dict] | None = None,
    callout: dict | None = None,
) -> None:
    rot = rotation_matrix(rx, ry, rz)
    light = np.array([0.35, 0.55, 0.76], dtype=float)
    light /= np.linalg.norm(light)

    rendered = []
    all_points = []

    def queue_mesh(verts: np.ndarray, mesh_faces: np.ndarray, rgb: tuple[int, int, int], opacity: float, stroke: str) -> None:
        transformed = verts @ rot.T
        all_points.append(transformed)
        for face in mesh_faces:
            tri = transformed[face]
            normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            length = np.linalg.norm(normal)
            if length == 0:
                continue
            normal /= length
            intensity = float(np.dot(normal, light))
            color = shade_color(rgb, intensity)
            depth = float(np.mean(tri[:, 2]))
            rendered.append(
                {
                    "points_3d": tri,
                    "fill": color,
                    "opacity": opacity,
                    "stroke": stroke,
                    "depth": depth,
                }
            )

    queue_mesh(vertices, faces, mesh_rgb, 1.0, "#705329")
    for mesh in extra_meshes or []:
        queue_mesh(mesh["vertices"], mesh["faces"], mesh["rgb"], mesh.get("opacity", 0.5), mesh.get("stroke", "#6d7484"))

    cloud = np.vstack(all_points)
    mins = cloud.min(axis=0)
    maxs = cloud.max(axis=0)
    span = max(maxs[0] - mins[0], maxs[1] - mins[1])
    scale = min(width * 0.58, height * 0.58) / span
    center = (width * 0.49, height * 0.62)

    polygons: list[str] = []
    for item in sorted(rendered, key=lambda it: it["depth"]):
        pts2d = project_points(item["points_3d"], width, height, scale, center)
        pts_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts2d)
        polygons.append(
            f'<polygon points="{pts_text}" fill="{item["fill"]}" fill-opacity="{item["opacity"]:.3f}" '
            f'stroke="{item["stroke"]}" stroke-opacity="0.45" stroke-width="1.2" />'
        )

    shadow_rx = (maxs[0] - mins[0]) * scale * 0.42
    shadow_ry = shadow_rx * 0.18
    shadow_cx = center[0] - 10
    shadow_cy = center[1] + (maxs[1] - mins[1]) * scale * 0.52

    callout_svg = ""
    if callout:
        target = np.array(callout["point"], dtype=float) @ rot.T
        anchor = project_points(target.reshape(1, 3), width, height, scale, center)[0]
        tx, ty = callout["text_xy"]
        lines = callout["lines"]
        line_gap = 40
        text_parts = [
            f'<text x="{tx}" y="{ty + i * line_gap}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="30" fill="#3c342c">{escape(line)}</text>'
            for i, line in enumerate(lines)
        ]
        callout_svg = (
            f'<line x1="{anchor[0]:.2f}" y1="{anchor[1]:.2f}" x2="{tx - 24}" y2="{ty - 10}" '
            f'stroke="#6b5841" stroke-width="3" />'
            f'<circle cx="{anchor[0]:.2f}" cy="{anchor[1]:.2f}" r="7" fill="#6b5841" />'
            + "".join(text_parts)
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{background_top}" />
      <stop offset="100%" stop-color="{background_bottom}" />
    </linearGradient>
    <filter id="blur">
      <feGaussianBlur stdDeviation="18" />
    </filter>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)" />
  <ellipse cx="{shadow_cx:.2f}" cy="{shadow_cy:.2f}" rx="{shadow_rx:.2f}" ry="{shadow_ry:.2f}" fill="#7d6646" fill-opacity="0.18" filter="url(#blur)" />
  <text x="100" y="120" font-family="Helvetica, Arial, sans-serif" font-size="68" fill="#201a14">{escape(title)}</text>
  <text x="100" y="175" font-family="Helvetica, Arial, sans-serif" font-size="32" fill="#5e5143">{escape(subtitle)}</text>
  {''.join(polygons)}
  {callout_svg}
</svg>
'''
    out_path.write_text(svg)


def mm_to_px(value: float, scale: float, offset: float) -> float:
    return offset + value * scale


def dimension_arrow(x1: float, y1: float, x2: float, y2: float, label: str, *, vertical: bool = False) -> str:
    if vertical:
        tx = x1 + 18
        ty = (y1 + y2) / 2 + 10
        rotate = f' transform="rotate(-90 {tx} {ty})"'
    else:
        tx = (x1 + x2) / 2
        ty = y1 - 16
        rotate = ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#6c635d" stroke-width="3" marker-start="url(#arrow)" marker-end="url(#arrow)" />'
        f'<text x="{tx}" y="{ty}" font-family="Helvetica, Arial, sans-serif" font-size="28" fill="#433a34" text-anchor="middle"{rotate}>{escape(label)}</text>'
    )


def render_dimensions_svg(out_path: Path) -> None:
    width = 1600
    height = 1200
    scale = 5.4

    top_left_x = 130
    top_left_y = 285
    base_x1 = mm_to_px(0, scale, top_left_x)
    base_y1 = mm_to_px(0, scale, top_left_y)
    base_x2 = mm_to_px(BASE_W, scale, top_left_x)
    base_y2 = mm_to_px(BASE_H, scale, top_left_y)

    pocket_x1 = mm_to_px((BASE_W - POCKET_W) / 2, scale, top_left_x)
    pocket_y1 = mm_to_px((BASE_H - POCKET_H) / 2, scale, top_left_y)
    pocket_x2 = mm_to_px((BASE_W + POCKET_W) / 2, scale, top_left_x)
    pocket_y2 = mm_to_px((BASE_H + POCKET_H) / 2, scale, top_left_y)

    profile_origin_x = 970
    profile_origin_y = 350
    profile_scale = 15
    profile_w = BASE_W * 0.23 * profile_scale / 10
    profile_h = HOLDER_H * profile_scale / 10
    base_thickness = BASE_T * profile_scale / 10
    wall_thickness = WALL_T * profile_scale / 10

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1200" viewBox="0 0 1600 1200">',
        "<defs>",
        '  <linearGradient id="paper" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#fffdfa" />',
        '    <stop offset="100%" stop-color="#f3ede3" />',
        "  </linearGradient>",
        '  <marker id="arrow" markerWidth="10" markerHeight="10" refX="5" refY="5" orient="auto">',
        '    <path d="M0,0 L10,5 L0,10 z" fill="#6c635d" />',
        "  </marker>",
        "</defs>",
        '<rect width="100%" height="100%" fill="url(#paper)" />',
        '<text x="110" y="120" font-family="Helvetica, Arial, sans-serif" font-size="68" fill="#201a14">Holder Dimensions</text>',
        '<text x="110" y="175" font-family="Helvetica, Arial, sans-serif" font-size="32" fill="#5e5143">Based on the exported model and the generator constants in generate_holder.py</text>',
        f'<rect x="{base_x1:.2f}" y="{base_y1:.2f}" width="{(base_x2 - base_x1):.2f}" height="{(base_y2 - base_y1):.2f}" rx="18" fill="#e6d7b3" stroke="#6f5d38" stroke-width="4" />',
        f'<rect x="{pocket_x1:.2f}" y="{pocket_y1:.2f}" width="{(pocket_x2 - pocket_x1):.2f}" height="{(pocket_y2 - pocket_y1):.2f}" fill="none" stroke="#8f7b55" stroke-width="3" stroke-dasharray="12 10" />',
        f'<line x1="{base_x1 - 38:.2f}" y1="{base_y1:.2f}" x2="{base_x1 - 38:.2f}" y2="{base_y2:.2f}" stroke="#8d847d" stroke-width="2" />',
        f'<line x1="{base_x2 + 38:.2f}" y1="{base_y1:.2f}" x2="{base_x2 + 38:.2f}" y2="{base_y2:.2f}" stroke="#8d847d" stroke-width="2" />',
        f'<line x1="{base_x1:.2f}" y1="{base_y2 + 48:.2f}" x2="{base_x2:.2f}" y2="{base_y2 + 48:.2f}" stroke="#8d847d" stroke-width="2" />',
        f'<line x1="{base_x1:.2f}" y1="{base_y1 - 48:.2f}" x2="{base_x2:.2f}" y2="{base_y1 - 48:.2f}" stroke="#8d847d" stroke-width="2" />',
        dimension_arrow(base_x1, base_y1 - 48, base_x2, base_y1 - 48, f"{BASE_W:.1f} mm"),
        dimension_arrow(base_x2 + 38, base_y1, base_x2 + 38, base_y2, f"{BASE_H:.1f} mm", vertical=True),
        f'<text x="{pocket_x1:.2f}" y="{pocket_y1 - 18:.2f}" font-family="Helvetica, Arial, sans-serif" font-size="28" fill="#433a34">Pocket: {POCKET_W:.1f} x {POCKET_H:.2f} mm</text>',
        f'<text x="{top_left_x:.2f}" y="{base_y2 + 110:.2f}" font-family="Helvetica, Arial, sans-serif" font-size="28" fill="#433a34">Radio body used: {RADIO_W:.1f} x {RADIO_H:.2f} x {RADIO_D:.1f} mm</text>',
        f'<text x="{top_left_x:.2f}" y="{base_y2 + 150:.2f}" font-family="Helvetica, Arial, sans-serif" font-size="28" fill="#433a34">Clearance: about {CLEAR:.1f} mm per side</text>',
        f'<path d="M {profile_origin_x},{profile_origin_y + profile_h} L {profile_origin_x},{profile_origin_y} L {profile_origin_x + wall_thickness},{profile_origin_y} L {profile_origin_x + wall_thickness},{profile_origin_y + base_thickness} L {profile_origin_x + profile_w - wall_thickness},{profile_origin_y + base_thickness} L {profile_origin_x + profile_w - wall_thickness},{profile_origin_y} L {profile_origin_x + profile_w},{profile_origin_y} L {profile_origin_x + profile_w},{profile_origin_y + profile_h} Z" fill="#d9c191" stroke="#6f5d38" stroke-width="4" />',
        f'<rect x="{profile_origin_x + wall_thickness:.2f}" y="{profile_origin_y + base_thickness:.2f}" width="{profile_w - 2 * wall_thickness:.2f}" height="{profile_h - base_thickness:.2f}" fill="#fffdfa" opacity="0.75" />',
        f'<line x1="{profile_origin_x - 30:.2f}" y1="{profile_origin_y:.2f}" x2="{profile_origin_x - 30:.2f}" y2="{profile_origin_y + profile_h:.2f}" stroke="#8d847d" stroke-width="2" />',
        f'<line x1="{profile_origin_x:.2f}" y1="{profile_origin_y + profile_h + 40:.2f}" x2="{profile_origin_x + profile_w:.2f}" y2="{profile_origin_y + profile_h + 40:.2f}" stroke="#8d847d" stroke-width="2" />',
        dimension_arrow(profile_origin_x, profile_origin_y + profile_h + 40, profile_origin_x + profile_w, profile_origin_y + profile_h + 40, "profile view"),
        dimension_arrow(profile_origin_x - 30, profile_origin_y, profile_origin_x - 30, profile_origin_y + profile_h, f"{HOLDER_H:.1f} mm", vertical=True),
        f'<text x="{profile_origin_x:.2f}" y="{profile_origin_y - 30:.2f}" font-family="Helvetica, Arial, sans-serif" font-size="34" fill="#201a14">Side Profile</text>',
        f'<text x="{profile_origin_x:.2f}" y="{profile_origin_y + profile_h + 110:.2f}" font-family="Helvetica, Arial, sans-serif" font-size="28" fill="#433a34">Base thickness: {BASE_T:.1f} mm   Wall height above base: {WALL_H:.1f} mm</text>',
        "</svg>",
    ]
    out_path.write_text("\n".join(lines))


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    vertices, faces = load_obj(OBJ_PATH)

    render_mesh_svg(
        vertices,
        faces,
        OUT_DIR / "holder-isometric.svg",
        title="Kenwood TH-D75 Desk Holder",
        subtitle="Exact render from the exported OBJ mesh",
        rx=62,
        ry=-28,
    )

    render_mesh_svg(
        vertices,
        faces,
        OUT_DIR / "holder-right-access.svg",
        title="Right-Side Cable Access",
        subtitle="The side posts leave the connector side mostly open",
        rx=64,
        ry=34,
        callout={
            "point": (POCKET_W / 2 + WALL_T, POCKET_H / 2 - 11, BASE_T + 10),
            "text_xy": (1120, 360),
            "lines": ["Open right-side access", "for charging and data cables"],
        },
    )

    radio_vertices, radio_faces = make_box(
        (RADIO_W, RADIO_H, RADIO_D),
        (0.0, 0.0, BASE_T + RADIO_D / 2),
    )
    render_mesh_svg(
        vertices,
        faces,
        OUT_DIR / "holder-with-radio-envelope.svg",
        title="Radio Envelope Reference",
        subtitle="Translucent block shows the published radio body dimensions used for fit",
        rx=62,
        ry=-28,
        extra_meshes=[
            {
                "vertices": radio_vertices,
                "faces": radio_faces,
                "rgb": (93, 135, 198),
                "opacity": 0.32,
                "stroke": "#4f6a95",
            }
        ],
    )

    render_dimensions_svg(OUT_DIR / "holder-dimensions.svg")


if __name__ == "__main__":
    main()
