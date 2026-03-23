import argparse
import json
import math
import os
from collections import defaultdict
from copy import deepcopy
from xml.etree import ElementTree as ET

from geometry import build_edge_path

# ───────────────────────── constants ──────────────────────────────────────────
STAGES = ["信息收集", "存储/使用", "分享/传输", "归档/删除"]
STAGE_INDEX = {name: i for i, name in enumerate(STAGES)}
LANES  = ["data_subject", "internal_staff", "internal_system", "third_party"]
LANE_LABELS = {
    "data_subject":   "数据主体",
    "internal_staff": "内部人员",
    "internal_system":"内部系统",
    "third_party":    "第三方",
}
DEFAULT_STORE_SUBCOLUMNS = ["用户界面", "业务系统"]

TYPE_STYLES = {
    "human_actor":       "rounded=1;whiteSpace=wrap;html=1;",
    "ui_function":       "whiteSpace=wrap;html=1;",
    "internal_system":   "rounded=1;whiteSpace=wrap;html=1;",
    "datastore":         "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;",
    "third_party_cloud": "shape=cloud;whiteSpace=wrap;html=1;",
    "data_item_dot":     "ellipse;whiteSpace=wrap;html=1;aspect=fixed;",
}
TYPE_SIZES = {
    "human_actor":       (120, 60),
    "ui_function":       (130, 48),
    "internal_system":   (140, 60),
    "datastore":         (120, 72),
    "third_party_cloud": (130, 60),
    "data_item_dot":     (24, 24),
}

USER_ACTOR_STYLE = (
    "shape=umlActor;whiteSpace=wrap;html=1;"
    "verticalLabelPosition=bottom;verticalAlign=top;"
)
USER_ACTOR_SIZE = (42, 84)

DEFAULT_ACTIVITY_COLOR = "#5b6e84"

DATA_DOT_COLORS = [
    "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71",
    "#1abc9c", "#3498db", "#9b59b6", "#e91e63",
    "#00bcd4", "#ff5722",
]

DOT_SIZE    = 24
DOT_SPACING = 30
DOT_CLUSTER_GAP = 20
DOT_PATH_MARGIN = 18
DOT_MIN_SIZE = 18
DOT_SHORT_PATH_THRESHOLD = 90
DOT_AVOIDANCE_STEP = 24
ROUTE_BOX_PAD = 10
DOT_ENTITY_PAD = 10
DOT_OUTER_SEG_PENALTY = 1200
DOT_TIGHT_ROUTE_WEIGHT = 120

SLOT_H = 104          # vertical pitch per entity slot
SLOT_PAD_TOP = 20     # top margin within a lane
SLOT_PAD_BOT = 50     # bottom margin (routing channel space)


# ───────────────────────── I/O ────────────────────────────────────────────────
def load_input(path):
    _, ext = os.path.splitext(path.lower())
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if ext == ".json":
        return json.loads(raw)
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit("pip install pyyaml, or provide a JSON file.") from exc
    return yaml.safe_load(raw)


def esc(v):
    if v is None:
        return ""
    return (str(v)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class IdGen:
    def __init__(self):
        self._n = 2
    def next(self):
        v = str(self._n); self._n += 1; return v


class Builder:
    def __init__(self):
        self.root = ET.Element(
            "mxfile",
            host="Codex",
            agent="Codex",
            version="29.6.1",
        )
        diagram = ET.SubElement(self.root, "diagram", id="codex-page-1", name="第 1 页")
        model = ET.SubElement(
            diagram,
            "mxGraphModel",
            dx="1200",
            dy="900",
            grid="1",
            gridSize="10",
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth="827",
            pageHeight="1169",
            math="0",
            shadow="0",
            adaptiveColors="auto",
        )
        r = ET.SubElement(model, "root")
        ET.SubElement(r, "mxCell", id="0")
        ET.SubElement(r, "mxCell", id="1", parent="0")
        self._r   = r
        self._ids = IdGen()

    def _meta_attrs(self, metadata):
        attrs = {}
        for key, value in (metadata or {}).items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                attrs[key] = ",".join(str(v) for v in value)
            elif isinstance(value, bool):
                attrs[key] = "true" if value else "false"
            else:
                attrs[key] = str(value)
        return attrs

    def vertex(self, value, style, x, y, w, h, parent="1", metadata=None):
        attrs = {
            "id": self._ids.next(),
            "value": esc(value),
            "style": style,
            "vertex": "1",
            "parent": parent,
        }
        attrs.update(self._meta_attrs(metadata))
        cell = ET.SubElement(
            self._r, "mxCell",
            **attrs,
        )
        ET.SubElement(cell, "mxGeometry",
                      x=str(round(x)), y=str(round(y)),
                      width=str(round(w)), height=str(round(h)),
                      **{"as": "geometry"})
        return cell.attrib["id"]

    def edge(self, src, tgt, style, value="", parent="1", points=None, metadata=None):
        attrs = {
            "id": self._ids.next(),
            "value": esc(value),
            "style": style,
            "edge": "1",
            "source": src,
            "target": tgt,
            "parent": parent,
        }
        attrs.update(self._meta_attrs(metadata))
        cell = ET.SubElement(
            self._r, "mxCell",
            **attrs,
        )
        geo = ET.SubElement(cell, "mxGeometry", relative="1",
                            **{"as": "geometry"})
        if points:
            arr = ET.SubElement(geo, "Array", **{"as": "points"})
            for px, py in points:
                ET.SubElement(arr, "mxPoint",
                              x=str(round(px)), y=str(round(py)))
        return cell.attrib["id"]

    def tostring(self):
        return ET.tostring(self.root, encoding="unicode")


# ───────────────────────── layout ─────────────────────────────────────────────
def populated_subcolumns(data, preferred):
    used = set()
    for lb in (data.get("lanes") or {}).values():
        for e in lb.get("entities") or []:
            sc = (e.get("subcolumn") or "").strip()
            if sc:
                used.add(sc)
    result = [sc for sc in preferred if sc in used]
    return result if result else preferred[:2]


def build_layout(data):
    preferred = (
        ((data.get("layout") or {}).get("store_use_subcolumns")
         or DEFAULT_STORE_SUBCOLUMNS)[:]
    )
    subcols = populated_subcolumns(data, preferred)

    # ── Pre-scan entities to compute dynamic lane heights & stage widths ──
    slot_counts = defaultdict(int)       # (lane, stage, subcolumn) -> count
    max_ent_w   = defaultdict(float)     # (stage, subcolumn) -> max width

    for lk in LANES:
        block = (data.get("lanes") or {}).get(lk) or {}
        for e in block.get("entities") or []:
            etype = e.get("type", "internal_system")
            stage = e.get("stage") or dflt_stage(lk, etype)
            sc = (e.get("subcolumn") or "").strip() or "_"
            ne = {"type": etype, "lane_key": lk}
            _, (w, _) = resolve_visual(ne)
            slot_counts[(lk, stage, sc)] += 1
            max_ent_w[(stage, sc)] = max(max_ent_w.get((stage, sc), 0), w)

    # Dynamic lane heights: pad + max_slots_in_any_column × SLOT_H
    MIN_LANE_H = {
        "data_subject": 120, "internal_staff": 60,
        "internal_system": 200, "third_party": 120,
    }
    lane_h = {}
    for lk in LANES:
        max_slots = 0
        for (l, st, sc), count in slot_counts.items():
            if l == lk:
                max_slots = max(max_slots, count)
        computed = SLOT_PAD_TOP + max_slots * SLOT_H + SLOT_PAD_BOT
        lane_h[lk] = max(MIN_LANE_H.get(lk, 100), computed)

    # Dynamic stage widths
    MIN_STAGE_W = {
        "信息收集": 150, "存储/使用": 300,
        "分享/传输": 180, "归档/删除": 130,
    }
    stage_w = {}
    for s in STAGES:
        if s == "存储/使用" and subcols:
            sc_widths = []
            for sc in subcols:
                ew = max_ent_w.get((s, sc), 120)
                sc_widths.append(ew + 60)
            total = sum(sc_widths) + 10 * (len(sc_widths) + 1)
            stage_w[s] = max(MIN_STAGE_W[s], round(total))
        else:
            max_w = 0
            for (st, sc), w in max_ent_w.items():
                if st == s:
                    max_w = max(max_w, w)
            computed = max_w + 60 if max_w > 0 else 0
            stage_w[s] = max(MIN_STAGE_W.get(s, 130), round(computed))

    # Expand stage widths to accommodate layout_hints that push entities
    # beyond computed boundaries.
    tmp_cx = 105
    tmp_stage_x = {}
    for s in STAGES:
        tmp_stage_x[s] = tmp_cx
        tmp_cx += stage_w[s] + 10

    for lk in LANES:
        block = (data.get("lanes") or {}).get(lk) or {}
        for e in block.get("entities") or []:
            hint = e.get("layout_hint") or {}
            if "x" in hint:
                etype = e.get("type", "internal_system")
                stage = e.get("stage") or dflt_stage(lk, etype)
                ne = {"type": etype, "lane_key": lk}
                _, (w, _) = resolve_visual(ne)
                right_needed = float(hint["x"]) + w + 20
                sx = tmp_stage_x[stage]
                required_w = right_needed - sx
                if required_w > stage_w[stage]:
                    stage_w[stage] = round(required_w)

    L = {
        "title_x": 20, "title_y": 20, "title_w": 640, "title_h": 30,
        "ll_x": 15,    "ll_w": 80,
        "main_x": 105, "main_y": 65,
        "lane_gap": 16, "hdr_h": 28, "sub_h": 26,
        "lane_h": lane_h,
        "stage_w": stage_w,
        "subcols": subcols,
    }

    cx = L["main_x"]
    stage_b = {}
    for s in STAGES:
        w = stage_w[s]
        stage_b[s] = {"x": cx, "y": L["main_y"], "w": w}
        cx += w + 10
    L["stage_b"] = stage_b

    cy       = L["main_y"] + L["hdr_h"] + 12
    lane_b   = {}
    total_w  = cx - L["ll_x"] - 10
    for lk in LANES:
        h = lane_h[lk]
        lane_b[lk] = {"x": L["ll_x"], "y": cy, "w": total_w, "h": h}
        cy += h + L["lane_gap"]
    L["lane_b"] = lane_b

    sb  = stage_b["存储/使用"]
    n   = len(subcols)
    scw = (sb["w"] - 10 * (n + 1)) / max(1, n)
    sc_b = {}
    for i, sc in enumerate(subcols):
        sc_b[sc] = {"x": sb["x"] + 10 + i * (scw + 10), "w": scw}
    L["sc_b"] = sc_b

    il           = lane_b["internal_system"]
    L["bch_y"]   = il["y"] + il["h"] - 28
    L["lg_x"]    = L["ll_x"] + L["ll_w"] - 5
    L["rg_x"]    = cx + 12
    L["il_top"]  = il["y"]
    L["il_bot"]  = il["y"] + il["h"]

    L["legend_x"] = cx + 50
    L["legend_y"] = 70
    L["legend_w"] = 370
    return L


# ───────────────────────── entity normalisation & placement ───────────────────
def dflt_stage(lk, etype):
    if lk == "data_subject": return "信息收集"
    if lk == "third_party":  return "分享/传输"
    return "存储/使用"


def resolve_visual(entity):
    etype = entity.get("type", "internal_system")
    lk    = entity.get("lane_key", "")
    if etype == "human_actor" and lk == "data_subject":
        return USER_ACTOR_STYLE, USER_ACTOR_SIZE
    return (TYPE_STYLES.get(etype, TYPE_STYLES["internal_system"]),
            TYPE_SIZES.get(etype, (120, 60)))


def normalize_entities(data):
    entities, by_id = [], {}
    for lk in LANES:
        block = (data.get("lanes") or {}).get(lk) or {}
        for e in block.get("entities") or []:
            ne = deepcopy(e)
            ne["lane_key"] = lk
            ne.setdefault("type",      "internal_system")
            ne.setdefault("stage",     dflt_stage(lk, ne["type"]))
            ne.setdefault("subcolumn", "")
            entities.append(ne)
            by_id[ne["id"]] = ne
    return entities, by_id


def resolve_polish_mode(data, cli_mode=None):
    if cli_mode and cli_mode != "auto":
        return cli_mode
    polish = data.get("polish") or {}
    return (polish.get("mode") or "layout_locked").strip() or "layout_locked"


def entity_semantic_role(entity):
    return ((entity or {}).get("semantic_role") or "").strip()


def build_flow_context(flow, src, tgt):
    intent = deepcopy(flow.get("routing_intent") or {})
    flow_role = ((flow or {}).get("flow_role") or "").strip()
    src_entity = src.get("entity") or {}
    tgt_entity = tgt.get("entity") or {}
    src_stage = src_entity.get("stage", "")
    tgt_stage = tgt_entity.get("stage", "")
    target_role = entity_semantic_role(tgt_entity)
    source_role = entity_semantic_role(src_entity)
    n_dots = len(flow.get("data_item_ids") or [])

    inferred_return_to_ui = (
        tgt_entity.get("type") == "ui_function" and
        src_entity.get("lane_key") == "internal_system" and
        STAGE_INDEX.get(src_stage, 0) >= STAGE_INDEX.get(tgt_stage, 0)
    )
    inferred_reporting_sink = (
        target_role in ("analysis_sink", "reporting_sink") and
        n_dots > 1
    )

    return {
        "flow_id": flow.get("id", ""),
        "flow_role": flow_role,
        "routing_intent": intent,
        "n_dots": n_dots,
        "source_role": source_role,
        "target_role": target_role,
        "prefer_return_to_ui": (
            flow_role == "return_to_ui" or
            intent.get("prefer_return_to_ui") is True or
            inferred_return_to_ui
        ),
        "prefer_reporting_sink": (
            flow_role in ("reporting", "analysis_report") or
            intent.get("prefer_runway") is True or
            inferred_reporting_sink
        ),
    }


def flow_metadata(flow, src, tgt, flow_ctx):
    return {
        "codexKind": "flow_edge",
        "codexFlowId": flow.get("id", ""),
        "codexFlowRole": flow_ctx.get("flow_role", ""),
        "codexSourceEntityId": flow.get("source_entity_id", ""),
        "codexTargetEntityId": flow.get("target_entity_id", ""),
        "codexDataItemIds": flow.get("data_item_ids") or [],
        "codexTargetRole": flow_ctx.get("target_role", ""),
        "codexRoutingIntent": json.dumps(flow_ctx.get("routing_intent") or {}, ensure_ascii=False, sort_keys=True),
    }


def place_entities(data, entities, L):
    placed = {}
    ctr    = defaultdict(int)
    for e in entities:
        lk    = e["lane_key"]
        lane  = L["lane_b"][lk]
        stage = e.get("stage") or dflt_stage(lk, e["type"])
        stb   = L["stage_b"].get(stage, L["stage_b"]["存储/使用"])
        sc    = e.get("subcolumn") or ""
        _, (w, h) = resolve_visual(e)

        hint = e.get("layout_hint") or {}
        has_manual_xy = ("x" in hint and "y" in hint)

        if has_manual_xy:
            # Explicit per-entity anchor for manual visual tuning.
            x = float(hint.get("x", 0))
            y = float(hint.get("y", 0))
        else:
            if stage == "存储/使用" and sc and sc in L["sc_b"]:
                scb = L["sc_b"][sc]
                x   = scb["x"] + max(0, (scb["w"] - w) / 2)
            else:
                x = stb["x"] + max(10, (stb["w"] - w) / 2)

            gk   = (lk, stage, sc or "_")
            slot = ctr[gk]; ctr[gk] += 1
            y = lane["y"] + SLOT_PAD_TOP + slot * SLOT_H

        sty, _ = resolve_visual(e)
        placed[e["id"]] = {
            "x": x, "y": y, "w": w, "h": h,
            "style": sty, "entity": e,
        }
    return placed


# ───────────────────────── shape-aware ports ──────────────────────────────────

def _entity_shape(node):
    e = node.get("entity") or {}
    etype = e.get("type", "")
    lk    = e.get("lane_key", "")
    if etype == "human_actor" and lk == "data_subject":
        return "umlActor"
    if etype == "third_party_cloud":
        return "cloud"
    if etype == "datastore":
        return "cylinder"
    return "rect"

_ACTOR_PORTS = {
    "right": (1.0,  0.33, 0),
    "left":  (0.0,  0.33, 0),
    "top":   (0.5,  0.0,  0),
    "bottom":(0.5,  1.0,  1),
}
_CLOUD_PORTS = {
    "right": (0.875, 0.5, 0),
    "left":  (0.08, 0.53, 0),
    "top":   (0.5,  0.15, 0),
    "bottom":(0.5,  0.85, 0),
}
_RECT_PORTS = {
    "right": (1.0, 0.5, 1),
    "left":  (0.0, 0.5, 1),
    "top":   (0.5, 0.0, 1),
    "bottom":(0.5, 1.0, 1),
}
_CYLINDER_PORTS = {
    "right": (1.0, 0.5, 1),
    "left":  (0.0, 0.5, 1),
    "top":   (0.5, 0.0, 1),
    "bottom":(0.5, 1.0, 1),
}

_SHAPE_PORT_MAP = {
    "umlActor": _ACTOR_PORTS,
    "cloud":    _CLOUD_PORTS,
    "cylinder": _CYLINDER_PORTS,
    "rect":     _RECT_PORTS,
}


def _get_port(node, direction):
    shape = _entity_shape(node)
    table = _SHAPE_PORT_MAP.get(shape, _RECT_PORTS)
    return table.get(direction, _RECT_PORTS[direction])


def _anchor_xy(node, direction):
    px, py, _ = _get_port(node, direction)
    return node["x"] + px * node["w"], node["y"] + py * node["h"]


def _pt(x, y):
    return (float(x), float(y))


def _segments(path):
    return [
        (path[i], path[i + 1])
        for i in range(len(path) - 1)
        if _seg_len(path[i], path[i + 1]) > 0.5
    ]


def _path_len(path):
    return sum(_seg_len(a, b) for a, b in _segments(path))


def _longest_segment_len(path):
    segs = _segments(path)
    return max((_seg_len(a, b) for a, b in segs), default=0)


def _inner_longest_segment_len(path):
    segs = _segments(path)
    if len(segs) <= 2:
        return 0
    return max((_seg_len(a, b) for a, b in segs[1:-1]), default=0)


def _entity_box(node, pad=0):
    return (
        node["x"] - pad,
        node["y"] - pad,
        node["x"] + node["w"] + pad,
        node["y"] + node["h"] + pad,
    )


def _rect_intersects_rect(a, b, pad=0):
    return not (
        a[2] <= b[0] - pad or
        a[0] >= b[2] + pad or
        a[3] <= b[1] - pad or
        a[1] >= b[3] + pad
    )


def _segment_intersects_box(a, b, box):
    x1, y1 = a
    x2, y2 = b
    bx1, by1, bx2, by2 = box

    if abs(y1 - y2) < 1e-6:
        y = y1
        if y < by1 or y > by2:
            return False
        left, right = sorted((x1, x2))
        return not (right <= bx1 or left >= bx2)

    if abs(x1 - x2) < 1e-6:
        x = x1
        if x < bx1 or x > bx2:
            return False
        top, bottom = sorted((y1, y2))
        return not (bottom <= by1 or top >= by2)

    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    return not (right <= bx1 or left >= bx2 or bottom <= by1 or top >= by2)


def _segment_overlap_count(seg, other):
    (ax1, ay1), (ax2, ay2) = seg
    (bx1, by1), (bx2, by2) = other

    a_h = abs(ay1 - ay2) < 1e-6
    b_h = abs(by1 - by2) < 1e-6
    a_v = abs(ax1 - ax2) < 1e-6
    b_v = abs(bx1 - bx2) < 1e-6

    if a_h and b_h and abs(ay1 - by1) < 1e-6:
        a0, a1 = sorted((ax1, ax2))
        b0, b1 = sorted((bx1, bx2))
        return 1 if min(a1, b1) - max(a0, b0) > 4 else 0
    if a_v and b_v and abs(ax1 - bx1) < 1e-6:
        a0, a1 = sorted((ay1, ay2))
        b0, b1 = sorted((by1, by2))
        return 1 if min(a1, b1) - max(a0, b0) > 4 else 0
    return 0


def _path_collision_count(path, placed, ignore_ids=()):
    if not placed:
        return 0
    ignore_ids = set(ignore_ids or [])
    hits = 0
    for eid, node in placed.items():
        if eid in ignore_ids:
            continue
        box = _entity_box(node, ROUTE_BOX_PAD)
        if any(_segment_intersects_box(a, b, box) for a, b in _segments(path)):
            hits += 1
    return hits


def _path_overlap_count(path, other_paths):
    overlaps = 0
    my_segments = _segments(path)
    for other_path in other_paths or []:
        for seg in my_segments:
            for other_seg in _segments(other_path):
                overlaps += _segment_overlap_count(seg, other_seg)
    return overlaps


def _segments_parallel_distance(seg_a, seg_b):
    (ax1, ay1), (ax2, ay2) = seg_a
    (bx1, by1), (bx2, by2) = seg_b

    a_h = abs(ay1 - ay2) < 1e-6
    b_h = abs(by1 - by2) < 1e-6
    a_v = abs(ax1 - ax2) < 1e-6
    b_v = abs(bx1 - bx2) < 1e-6

    if a_h and b_h:
        a0, a1 = sorted((ax1, ax2))
        b0, b1 = sorted((bx1, bx2))
        overlap = min(a1, b1) - max(a0, b0)
        if overlap > 5:
            return abs(ay1 - by1)
    if a_v and b_v:
        a0, a1 = sorted((ay1, ay2))
        b0, b1 = sorted((by1, by2))
        overlap = min(a1, b1) - max(a0, b0)
        if overlap > 5:
            return abs(ax1 - bx1)
    return None


def _path_parallel_proximity_penalty(path, other_paths, min_gap=2 * DOT_SIZE):
    penalty = 0
    my_segments = _segments(path)
    for other_path in other_paths or []:
        other_segments = _segments(other_path)
        for seg in my_segments:
            for other_seg in other_segments:
                dist = _segments_parallel_distance(seg, other_seg)
                if dist is not None and 0.5 < dist < min_gap:
                    penalty += int((min_gap - dist) * 60)
    return penalty


def _path_respects_ports(path, exit_dir, entry_dir):
    segs = _segments(path)
    if not segs:
        return True

    (sx, sy), (fx, fy) = segs[0]
    if exit_dir == "right" and not (abs(fy - sy) < 1e-6 and fx >= sx):
        return False
    if exit_dir == "left" and not (abs(fy - sy) < 1e-6 and fx <= sx):
        return False
    if exit_dir == "bottom" and not (abs(fx - sx) < 1e-6 and fy >= sy):
        return False
    if exit_dir == "top" and not (abs(fx - sx) < 1e-6 and fy <= sy):
        return False

    (px, py), (tx, ty) = segs[-1]
    if entry_dir == "left" and not (abs(py - ty) < 1e-6 and px <= tx):
        return False
    if entry_dir == "right" and not (abs(py - ty) < 1e-6 and px >= tx):
        return False
    if entry_dir == "top" and not (abs(px - tx) < 1e-6 and py <= ty):
        return False
    if entry_dir == "bottom" and not (abs(px - tx) < 1e-6 and py >= ty):
        return False
    return True


def _route_bounds(src, tgt, L):
    slb = L["lane_b"][src["entity"]["lane_key"]]
    tlb = L["lane_b"][tgt["entity"]["lane_key"]]
    top = min(slb["y"], tlb["y"]) + 8
    bottom = max(slb["y"] + slb["h"], tlb["y"] + tlb["h"]) - 8
    left = L["lg_x"] + 6
    right = max(
        L["rg_x"] - 6,
        src["x"] + src["w"] + 24,
        tgt["x"] + tgt["w"] + 24,
    )
    return left, top, right, bottom


def _primary_waypoints(src, tgt, L, fi, exit_dir, entry_dir, dup_index=0, n_dots=0):
    sx, sy = _anchor_xy(src, exit_dir)
    tx, ty = _anchor_xy(tgt, entry_dir)
    _, top, _, bottom = _route_bounds(src, tgt, L)

    slk = src["entity"]["lane_key"]
    tlk = tgt["entity"]["lane_key"]
    off = dup_index * 20

    is_h_exit = exit_dir in ("left", "right")
    is_h_entry = entry_dir in ("left", "right")
    is_perp = is_h_exit != is_h_entry

    if slk != tlk:
        if slk == "data_subject" and tlk == "internal_system":
            bend_x = src["x"] + src["w"] + 50 + off
            return [_pt(bend_x, sy), _pt(bend_x, ty)]

        if slk == "internal_system" and tlk == "data_subject":
            gx = L["lg_x"] + off
            return [_pt(gx, sy), _pt(gx, ty)]

        if slk == "third_party" and tlk == "internal_system":
            gx = max(src["x"] + src["w"], tgt["x"] + tgt["w"]) + 18 + off
            return [_pt(gx, sy), _pt(gx, ty)]

        if slk == "internal_system" and tlk == "third_party":
            if is_perp:
                if is_h_exit:
                    return [_pt(tx, sy)]
                return [_pt(sx, ty)]
            my = min(bottom, max(sy, ty) + 48 + off)
            return [_pt(sx, my), _pt(tx, my)]

    if n_dots <= 3:
        if is_h_exit and is_h_entry and abs(sy - ty) < 8:
            return []
        if not is_h_exit and not is_h_entry and abs(sx - tx) < 8:
            return []

    if is_perp:
        if is_h_exit:
            return [_pt(tx, sy)]
        return [_pt(sx, ty)]

    if is_h_exit and is_h_entry:
        if n_dots > 3 and abs(sy - ty) < 30:
            arch_h = max(50, n_dots * 14)
            arch_y = max(sy, ty) + arch_h + (fi % 3) * 12 + off
            arch_y = min(arch_y, L["il_bot"] - 20)
            return [_pt(sx, arch_y), _pt(tx, arch_y)]
        mx = (sx + tx) / 2 + off
        return [_pt(mx, sy), _pt(mx, ty)]

    if not is_h_exit and not is_h_entry:
        if abs(sx - tx) < 8:
            return []
        my = (sy + ty) / 2 + off
        return [_pt(sx, my), _pt(tx, my)]

    mx = (sx + tx) / 2 + off
    return [_pt(mx, sy), _pt(mx, ty)]


def _candidate_waypoint_sets(src, tgt, L, fi, exit_dir, entry_dir, flow_ctx, dup_index=0):
    sx, sy = _anchor_xy(src, exit_dir)
    tx, ty = _anchor_xy(tgt, entry_dir)
    off = dup_index * 20
    left, top, right, bottom = _route_bounds(src, tgt, L)
    is_h_exit = exit_dir in ("left", "right")
    is_h_entry = entry_dir in ("left", "right")
    n_dots = flow_ctx.get("n_dots", 0)

    candidates = [_primary_waypoints(src, tgt, L, fi, exit_dir, entry_dir, dup_index, n_dots)]

    if abs(sx - tx) > 4 and abs(sy - ty) > 4:
        candidates.append([_pt(tx, sy)])
        candidates.append([_pt(sx, ty)])

    # Vertical-port side detours: preserve bottom/top semantics while creating
    # a long horizontal inner segment for data dots.
    if not is_h_exit and not is_h_entry and n_dots > 1:
        my = (sy + ty) / 2
        for x in (
            min(src["x"], tgt["x"]) - 26 - off,
            max(src["x"] + src["w"], tgt["x"] + tgt["w"]) + 26 + off,
            left + 30 + off,
            right - 30 - off,
        ):
            xx = max(left, min(right, x))
            candidates.append([_pt(sx, my), _pt(xx, my), _pt(xx, ty)])

    y_candidates = [
        min(src["y"], tgt["y"]) - 20 - off,
        max(src["y"] + src["h"], tgt["y"] + tgt["h"]) + 20 + off,
        top + off,
        bottom - off,
    ]
    x_candidates = [
        min(src["x"], tgt["x"]) - 20 - off,
        max(src["x"] + src["w"], tgt["x"] + tgt["w"]) + 20 + off,
        left + off,
        right + off,
    ]

    for y in y_candidates:
        yy = max(top, min(bottom, y))
        candidates.append([_pt(sx, yy), _pt(tx, yy)])

    for x in x_candidates:
        xx = max(left, min(right, x))
        candidates.append([_pt(xx, sy), _pt(xx, ty)])

    if flow_ctx.get("prefer_return_to_ui"):
        lower_y = min(bottom - 12, max(src["y"] + src["h"], tgt["y"] + tgt["h"]) + 35 + off)
        candidates.append([_pt(sx, lower_y), _pt(tx, lower_y)])
        candidates.append([_pt(sx, lower_y), _pt(tx, lower_y), _pt(tx, ty)])

    if flow_ctx.get("prefer_reporting_sink"):
        if entry_dir == "left":
            runway_x = max(left + 24, min(right - 24, tgt["x"] - 35 - off))
            candidates.append([_pt(runway_x, sy), _pt(runway_x, ty)])
            candidates.append([_pt(runway_x, sy), _pt(runway_x, ty), _pt(tx, ty)])
        elif entry_dir == "right":
            runway_x = max(left + 24, min(right - 24, tgt["x"] + tgt["w"] + 35 + off))
            candidates.append([_pt(runway_x, sy), _pt(runway_x, ty)])
            candidates.append([_pt(runway_x, sy), _pt(runway_x, ty), _pt(tx, ty)])

    def _normalize(wpts):
        result = []
        for pt in wpts:
            if not result or result[-1] != pt:
                result.append(pt)
        return result

    unique = []
    seen = set()
    for wpts in candidates:
        wpts = _normalize(wpts)
        key = tuple(wpts)
        if key not in seen:
            seen.add(key)
            unique.append(wpts)
    return unique


# ───────────────────────── direction choice ───────────────────────────────────

def _choose_direction(src, tgt, flow_ctx):
    """Pick exit/entry direction pair.

    Principles (from user hand-edit analysis):
      - Prefer perpendicular pairs (L-bend = 1 turn) over parallel (S-bend = 2).
      - Cross-lane flows use predefined gutter strategies.
      - Choose the nearest face pair to keep lines short.
    """
    sxc = src["x"] + src["w"] / 2
    syc = src["y"] + src["h"] / 2
    txc = tgt["x"] + tgt["w"] / 2
    tyc = tgt["y"] + tgt["h"] / 2
    dx = txc - sxc
    dy = tyc - syc

    slk = src["entity"]["lane_key"]
    tlk = tgt["entity"]["lane_key"]
    src_entity = src.get("entity") or {}
    tgt_entity = tgt.get("entity") or {}
    src_type = src_entity.get("type", "")
    tgt_type = tgt_entity.get("type", "")
    src_stage = src_entity.get("stage", "")
    tgt_stage = tgt_entity.get("stage", "")
    n_dots = flow_ctx.get("n_dots", 0)

    # ── Cross-lane predefined strategies ─────────────────────────────────
    if slk != tlk:
        if slk == "data_subject" and tlk == "internal_system":
            return "right", "left"
        if slk == "internal_system" and tlk == "data_subject":
            return "left", "left"
        if slk == "third_party" and tlk == "internal_system":
            return "right", "right"
        if slk == "internal_system" and tlk == "third_party":
            return "bottom", ("left" if dx >= 0 else "right")
        if abs(dx) >= abs(dy):
            return ("right" if dx > 0 else "left"), ("left" if dx > 0 else "right")
        return ("bottom" if dy > 0 else "top"), ("top" if dy > 0 else "bottom")

    # ── Same lane ────────────────────────────────────────────────────────
    s_right  = src["x"] + src["w"]
    s_bottom = src["y"] + src["h"]
    t_left   = tgt["x"]
    t_top    = tgt["y"]
    t_right  = tgt["x"] + tgt["w"]
    t_bottom = tgt["y"] + tgt["h"]

    h_gap = s_right < t_left - 5 or t_right < src["x"] - 5
    v_gap = s_bottom < t_top - 5 or t_bottom < src["y"] - 5

    if flow_ctx.get("prefer_return_to_ui") and tgt_type == "ui_function":
        return "bottom", "bottom"

    if flow_ctx.get("prefer_reporting_sink") and h_gap:
        if dx >= 0:
            return "right", "left"
        return "left", "right"

    # Later-stage systems returning to an earlier UI should prefer the
    # upper local corridor and re-enter the UI from the top.
    if (
        h_gap and not v_gap and dx < 0 and
        tgt_type == "ui_function" and
        STAGE_INDEX.get(src_stage, 0) > STAGE_INDEX.get(tgt_stage, 0)
    ):
        return "top", "top"

    # Multi-dot writes into a datastore need a longer usable segment than a
    # center vertical drop can provide. Prefer entering from the side.
    if (
        v_gap and not h_gap and
        tgt_type == "datastore" and
        n_dots > 1
    ):
        return "bottom", ("left" if dx >= 0 else "right")

    if v_gap and not h_gap:
        return ("bottom", "top") if dy > 0 else ("top", "bottom")

    if h_gap and not v_gap:
        return ("right", "left") if dx > 0 else ("left", "right")

    if h_gap and v_gap:
        # Diagonal — try perpendicular L-bend and parallel S-bend candidates.
        # For each quadrant, two perpendicular pairs make geometric sense:
        #   exit horizontal → turn vertical, corner at (entry_x, exit_y)
        #   exit vertical   → turn horizontal, corner at (exit_x, entry_y)
        if dx > 0 and dy > 0:
            perp = [("right", "top"), ("bottom", "left")]
            par  = [("right", "left"), ("bottom", "top")]
        elif dx > 0 and dy < 0:
            perp = [("right", "bottom"), ("top", "left")]
            par  = [("right", "left"), ("top", "bottom")]
        elif dx < 0 and dy > 0:
            perp = [("left", "top"), ("bottom", "right")]
            par  = [("left", "right"), ("bottom", "top")]
        else:
            perp = [("left", "bottom"), ("top", "right")]
            par  = [("left", "right"), ("top", "bottom")]

        best = perp[0]
        best_score = float("inf")
        for ed, nd in perp + par:
            exy = _anchor_xy(src, ed)
            nxy = _anchor_xy(tgt, nd)
            dist = abs(nxy[0] - exy[0]) + abs(nxy[1] - exy[1])
            is_perp = (ed in ("left", "right")) != (nd in ("left", "right"))
            score = dist - (50 if is_perp else 0)

            # Upstream return-to-UI flows should re-enter the UI from below,
            # not from the right edge. This matches the user's hand-edited
            # browser recommendation diagram and improves local readability.
            if dx < 0 and dy < 0 and tgt_type == "ui_function":
                if nd == "bottom":
                    score -= 80
                if ed == "left":
                    score -= 20
                if nd == "right":
                    score += 120
                if ed == "top" and src_type == "internal_system":
                    score += 40

            if score < best_score:
                best_score = score
                best = (ed, nd)
        return best

    if abs(dx) >= abs(dy):
        return ("right" if dx >= 0 else "left"), ("left" if dx >= 0 else "right")
    return ("bottom" if dy >= 0 else "top"), ("top" if dy >= 0 else "bottom")


# ───────────────────────── edge style builder ─────────────────────────────────

def build_edge_style(base_style, src, tgt, exit_dir, entry_dir,
                     exit_port_override=None, entry_port_override=None):
    if exit_port_override:
        ex, ey, ep = exit_port_override
    else:
        ex, ey, ep = _get_port(src, exit_dir)
    if entry_port_override:
        nx, ny, np_ = entry_port_override
    else:
        nx, ny, np_ = _get_port(tgt, entry_dir)

    parts = [base_style]
    parts.append(f"exitX={ex};exitY={ey};exitPerimeter={ep};")
    if ep == 0:
        parts.append("exitDx=0;exitDy=0;")
    parts.append(f"entryX={nx};entryY={ny};entryPerimeter={np_};")
    if np_ == 0:
        parts.append("entryDx=0;entryDy=0;")
    return "".join(parts)


# ───────────────────────── routing ────────────────────────────────────────────

def _path_has_lower_corridor(path, src, tgt):
    threshold = max(src["y"] + src["h"], tgt["y"] + tgt["h"]) + 12
    for a, b in _segments(path):
        if abs(a[1] - b[1]) < 1e-6 and a[1] >= threshold:
            return True
    return False


def _path_has_readable_inner_runway(path, n_dots):
    if n_dots <= 1:
        return False
    needed = DOT_SIZE + max(0, n_dots - 1) * DOT_CLUSTER_GAP + 2 * DOT_PATH_MARGIN
    return _inner_longest_segment_len(path) >= needed


def _lowest_horizontal_y(path):
    ys = [a[1] for a, b in _segments(path) if abs(a[1] - b[1]) < 1e-6]
    return max(ys) if ys else None


def compute_route(src, tgt, L, fi, exit_dir, entry_dir, flow_ctx,
                  dup_index=0, placed=None, used_paths=None, phase="initial"):
    """Return the best waypoint list among low-bend orthogonal candidates.

    Selection priorities:
      1. Avoid intersecting non-source/target entity bounding boxes.
      2. Keep bend count low.
      3. Keep route length short.
    """
    best = None
    ignore_ids = {
        src["entity"]["id"],
        tgt["entity"]["id"],
    }
    n_dots = flow_ctx.get("n_dots", 0)
    prefer_return_to_ui = flow_ctx.get("prefer_return_to_ui")
    prefer_reporting_sink = flow_ctx.get("prefer_reporting_sink")
    prefer_outer_share = (
        src["entity"]["lane_key"] == "internal_system" and
        tgt["entity"]["lane_key"] == "third_party"
    )

    for idx, wpts in enumerate(_candidate_waypoint_sets(
        src, tgt, L, fi, exit_dir, entry_dir, flow_ctx, dup_index
    )):
        path = _full_path(src, tgt, wpts, exit_dir, entry_dir)
        if not _path_respects_ports(path, exit_dir, entry_dir):
            continue
        hits = _path_collision_count(path, placed, ignore_ids)
        overlaps = _path_overlap_count(path, used_paths)
        proximity_penalty = _path_parallel_proximity_penalty(path, used_paths)
        bends = len(wpts)
        needed_seg = 0
        if n_dots > 0:
            needed_seg = DOT_SIZE + max(0, n_dots - 1) * DOT_CLUSTER_GAP + 2 * DOT_PATH_MARGIN
        shortfall = max(0, needed_seg - _longest_segment_len(path))
        inner_shortfall = max(0, needed_seg - _inner_longest_segment_len(path)) if n_dots > 1 else 0
        dup_penalty = 0
        if dup_index > 0 and bends < 2:
            dup_penalty = 3500
        readability_bonus = 0
        if prefer_reporting_sink and _path_has_readable_inner_runway(path, n_dots):
            readability_bonus -= 2200 if phase == "polish" else 1200
        if prefer_return_to_ui and _path_has_lower_corridor(path, src, tgt):
            readability_bonus -= 1600 if phase == "polish" else 900
        if prefer_outer_share and _path_has_lower_corridor(path, src, tgt):
            readability_bonus -= 1400 if phase == "polish" else 800
            low_y = _lowest_horizontal_y(path)
            if low_y is not None:
                readability_bonus -= int(low_y * 0.8)
        score = (
            hits * 100000 +
            overlaps * 5000 +
            proximity_penalty +
            shortfall * DOT_TIGHT_ROUTE_WEIGHT +
            inner_shortfall * 35 +
            dup_penalty +
            readability_bonus +
            bends * 1000 +
            round(_path_len(path)) +
            idx
        )
        if best is None or score < best[0]:
            best = (score, wpts)

    return best[1] if best else []


# ───────────────────────── dot placement ──────────────────────────────────────
def _seg_len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _full_path(src, tgt, wpts, exit_dir, entry_dir):
    return build_edge_path(
        src,
        tgt,
        waypoints=wpts,
        style="",
        fallback_exit_dir=exit_dir,
        fallback_entry_dir=entry_dir,
    )


def _walk(path, t):
    for i in range(len(path) - 1):
        seg = _seg_len(path[i], path[i + 1])
        if t <= seg + 1e-9:
            r = t / max(seg, 1e-9)
            return (path[i][0] + r * (path[i + 1][0] - path[i][0]),
                    path[i][1] + r * (path[i + 1][1] - path[i][1]))
        t -= seg
    return path[-1]


def place_dots(path, count):
    if count <= 0 or len(path) < 2:
        return []
    total = sum(_seg_len(path[i], path[i + 1]) for i in range(len(path) - 1))
    if total < 1:
        return [(path[0][0] + i * (DOT_SIZE + 2) - DOT_SIZE / 2,
                 path[0][1] - DOT_SIZE / 2)
                for i in range(count)]

    if count == 1:
        cluster_ts = [total / 2]
    else:
        usable = max(0, total - 2 * DOT_PATH_MARGIN)
        gap = min(DOT_CLUSTER_GAP, usable / (count - 1)) if usable > 0 else 0
        cluster_len = gap * (count - 1)
        lower = min(DOT_PATH_MARGIN, total / 2)
        upper = max(lower, total - DOT_PATH_MARGIN - cluster_len)
        start = min(max((total - cluster_len) / 2, lower), upper)
        cluster_ts = [start + gap * i for i in range(count)]

    positions = []
    for t in cluster_ts:
        cx, cy = _walk(path, t)
        positions.append((cx - DOT_SIZE / 2, cy - DOT_SIZE / 2))
    return positions


def _segment_axis(seg):
    (x1, y1), (x2, y2) = seg
    return "h" if abs(y1 - y2) < 1e-6 else "v"


def _dot_positions_on_segment(seg, count, size, shift=0, margin=None):
    if count <= 0:
        return []
    (x1, y1), (x2, y2) = seg
    axis = _segment_axis(seg)
    length = _seg_len((x1, y1), (x2, y2))
    if length < 1:
        return []

    if margin is None:
        margin = DOT_PATH_MARGIN
    margin = min(margin, length / 2)
    if count == 1:
        gap = 0
        cluster_len = 0
    else:
        usable = max(0, length - 2 * margin)
        gap = min(DOT_CLUSTER_GAP, usable / (count - 1)) if usable > 0 else 0
        cluster_len = gap * (count - 1)

    lower = min(margin, length / 2)
    upper = max(lower, length - margin - cluster_len)
    start = min(max((length - cluster_len) / 2 + shift, lower), upper)

    rects = []
    for i in range(count):
        t = start + gap * i
        if axis == "h":
            base_x = min(x1, x2) + t
            rects.append((base_x - size / 2, y1 - size / 2, size, size))
        else:
            base_y = min(y1, y2) + t
            rects.append((x1 - size / 2, base_y - size / 2, size, size))
    return rects


def _rect_hits_segments(rect, segments):
    box = (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])
    return sum(1 for seg in segments if _segment_intersects_box(seg[0], seg[1], box))


def _rect_hits_entities(rect, placed):
    box = (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])
    hits = 0
    for node in (placed or {}).values():
        if _rect_intersects_rect(box, _entity_box(node), pad=DOT_ENTITY_PAD):
            hits += 1
    return hits


def _plan_dots_for_path(path, count, other_segments=None,
                        occupied_rects=None, dup_index=0, placed=None):
    if count <= 0 or len(path) < 2:
        return []

    other_segments = other_segments or []
    occupied_rects = occupied_rects or []
    segments = _segments(path)
    if not segments:
        return []

    best = None
    shift_seed = dup_index * (DOT_AVOIDANCE_STEP / 2)
    shift_steps = [shift_seed]
    for step in (DOT_AVOIDANCE_STEP, DOT_AVOIDANCE_STEP * 2, DOT_AVOIDANCE_STEP * 3):
        shift_steps.extend([shift_seed + step, shift_seed - step])

    for idx, seg in enumerate(segments):
        seg_len = _seg_len(*seg)
        if seg_len < DOT_MIN_SIZE + 4:
            continue
        size = DOT_SIZE
        if count == 1 and seg_len < DOT_SHORT_PATH_THRESHOLD:
            size = max(DOT_MIN_SIZE, min(DOT_SIZE, int(seg_len / 3)))

        is_outer = idx == 0 or idx == len(segments) - 1
        segment_margin = DOT_PATH_MARGIN + (size * 0.9 if is_outer else 0)
        inner_bonus = -120 if not is_outer else 0
        outer_penalty = DOT_OUTER_SEG_PENALTY if is_outer and count > 1 else 0
        for shift in shift_steps:
            rects = _dot_positions_on_segment(seg, count, size, shift, segment_margin)
            if len(rects) != count:
                continue
            needed_seg = size + max(0, count - 1) * DOT_CLUSTER_GAP + 2 * DOT_PATH_MARGIN
            tight_penalty = max(0, needed_seg - seg_len)
            entity_hits = sum(_rect_hits_entities(rect, placed) for rect in rects)
            dot_hits = sum(
                1
                for rect in rects
                for occ in occupied_rects
                if _rect_intersects_rect(
                    (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]),
                    occ,
                    pad=2,
                )
            )
            line_hits = sum(_rect_hits_segments(rect, other_segments) for rect in rects)
            score = (
                entity_hits * 50000 +
                dot_hits * 10000 +
                line_hits * 400 +
                tight_penalty * 120 +
                outer_penalty +
                round(abs(shift)) * 5 +
                round(-seg_len) +
                inner_bonus
            )
            if best is None or score < best[0]:
                best = (score, size, rects)

    if best is None:
        return [(x, y, DOT_SIZE) for x, y in place_dots(path, count)]

    _, size, rects = best
    return [(x, y, size) for x, y, _, _ in rects]


def build_color_map(items):
    return {str(it["id"]): DATA_DOT_COLORS[i % len(DATA_DOT_COLORS)]
            for i, it in enumerate(items)}


# ───────────────────────── drawing ────────────────────────────────────────────
def draw_background(b, data, L):
    t1 = ("text;html=1;strokeColor=none;fillColor=none;"
          "align=left;verticalAlign=middle;fontSize=18;fontStyle=1;")
    title = (data.get("title_override") or
             f"{data.get('business_name','').strip()}"
             f"——{data.get('activity_name','').strip()}")
    b.vertex(title, t1, L["title_x"], L["title_y"], L["title_w"], L["title_h"],
             metadata={"codexKind": "title"})

    hdr = "rounded=0;whiteSpace=wrap;html=1;fillColor=#efefef;strokeColor=none;fontSize=12;"
    sub = "rounded=0;whiteSpace=wrap;html=1;fillColor=#f7f7f7;strokeColor=none;fontSize=11;"
    bg  = "rounded=0;whiteSpace=wrap;html=1;fillColor=#f1f1f1;strokeColor=none;"
    lbl = ("rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=none;"
           "fontSize=12;align=center;verticalAlign=middle;")

    for s in STAGES:
        sb = L["stage_b"][s]
        b.vertex(s, hdr, sb["x"], sb["y"], sb["w"], L["hdr_h"],
                 metadata={"codexKind": "stage_header", "codexStage": s})

    sub_y = L["main_y"] + L["hdr_h"] + 8
    for sc, scb in L["sc_b"].items():
        b.vertex(sc, sub, scb["x"], sub_y, scb["w"], L["sub_h"],
                 metadata={"codexKind": "subcolumn_header", "codexSubcolumn": sc})

    for lk in LANES:
        lb = L["lane_b"][lk]
        b.vertex("", bg, lb["x"], lb["y"], lb["w"], lb["h"],
                 metadata={"codexKind": "lane_background", "codexLaneKey": lk})
        b.vertex(LANE_LABELS[lk], lbl,
                 L["ll_x"], lb["y"], L["ll_w"], lb["h"],
                 metadata={"codexKind": "lane_label", "codexLaneKey": lk})


def draw_entities(b, placed):
    for item in placed.values():
        e = item["entity"]
        if e["type"] == "data_item_dot":
            continue
        cid = b.vertex(
            e["name"],
            item["style"],
            item["x"],
            item["y"],
            item["w"],
            item["h"],
            metadata={
                "codexKind": "entity",
                "codexEntityId": e["id"],
                "codexEntityType": e.get("type", ""),
                "codexLaneKey": e.get("lane_key", ""),
                "codexStage": e.get("stage", ""),
                "codexSubcolumn": e.get("subcolumn", ""),
                "codexSemanticRole": e.get("semantic_role", ""),
            },
        )
        item["cell_id"] = cid


def draw_flows(b, data, placed, L, color, polish_mode):
    edge_base = (
        "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
        "jettySize=auto;html=1;endArrow=classic;endFill=1;"
        f"strokeColor={color};strokeWidth=1.5;"
    )
    dot_s = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;"
    cmap  = build_color_map(data.get("data_items") or [])
    edge_records = []

    flows = data.get("flows") or []
    used_paths = []

    pair_counter = defaultdict(int)
    dup_indices = []
    for flow in flows:
        key = (flow["source_entity_id"], flow["target_entity_id"])
        dup_indices.append(pair_counter[key])
        pair_counter[key] += 1

    for fi, flow in enumerate(flows):
        src = placed.get(flow["source_entity_id"])
        tgt = placed.get(flow["target_entity_id"])
        if not src or not tgt:
            continue
        if "cell_id" not in src or "cell_id" not in tgt:
            continue

        dup_idx = dup_indices[fi]
        flow_ctx = build_flow_context(flow, src, tgt)
        exit_dir, entry_dir = _choose_direction(src, tgt, flow_ctx)

        exit_override = None
        entry_override = None
        if dup_idx > 0:
            base_ex, base_ey, base_ep = _get_port(src, exit_dir)
            base_nx, base_ny, base_np = _get_port(tgt, entry_dir)
            shift = dup_idx * 0.15
            if exit_dir in ("right", "left"):
                exit_override = (base_ex, min(0.9, base_ey + shift), base_ep)
                entry_override = (base_nx, min(0.9, base_ny + shift), base_np)
            else:
                exit_override = (min(0.9, base_ex + shift), base_ey, base_ep)
                entry_override = (min(0.9, base_nx + shift), base_ny, base_np)

        n_dots = flow_ctx["n_dots"]
        wpts = compute_route(
            src,
            tgt,
            L,
            fi,
            exit_dir,
            entry_dir,
            flow_ctx,
            dup_idx,
            placed,
            used_paths,
            phase="initial",
        )
        edge_style = build_edge_style(
            edge_base, src, tgt, exit_dir, entry_dir,
            exit_override, entry_override,
        )
        path = build_edge_path(
            src,
            tgt,
            waypoints=wpts,
            style=edge_style,
            fallback_exit_dir=exit_dir,
            fallback_entry_dir=entry_dir,
        )
        used_paths.append(path)
        dot_ids = [str(v) for v in (flow.get("data_item_ids") or [])]
        edge_records.append({
            "flow": flow,
            "flow_ctx": flow_ctx,
            "src": src,
            "tgt": tgt,
            "exit_dir": exit_dir,
            "entry_dir": entry_dir,
            "edge_style": edge_style,
            "path": path,
            "waypoints": wpts,
            "dot_ids": dot_ids,
            "dup_idx": dup_idx,
        })

    if polish_mode == "layout_locked":
        polished = []
        for idx, rec in enumerate(edge_records):
            flow_ctx = rec["flow_ctx"]
            if not (flow_ctx.get("prefer_return_to_ui") or flow_ctx.get("prefer_reporting_sink")):
                polished.append(rec)
                continue
            other_paths = [edge_records[j]["path"] for j in range(len(edge_records)) if j != idx]
            wpts = compute_route(
                rec["src"],
                rec["tgt"],
                L,
                idx,
                rec["exit_dir"],
                rec["entry_dir"],
                flow_ctx,
                rec["dup_idx"],
                placed,
                other_paths,
                phase="polish",
            )
            rec["waypoints"] = wpts
            rec["path"] = build_edge_path(
                rec["src"],
                rec["tgt"],
                waypoints=wpts,
                style=rec["edge_style"],
                fallback_exit_dir=rec["exit_dir"],
                fallback_entry_dir=rec["entry_dir"],
            )
            polished.append(rec)
        edge_records = polished

    for rec in edge_records:
        b.edge(
            rec["src"]["cell_id"],
            rec["tgt"]["cell_id"],
            rec["edge_style"],
            points=rec["waypoints"],
            metadata=flow_metadata(rec["flow"], rec["src"], rec["tgt"], rec["flow_ctx"]),
        )

    all_segments = []
    for idx, rec in enumerate(edge_records):
        for seg in _segments(rec["path"]):
            all_segments.append((idx, seg))

    occupied_rects = []
    for idx, rec in enumerate(edge_records):
        other_segments = [seg for owner, seg in all_segments if owner != idx]
        placements = _plan_dots_for_path(
            rec["path"],
            len(rec["dot_ids"]),
            other_segments=other_segments,
            occupied_rects=occupied_rects,
            dup_index=rec["dup_idx"],
            placed=placed,
        )
        for did, (dx, dy, size) in zip(rec["dot_ids"], placements):
            dc = cmap.get(did, "#999999")
            ds = dot_s + f"fillColor={dc};strokeColor=none;fontColor=#ffffff;fontStyle=1;"
            b.vertex(
                did,
                ds,
                dx,
                dy,
                size,
                size,
                metadata={
                    "codexKind": "data_dot",
                    "codexDataItemId": did,
                    "codexFlowId": rec["flow"].get("id", ""),
                    "codexFlowRole": rec["flow_ctx"].get("flow_role", ""),
                },
            )
            occupied_rects.append((dx, dy, dx + size, dy + size))


def draw_legend(b, data, L, color):
    lx, ly = L["legend_x"], L["legend_y"]
    t1 = ("text;html=1;strokeColor=none;fillColor=none;"
          "align=left;verticalAlign=middle;fontSize=12;fontStyle=1;")
    t2 = ("text;html=1;strokeColor=none;fillColor=none;"
          "align=left;verticalAlign=middle;fontSize=11;")

    b.vertex("图形类型说明", t1, lx, ly, 180, 24, metadata={"codexKind": "legend_header"})
    sy = ly + 32
    symbols = [
        ("数据主体（用户）",           USER_ACTOR_STYLE,                42, 84),
        ("人工操作/第三方（非云服务）", TYPE_STYLES["human_actor"],     110, 36),
        ("界面/功能名称",              TYPE_STYLES["ui_function"],       90, 36),
        ("后台/系统/数据库集",         TYPE_STYLES["internal_system"],  110, 40),
        ("文档/存储",                 TYPE_STYLES["datastore"],          90, 48),
        ("第三方云服务",              TYPE_STYLES["third_party_cloud"],  90, 46),
    ]
    for label, sty, sw, sh in symbols:
        b.vertex(label, sty, lx, sy, sw, sh, metadata={"codexKind": "legend_symbol"})
        sy += sh + 10

    sy += 8
    b.vertex("数据项编号清单", t1, lx, sy, 180, 24, metadata={"codexKind": "legend_header"})
    sy += 30
    items = data.get("data_items") or []
    cmap  = build_color_map(items)
    ds    = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;"
    for item in items:
        sid = str(item["id"])
        dc  = cmap.get(sid, "#999999")
        b.vertex(sid,
                 ds + f"fillColor={dc};strokeColor=none;fontColor=#ffffff;fontStyle=1;",
                 lx, sy, 20, 20,
                 metadata={"codexKind": "legend_dot", "codexDataItemId": sid})
        nm   = item.get("name", "")
        desc = (item.get("description") or "").strip()
        b.vertex(f"{nm}: {desc}" if desc else nm, t2, lx + 26, sy - 2, 295, 24,
                 metadata={"codexKind": "legend_text", "codexDataItemId": sid})
        sy += 28

    sy += 8
    b.vertex("数据处理活动流向说明", t1, lx, sy, 200, 24, metadata={"codexKind": "legend_header"})
    sy += 30
    es = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;"
          f"endArrow=classic;strokeColor={color};strokeWidth=1.5;")
    a  = b.vertex("", "ellipse;fillColor=none;strokeColor=none;", lx,      sy, 1, 1, metadata={"codexKind": "legend_anchor"})
    bv = b.vertex("", "ellipse;fillColor=none;strokeColor=none;", lx + 65, sy, 1, 1, metadata={"codexKind": "legend_anchor"})
    b.edge(a, bv, es, metadata={"codexKind": "legend_edge"})
    act = data.get("activity_name") or ""
    b.vertex(f"{act}（单一数据处理活动）", t2, lx + 82, sy - 10, 250, 24,
             metadata={"codexKind": "legend_text"})


# ───────────────────────── entry point ────────────────────────────────────────
def build_diagram(data, polish_mode="auto"):
    b       = Builder()
    L       = build_layout(data)
    ents, _ = normalize_entities(data)
    placed  = place_entities(data, ents, L)
    color   = (data.get("activity_color") or "").strip() or DEFAULT_ACTIVITY_COLOR
    polish_mode = resolve_polish_mode(data, polish_mode)

    draw_background(b, data, L)
    draw_entities(b, placed)
    draw_flows(b, data, placed, L, color, polish_mode)
    draw_legend(b, data, L, color)
    return b.tostring()


def write_output(content, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def main():
    p = argparse.ArgumentParser(
        description="Generate company-standard Data Flow .drawio file."
    )
    p.add_argument("input",  help="Path to JSON (or YAML) input file.")
    p.add_argument("-o", "--output", help="Output .drawio file path.")
    p.add_argument("--polish-mode", choices=["auto", "none", "layout_locked"], default="auto",
                   help="Route polish mode. 'layout_locked' only rewrites ports/waypoints/dots.")
    args = p.parse_args()
    data = load_input(args.input)
    xml  = build_diagram(data, polish_mode=args.polish_mode)
    out  = args.output or os.path.splitext(args.input)[0] + ".drawio"
    write_output(xml, out)
    print(out)


if __name__ == "__main__":
    main()
