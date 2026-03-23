import math
import re


def parse_style_map(style):
    result = {}
    for part in (style or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


def get_style_float(style, key):
    m = re.search(rf"{re.escape(key)}=([\d.]+)", style or "")
    if not m:
        return None
    return float(m.group(1))


def extract_port_spec(style, prefix):
    px = get_style_float(style, f"{prefix}X")
    py = get_style_float(style, f"{prefix}Y")
    if px is None or py is None:
        return None
    perimeter = get_style_float(style, f"{prefix}Perimeter")
    if perimeter is None:
        perimeter = 1.0
    return (px, py, perimeter)


def entity_center(node):
    return (node["x"] + node["w"] / 2, node["y"] + node["h"] / 2)


def seg_len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def path_segments(path):
    return [(path[i], path[i + 1]) for i in range(len(path) - 1)]


def direction_from_port(px, py):
    if py < 0.15:
        return "top"
    if py > 0.85:
        return "bottom"
    if px < 0.15:
        return "left"
    if px > 0.85:
        return "right"
    return "center"


def fallback_port(direction):
    table = {
        "right": (1.0, 0.5, 1.0),
        "left": (0.0, 0.5, 1.0),
        "top": (0.5, 0.0, 1.0),
        "bottom": (0.5, 1.0, 1.0),
    }
    return table.get(direction or "", (0.5, 0.5, 1.0))


def anchor_from_port(node, port_spec):
    px, py, _ = port_spec
    return (node["x"] + px * node["w"], node["y"] + py * node["h"])


def build_edge_path(src, tgt, waypoints=None, style="", fallback_exit_dir=None, fallback_entry_dir=None):
    exit_spec = extract_port_spec(style, "exit") or fallback_port(fallback_exit_dir)
    entry_spec = extract_port_spec(style, "entry") or fallback_port(fallback_entry_dir)
    exit_dir = direction_from_port(exit_spec[0], exit_spec[1])
    entry_dir = direction_from_port(entry_spec[0], entry_spec[1])
    sx, sy = anchor_from_port(src, exit_spec)
    tx, ty = anchor_from_port(tgt, entry_spec)

    if waypoints:
        return [(sx, sy)] + list(waypoints) + [(tx, ty)]

    is_h_exit = exit_dir in ("left", "right")
    is_h_entry = entry_dir in ("left", "right")
    if abs(sx - tx) < 1e-6 or abs(sy - ty) < 1e-6:
        return [(sx, sy), (tx, ty)]
    if is_h_exit and is_h_entry:
        mx = (sx + tx) / 2
        return [(sx, sy), (mx, sy), (mx, ty), (tx, ty)]
    if not is_h_exit and not is_h_entry:
        my = (sy + ty) / 2
        return [(sx, sy), (sx, my), (tx, my), (tx, ty)]
    if is_h_exit:
        return [(sx, sy), (tx, sy), (tx, ty)]
    return [(sx, sy), (sx, ty), (tx, ty)]
