"""
Automated validation script for company-standard Data Flow diagrams.

Parses a generated .drawio file and its corresponding .json input,
then checks Hard Constraints (HC-1 through HC-5) and Checklist items
(CK-1 through CK-5). Outputs a structured JSON report to stdout.

Usage:
    python validate_company_data_flow.py <output.drawio> <input.json>
"""

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from xml.etree import ElementTree as ET

from geometry import (
    build_edge_path,
    direction_from_port,
    entity_center,
    extract_port_spec,
    path_segments,
    seg_len,
)


# ─── Constants (mirrored from generate_company_data_flow.py) ──────────────────

STAGES = ["信息收集", "存储/使用", "分享/传输", "归档/删除"]
LANES = ["data_subject", "internal_staff", "internal_system", "third_party"]
LANE_LABELS = {
    "data_subject": "数据主体",
    "internal_staff": "内部人员",
    "internal_system": "内部系统",
    "third_party": "第三方",
}
LANE_LABELS_REV = {v: k for k, v in LANE_LABELS.items()}

DOT_SIZE = 24
D = DOT_SIZE

SLOT_H = 104
SLOT_PAD_TOP = 20
SLOT_PAD_BOT = 50

MIN_LANE_H = {
    "data_subject": 120, "internal_staff": 60,
    "internal_system": 200, "third_party": 120,
}
MIN_STAGE_W = {
    "信息收集": 150, "存储/使用": 300,
    "分享/传输": 180, "归档/删除": 130,
}

TYPE_EXPECTED_STYLES = {
    "human_actor": ["umlActor", "rounded=1"],
    "ui_function": ["whiteSpace=wrap"],
    "internal_system": ["rounded=1"],
    "datastore": ["cylinder3"],
    "third_party_cloud": ["cloud"],
}


# ─── XML Parsing Helpers ─────────────────────────────────────────────────────

def parse_drawio(path):
    """Parse .drawio XML and extract cells with geometry."""
    tree = ET.parse(path)
    root = tree.getroot()
    cells = []
    for cell in root.iter("mxCell"):
        info = dict(cell.attrib)
        geo = cell.find("mxGeometry")
        if geo is not None:
            for attr in ("x", "y", "width", "height"):
                val = geo.get(attr)
                if val is not None:
                    info["geo_" + attr] = float(val)
        points_el = None
        if geo is not None:
            arr = geo.find("Array")
            if arr is not None:
                points_el = arr
        if points_el is not None:
            pts = []
            for pt in points_el.findall("mxPoint"):
                px = pt.get("x")
                py = pt.get("y")
                if px is not None and py is not None:
                    pts.append((float(px), float(py)))
            info["waypoints"] = pts
        cells.append(info)
    return cells


def load_json_input(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─── Layout Reconstruction ───────────────────────────────────────────────────

def reconstruct_layout(cells):
    """
    Reconstruct lane and stage boundaries from background rectangles.
    Returns dict with 'lanes' and 'stages' bounding boxes.
    """
    bg_style = "fillColor=#f1f1f1"
    hdr_style = "fillColor=#efefef"

    lane_boxes = []
    stage_boxes = []

    for c in cells:
        style = c.get("style", "")
        is_vertex = c.get("vertex") == "1"
        if not is_vertex:
            continue
        has_geo = "geo_x" in c and "geo_y" in c

        if bg_style in style and has_geo:
            lane_boxes.append({
                "x": c["geo_x"], "y": c["geo_y"],
                "w": c["geo_width"], "h": c["geo_height"],
            })
        elif hdr_style in style and has_geo:
            stage_boxes.append({
                "x": c["geo_x"], "y": c["geo_y"],
                "w": c["geo_width"], "h": c["geo_height"],
                "label": c.get("value", ""),
            })

    lane_boxes.sort(key=lambda b: b["y"])
    stage_boxes.sort(key=lambda b: b["x"])

    lanes = {}
    lane_keys_ordered = list(LANE_LABELS.keys())
    for i, box in enumerate(lane_boxes):
        if i < len(lane_keys_ordered):
            lanes[lane_keys_ordered[i]] = box

    stages = {}
    for box in stage_boxes:
        label = box.get("label", "").strip()
        if label in STAGES:
            stages[label] = box

    return {"lanes": lanes, "stages": stages}


def find_entity_cells(cells, json_data):
    """
    Match JSON entities to drawn mxCell vertices by value (name).
    Returns dict: entity_id -> cell info with geometry.
    """
    entity_map = {}
    all_entities = []
    for lk in LANES:
        block = (json_data.get("lanes") or {}).get(lk) or {}
        for e in block.get("entities") or []:
            e["_lane_key"] = lk
            all_entities.append(e)

    name_to_entity = {}
    id_to_entity = {}
    for e in all_entities:
        name_to_entity[e["name"]] = e
        id_to_entity[e["id"]] = e

    vertex_cells = [
        c for c in cells
        if c.get("vertex") == "1" and "geo_x" in c
    ]

    for c in vertex_cells:
        val = (c.get("value") or "").strip()
        ent = None
        meta_id = (c.get("codexEntityId") or "").strip()
        if meta_id and meta_id in id_to_entity:
            ent = id_to_entity[meta_id]
        elif val in name_to_entity:
            ent = name_to_entity[val]
        if ent:
            entity_map[ent["id"]] = {
                "entity": ent,
                "cell_id": c.get("id"),
                "x": c["geo_x"],
                "y": c["geo_y"],
                "w": c.get("geo_width", 0),
                "h": c.get("geo_height", 0),
                "style": c.get("style", ""),
            }

    return entity_map


def find_edge_cells(cells):
    """Extract all edge cells with source, target, style, and waypoints."""
    edges = []
    for c in cells:
        if c.get("edge") == "1":
            edges.append({
                "id": c.get("id"),
                "source": c.get("source"),
                "target": c.get("target"),
                "style": c.get("style", ""),
                "waypoints": c.get("waypoints", []),
                "flow_id": c.get("codexFlowId", ""),
                "flow_role": c.get("codexFlowRole", ""),
            })
    return edges


def find_dot_cells(cells):
    """Find all data dot circles (ellipse with aspect=fixed and small size)."""
    dots = []
    for c in cells:
        if c.get("vertex") != "1":
            continue
        if c.get("codexKind") == "legend_dot":
            continue
        if c.get("codexKind") == "data_dot":
            dots.append({
                "id": c.get("id"),
                "label": (c.get("value") or "").strip(),
                "x": c.get("geo_x", 0),
                "y": c.get("geo_y", 0),
                "w": c.get("geo_width", 0),
                "h": c.get("geo_height", 0),
            })
            continue
        style = c.get("style", "")
        if "ellipse" in style and "aspect=fixed" in style:
            w = c.get("geo_width", 0)
            if w <= DOT_SIZE + 4:
                dots.append({
                    "id": c.get("id"),
                    "label": (c.get("value") or "").strip(),
                    "x": c.get("geo_x", 0),
                    "y": c.get("geo_y", 0),
                    "w": w,
                    "h": c.get("geo_height", 0),
                })
    return dots


# ─── Geometry Helpers ─────────────────────────────────────────────────────────

def point_in_box(px, py, box, pad=5):
    """Check if point (px, py) is inside box dict with keys x, y, w, h."""
    return (box["x"] - pad <= px <= box["x"] + box["w"] + pad and
            box["y"] - pad <= py <= box["y"] + box["h"] + pad)


def segments_parallel_distance(seg_a, seg_b):
    """
    If two segments are roughly parallel (both horizontal or both vertical),
    return the perpendicular distance between them. Otherwise return None.
    """
    (ax1, ay1), (ax2, ay2) = seg_a
    (bx1, by1), (bx2, by2) = seg_b

    a_horiz = abs(ay1 - ay2) < 2
    a_vert = abs(ax1 - ax2) < 2
    b_horiz = abs(by1 - by2) < 2
    b_vert = abs(bx1 - bx2) < 2

    if a_horiz and b_horiz:
        a_left, a_right = min(ax1, ax2), max(ax1, ax2)
        b_left, b_right = min(bx1, bx2), max(bx1, bx2)
        overlap = min(a_right, b_right) - max(a_left, b_left)
        if overlap > 5:
            return abs(ay1 - by1)
    elif a_vert and b_vert:
        a_top, a_bot = min(ay1, ay2), max(ay1, ay2)
        b_top, b_bot = min(by1, by2), max(by1, by2)
        overlap = min(a_bot, b_bot) - max(a_top, b_top)
        if overlap > 5:
            return abs(ax1 - bx1)

    return None
def extract_exit_entry_dirs(style):
    """Extract exit and entry directions from edge style string."""
    dirs = {}
    for key in ("exitX", "exitY", "entryX", "entryY"):
        m = re.search(rf"{key}=([\d.]+)", style)
        if m:
            dirs[key] = float(m.group(1))
    return dirs


def segment_intersects_box(a, b, box):
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


def edge_overlap_segment(seg_a, seg_b):
    (ax1, ay1), (ax2, ay2) = seg_a
    (bx1, by1), (bx2, by2) = seg_b

    a_h = abs(ay1 - ay2) < 2
    b_h = abs(by1 - by2) < 2
    a_v = abs(ax1 - ax2) < 2
    b_v = abs(bx1 - bx2) < 2

    if a_h and b_h and abs(ay1 - by1) < 2:
        a0, a1 = sorted((ax1, ax2))
        b0, b1 = sorted((bx1, bx2))
        lo = max(a0, b0)
        hi = min(a1, b1)
        if hi - lo > 5:
            return ((lo, ay1), (hi, ay1))
    if a_v and b_v and abs(ax1 - bx1) < 2:
        a0, a1 = sorted((ay1, ay2))
        b0, b1 = sorted((by1, by2))
        lo = max(a0, b0)
        hi = min(a1, b1)
        if hi - lo > 5:
            return ((ax1, lo), (ax1, hi))
    return None


# ─── Check Functions ─────────────────────────────────────────────────────────

def check_hc1_row_column(entity_map, layout):
    """HC-1: Every entity must be inside its declared lane and stage."""
    fails = []
    lanes = layout["lanes"]
    stages = layout["stages"]

    for eid, info in entity_map.items():
        ent = info["entity"]
        lk = ent["_lane_key"]
        stage = ent.get("stage", "存储/使用")
        cx, cy = entity_center(info)

        lane_ok = True
        if lk in lanes:
            lb = lanes[lk]
            if not (lb["y"] - 10 <= cy <= lb["y"] + lb["h"] + 10):
                lane_ok = False

        stage_ok = True
        if stage in stages:
            sb = stages[stage]
            if not (sb["x"] - 10 <= cx <= sb["x"] + sb["w"] + 10):
                stage_ok = False

        if not lane_ok or not stage_ok:
            reasons = []
            if not lane_ok:
                reasons.append(f"not in lane '{LANE_LABELS.get(lk, lk)}'")
            if not stage_ok:
                reasons.append(f"not in stage '{stage}'")
            fails.append(f"Entity '{ent['name']}' ({eid}): {'; '.join(reasons)}")

    return {
        "id": "HC-1",
        "name": "行列投射 (Row-Column Projection)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "All entities correctly placed.",
    }


def check_hc2_flow_spacing(entity_map, json_data):
    """HC-2: Flow spacing must be >= (N+2)*D in the primary direction."""
    fails = []
    flows = json_data.get("flows") or []

    for flow in flows:
        src_id = flow["source_entity_id"]
        tgt_id = flow["target_entity_id"]
        src = entity_map.get(src_id)
        tgt = entity_map.get(tgt_id)
        if not src or not tgt:
            continue

        n_dots = len(flow.get("data_item_ids") or [])
        required = (n_dots + 2) * D

        dx = abs(entity_center(src)[0] - entity_center(tgt)[0])
        dy = abs(entity_center(src)[1] - entity_center(tgt)[1])

        primary_dist = max(dx, dy)
        if primary_dist < required:
            fails.append(
                f"Flow '{flow.get('id', '?')}' ({src_id}->{tgt_id}): "
                f"distance={primary_dist:.0f}px, required=({n_dots}+2)*D="
                f"{required}px (N={n_dots})"
            )

    return {
        "id": "HC-2",
        "name": "连线间距 (N+2)D (Flow Spacing)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "All flows have sufficient spacing.",
    }


def check_hc4_parallel_spacing(entity_map, edge_cells, json_data):
    """HC-4: Parallel line segments must be >= 2D (48px) apart."""
    fails = []
    min_required = 2 * D

    cell_id_to_entity = {}
    for eid, info in entity_map.items():
        cid = info.get("cell_id")
        if cid:
            cell_id_to_entity[cid] = info

    all_segments = []
    for edge in edge_cells:
        src_info = cell_id_to_entity.get(edge["source"])
        tgt_info = cell_id_to_entity.get(edge["target"])
        if not src_info or not tgt_info:
            continue
        path = build_edge_path(
            src_info,
            tgt_info,
            waypoints=edge.get("waypoints", []),
            style=edge.get("style", ""),
        )
        segs = path_segments(path)
        for seg in segs:
            if seg_len(seg[0], seg[1]) > 10:
                all_segments.append((edge["id"], seg))

    violations = []
    for i in range(len(all_segments)):
        for j in range(i + 1, len(all_segments)):
            eid_a, seg_a = all_segments[i]
            eid_b, seg_b = all_segments[j]
            if eid_a == eid_b:
                continue
            dist = segments_parallel_distance(seg_a, seg_b)
            if dist is not None and dist < min_required and dist > 0.5:
                violations.append(
                    f"Edges {eid_a} & {eid_b}: parallel distance={dist:.0f}px < {min_required}px"
                )

    if len(violations) > 5:
        summary = f"{len(violations)} parallel spacing violations found. First 5: "
        fails = [summary + "; ".join(violations[:5])]
    else:
        fails = violations

    return {
        "id": "HC-4",
        "name": "连线间距>=2D (Parallel Line Spacing)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "All parallel segments have sufficient spacing.",
    }


def check_hc5_port_allocation(entity_map, edge_cells):
    """HC-5: Each side gets 1 dedicated line; overlap only when total > 4."""
    fails = []

    cell_id_to_eid = {}
    for eid, info in entity_map.items():
        cid = info.get("cell_id")
        if cid:
            cell_id_to_eid[cid] = eid

    connections_per_entity = defaultdict(lambda: defaultdict(int))
    total_per_entity = defaultdict(int)

    for edge in edge_cells:
        style = edge.get("style", "")
        dirs = extract_exit_entry_dirs(style)

        src_cid = edge.get("source")
        tgt_cid = edge.get("target")

        if src_cid in cell_id_to_eid:
            eid = cell_id_to_eid[src_cid]
            total_per_entity[eid] += 1
            if "exitX" in dirs and "exitY" in dirs:
                d = direction_from_port(dirs["exitX"], dirs["exitY"])
                if d == "center" and entity_map[eid]["entity"].get("type") == "third_party_cloud":
                    d = "left" if dirs["exitX"] < 0.5 else "right"
                connections_per_entity[eid][d] += 1

        if tgt_cid in cell_id_to_eid:
            eid = cell_id_to_eid[tgt_cid]
            total_per_entity[eid] += 1
            if "entryX" in dirs and "entryY" in dirs:
                d = direction_from_port(dirs["entryX"], dirs["entryY"])
                if d == "center" and entity_map[eid]["entity"].get("type") == "third_party_cloud":
                    d = "left" if dirs["entryX"] < 0.5 else "right"
                connections_per_entity[eid][d] += 1

    for eid, side_counts in connections_per_entity.items():
        total = total_per_entity[eid]
        if total <= 4:
            entity = entity_map[eid]["entity"]
            side_limit = 1
            if entity.get("type") == "third_party_cloud":
                side_limit = 2
            for side, count in side_counts.items():
                if count > side_limit:
                    ename = entity["name"]
                    fails.append(
                        f"Entity '{ename}' ({eid}): {count} lines on {side} side "
                        f"but total connections={total} <= 4"
                    )

    return {
        "id": "HC-5",
        "name": "四面端口优先 (Four-Side Port Priority)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "Port allocation within limits.",
    }


def build_edge_geometries(entity_map, edge_cells):
    cell_id_to_entity = {}
    for eid, info in entity_map.items():
        cid = info.get("cell_id")
        if cid:
            cell_id_to_entity[cid] = info

    records = []
    for edge in edge_cells:
        src_info = cell_id_to_entity.get(edge["source"])
        tgt_info = cell_id_to_entity.get(edge["target"])
        if not src_info or not tgt_info:
            continue
        path = build_edge_path(
            src_info,
            tgt_info,
            waypoints=edge.get("waypoints", []),
            style=edge.get("style", ""),
        )
        records.append({
            "edge": edge,
            "src": src_info,
            "tgt": tgt_info,
            "path": path,
            "segments": path_segments(path),
        })
    return records


def check_hc6_unrelated_entity_crossing(entity_map, edge_cells):
    """HC-6: No edge may pass through an unrelated entity box."""
    fails = []
    edge_records = build_edge_geometries(entity_map, edge_cells)

    for rec in edge_records:
        edge = rec["edge"]
        src_id = rec["src"]["entity"]["id"]
        tgt_id = rec["tgt"]["entity"]["id"]
        for eid, info in entity_map.items():
            if eid in (src_id, tgt_id):
                continue
            box = (
                info["x"] - 8,
                info["y"] - 8,
                info["x"] + info["w"] + 8,
                info["y"] + info["h"] + 8,
            )
            if any(segment_intersects_box(a, b, box) for a, b in rec["segments"]):
                fails.append(
                    f"Edge {edge['id']} ({edge.get('flow_id') or '?'}) intersects unrelated entity "
                    f"'{info['entity']['name']}'"
                )

    return {
        "id": "HC-6",
        "name": "不得穿越无关模块 (No Unrelated Entity Crossing)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "No edges cross unrelated entity boxes.",
    }


def check_hc7_semantic_merge(entity_map, edge_cells):
    """HC-7: Distinct semantic flows must keep readable independent corridors."""
    fails = []
    edge_records = build_edge_geometries(entity_map, edge_cells)
    min_shared = 48

    for i in range(len(edge_records)):
        for j in range(i + 1, len(edge_records)):
            a = edge_records[i]
            b = edge_records[j]
            ea = a["edge"]
            eb = b["edge"]
            sa = a["src"]["entity"]["id"]
            ta = a["tgt"]["entity"]["id"]
            sb = b["src"]["entity"]["id"]
            tb = b["tgt"]["entity"]["id"]

            relation = None
            if sa == sb and ta != tb:
                relation = "same_source"
                seg_pairs = [(a["segments"][0], b["segments"][0])] if a["segments"] and b["segments"] else []
            elif ta == tb and sa != sb:
                relation = "same_target"
                seg_pairs = [(a["segments"][-1], b["segments"][-1])] if a["segments"] and b["segments"] else []
            elif sa == tb and ta == sb:
                relation = "opposite_direction"
                seg_pairs = [
                    (seg_a, seg_b)
                    for seg_a in a["segments"]
                    for seg_b in b["segments"]
                ]
            else:
                continue

            for seg_a, seg_b in seg_pairs:
                overlap = edge_overlap_segment(seg_a, seg_b)
                if overlap is None:
                    continue
                if seg_len(*overlap) < min_shared:
                    continue
                fails.append(
                    f"Edges {ea['id']} ({ea.get('flow_id') or '?'}) and {eb['id']} ({eb.get('flow_id') or '?'}) "
                    f"share a {relation} corridor too early (overlap {seg_len(*overlap):.0f}px)"
                )
                break

    return {
        "id": "HC-7",
        "name": "不同语义流不得过早合流 (No Early Semantic Merge)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "Distinct semantic flows keep independent readable corridors.",
    }


def check_ck1_page_structure(cells):
    """CK-1: Title, 4 stages, 4 lanes, legend area must exist."""
    fails = []

    all_values = [c.get("value", "").strip() for c in cells if c.get("vertex") == "1"]

    for stage in STAGES:
        if not any(stage in v for v in all_values):
            fails.append(f"Missing stage: '{stage}'")

    for lk, label in LANE_LABELS.items():
        if not any(label in v for v in all_values):
            fails.append(f"Missing lane label: '{label}'")

    has_title = any("——" in v or "—" in v for v in all_values)
    if not has_title:
        found_biz = any(len(v) > 10 and "fontSize=18" in (c.get("style", ""))
                        for c in cells for v in [(c.get("value") or "").strip()] if v)
        if not found_biz:
            fails.append("Missing diagram title (expected format: '业务名称——活动名称')")

    legend_keywords = ["图形类型说明", "数据项编号清单", "数据处理活动"]
    legend_found = sum(1 for kw in legend_keywords if any(kw in v for v in all_values))
    if legend_found < 2:
        fails.append("Legend area incomplete (expected '图形类型说明' and '数据项编号清单')")

    return {
        "id": "CK-1",
        "name": "页面结构 (Page Structure)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "Page structure complete.",
    }


def check_ck2_shape_types(entity_map):
    """CK-2: Entity shape styles must match their declared type."""
    fails = []

    for eid, info in entity_map.items():
        ent = info["entity"]
        etype = ent.get("type", "internal_system")
        style = info.get("style", "")
        lk = ent.get("_lane_key", "")

        if etype == "human_actor" and lk == "data_subject":
            if "umlActor" not in style:
                fails.append(f"Entity '{ent['name']}': data_subject human_actor should use umlActor shape")
        elif etype == "third_party_cloud":
            if "cloud" not in style:
                fails.append(f"Entity '{ent['name']}': third_party_cloud should use cloud shape")
        elif etype == "datastore":
            if "cylinder" not in style:
                fails.append(f"Entity '{ent['name']}': datastore should use cylinder shape")

    return {
        "id": "CK-2",
        "name": "图形类型 (Shape Types)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "All shapes match declared types.",
    }


def check_ck3_data_dots(dot_cells, json_data):
    """CK-3: Data dots count and labels match data_items in JSON."""
    fails = []

    items = json_data.get("data_items") or []
    expected_ids = set(str(it["id"]) for it in items)
    found_ids = set(d["label"] for d in dot_cells if d["label"])

    missing = expected_ids - found_ids
    extra = found_ids - expected_ids

    if missing:
        fails.append(f"Missing data dot labels: {sorted(missing)}")
    if extra:
        fails.append(f"Extra data dot labels not in data_items: {sorted(extra)}")

    return {
        "id": "CK-3",
        "name": "数据圆点 (Data Dots)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "All data dots present and matched.",
    }


def check_ck4_flow_completeness(entity_map, edge_cells, json_data):
    """CK-4: Every flow in JSON has a corresponding edge in the diagram."""
    fails = []

    cell_id_to_eid = {}
    for eid, info in entity_map.items():
        cid = info.get("cell_id")
        if cid:
            cell_id_to_eid[cid] = eid

    drawn_pairs = set()
    for edge in edge_cells:
        src_eid = cell_id_to_eid.get(edge["source"])
        tgt_eid = cell_id_to_eid.get(edge["target"])
        if src_eid and tgt_eid:
            drawn_pairs.add((src_eid, tgt_eid))

    flows = json_data.get("flows") or []
    for flow in flows:
        pair = (flow["source_entity_id"], flow["target_entity_id"])
        if pair not in drawn_pairs:
            fails.append(
                f"Flow '{flow.get('id', '?')}' ({pair[0]}->{pair[1]}): no matching edge found"
            )

    return {
        "id": "CK-4",
        "name": "连线完整性 (Flow Completeness)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "All flows have corresponding edges.",
    }


def check_ck5_bend_count(edge_cells):
    """CK-5: Allow readability-driven extra bends for special semantic flows."""
    fails = []

    for edge in edge_cells:
        wpts = edge.get("waypoints", [])
        flow_role = edge.get("flow_role", "")
        allowance = 3
        if flow_role in ("return_to_ui", "reporting", "analysis_report", "third_party_return"):
            allowance = 4
        if len(wpts) > allowance:
            fails.append(
                f"Edge {edge['id']} ({edge.get('source','?')}->{edge.get('target','?')}): "
                f"{len(wpts)} waypoints (max {allowance} for flow_role='{flow_role or 'default'}')"
            )

    return {
        "id": "CK-5",
        "name": "拐点约束 (Bend Count)",
        "status": "PASS" if not fails else "FAIL",
        "details": "; ".join(fails) if fails else "All edges within bend limit.",
    }


# ─── Main Validation Pipeline ────────────────────────────────────────────────

def validate(drawio_path, json_path):
    cells = parse_drawio(drawio_path)
    json_data = load_json_input(json_path)

    layout = reconstruct_layout(cells)
    entity_map = find_entity_cells(cells, json_data)
    edge_cells = find_edge_cells(cells)
    dot_cells = find_dot_cells(cells)

    checks = [
        check_hc1_row_column(entity_map, layout),
        check_hc2_flow_spacing(entity_map, json_data),
        {"id": "HC-3", "name": "布局优先于连线 (Layout-First)", "status": "SKIP",
         "details": "Process constraint; not verifiable from static output."},
        check_hc4_parallel_spacing(entity_map, edge_cells, json_data),
        check_hc5_port_allocation(entity_map, edge_cells),
        check_hc6_unrelated_entity_crossing(entity_map, edge_cells),
        check_hc7_semantic_merge(entity_map, edge_cells),
        check_ck1_page_structure(cells),
        check_ck2_shape_types(entity_map),
        check_ck3_data_dots(dot_cells, json_data),
        check_ck4_flow_completeness(entity_map, edge_cells, json_data),
        check_ck5_bend_count(edge_cells),
    ]

    n_pass = sum(1 for c in checks if c["status"] == "PASS")
    n_fail = sum(1 for c in checks if c["status"] == "FAIL")
    n_skip = sum(1 for c in checks if c["status"] == "SKIP")
    overall = "PASS" if n_fail == 0 else "FAIL"

    report = {
        "overall": overall,
        "checks": checks,
        "summary": {
            "pass": n_pass,
            "fail": n_fail,
            "skip": n_skip,
            "total": len(checks),
        },
    }
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Validate a company-standard Data Flow .drawio against its JSON input."
    )
    parser.add_argument("drawio", help="Path to the generated .drawio file.")
    parser.add_argument("json_input", help="Path to the JSON input file.")
    args = parser.parse_args()

    report = validate(args.drawio, args.json_input)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    sys.exit(0 if report["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()
