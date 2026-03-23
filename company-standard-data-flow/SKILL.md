---
name: company-standard-data-flow
description: Generate, validate, and refine company-standard Data Flow diagrams in native draw.io XML. Covers layout, routing, dot placement, and automated subagent validation. Use when the user asks for a data flow diagram, DFD, draw.io data map, privacy data flow, or wants an existing .drawio diagram improved.
---

# Company Standard Data Flow

Use this skill for the full lifecycle of company-standard Data Flow diagrams: input normalization, draw.io generation, automated validation via subagent, and absorbing manual edits into reusable rules.

## Install (Cursor)

Copy this entire folder into your Cursor skills directory, preserving the folder name:

- **macOS / Linux:** `~/.cursor/skills/company-standard-data-flow/`
- **Windows:** `%USERPROFILE%\.cursor\skills\company-standard-data-flow\`

You need **Python 3** on PATH. Optional: `pip install pyyaml` if you use YAML input instead of JSON.

All generator and validator paths below are relative to the **skill root** (`company-standard-data-flow/`).

## Use This Skill When

- The user asks for a `Data Flow` / `DFD` / `draw.io` diagram.
- The user gives a business description and wants it turned into a structured diagram.
- The user wants to improve an existing `.drawio` output.
- The user manually edits a generated diagram and wants the intent identified and packaged back into the project.

## Hard Constraints

The following rules are **non-negotiable**. Every generated diagram must satisfy all of them before delivery. `D = DOT_SIZE = 24px` is the base measurement unit.

### HC-1 Row-Column Projection (行列投射)

Every entity must be placed inside the correct **lane** (row) and **stage** (column) as declared in the input JSON. No entity may visually cross lane or stage boundaries.

Validation: entity `(x, y)` must fall within the Y-range of its `lane_key` swimlane and the X-range of its `stage` column.

### HC-2 Flow Spacing = (N+2)D (连线间距)

For each flow connecting two entities, the available distance between source and target in the **primary direction of the connecting line** must be >= `(N + 2) * D`, where `N` is the number of data dots on that flow.

- If the path has bends and dots are distributed across multiple directions, each direction must independently satisfy `(n_i + 2) * D` where `n_i` is the number of dots allocated to that direction's segment.
- When this constraint cannot be met, **adjust entity positions first** (increase `SLOT_H`, `stage_w`, or add `layout_hint`), not just the route.

### HC-3 Layout-First Adjustment (布局优先于连线)

When any spacing constraint is violated, the fix priority is:

1. **Move entities** — increase lane height, stage width, or apply `layout_hint.x/y`
2. **Reroute lines** — change exit/entry direction or add waypoints
3. **Adjust dots** — shift dot cluster position or reduce dot size

Never only adjust lines while leaving entity positions unchanged.

### HC-4 Parallel Line Spacing >= 2D (连线间距)

Any two parallel line segments must be separated by at least `2D = 48px`. This applies to all co-directional segments regardless of which flow they belong to.

### HC-5 Four-Side Port Priority (四面端口优先)

Each entity has four connection sides (top, right, bottom, left). Each side gets **one dedicated line** by default. Only when an entity has more than 4 connections total may lines overlap within `2D` of the entity boundary.

## Core Rules

- Output native draw.io XML only.
- Four fixed stages: `信息收集` / `存储/使用` / `分享/传输` / `归档/删除`.
- Four fixed lanes: `数据主体` / `内部人员` / `内部系统` / `第三方`.
- **Adaptive canvas (v7)**: lane heights and stage widths are computed dynamically from entity counts and sizes — never assume a fixed page size.
- One diagram = one data processing activity; one `activity_color` for all main flow lines.
- Use numbered data dots to differentiate data items.
- **Routing (v6+)**: prefer L-bends; normally <= 2 bends per edge; extra bends only when dot count demands a wider arch.
- **Collision avoidance (v8)**: candidate routes are scored for entity collision, path overlap, and dot space sufficiency.
- **Semantic routing (v8.1/v8.2)**: return-to-UI flows and multi-dot datastore writes use context-aware port selection.

## Preferred Workflow

1. **Normalize input**: convert the user's business description into template fields.
2. **Fill JSON**: duplicate `company-standard-data-flow-input-template.json` next to your working files (or in the skill root) and fill `activity_name`, `activity_color`, entities, `data_items`, and `flows`.
3. **Generate diagram** (run from skill root, or use absolute paths to the scripts):

```powershell
cd $env:USERPROFILE\.cursor\skills\company-standard-data-flow
python ".\scripts\generate_company_data_flow.py" ".\my-flow.json" -o ".\my-flow.drawio"
```

4. **Launch validation subagent**: use the Cursor `Task` tool to start a `shell` subagent that runs the validation script. Use the following prompt template:

```
Run the DFD validation script and return the full JSON report. Command:

python "scripts/validate_company_data_flow.py" "<drawio_path>" "<json_path>"

(Run from the company-standard-data-flow skill directory, or use full paths to both the script and files.)

Read the script's stdout (a JSON report) and return it to me verbatim. Do not modify or omit any content.
```

5. **Check validation result**:
   - **All checks PASS** → proceed to step 6.
   - **Any check FAIL** → proceed to step 7.

6. **Deliver final `.drawio`** to the user.

7. **Fix issues based on report**: read the failed check details and apply fixes in priority order (HC-3: layout first, then routing, then dots). Typical fixes:
   - HC-1 fail → move entity to correct lane/stage in JSON, or fix `layout_hint`
   - HC-2 fail → increase `SLOT_H` or `stage_w`, or add `layout_hint` to spread entities
   - HC-4 fail → adjust waypoints or entity positions to create more separation
   - HC-5 fail → redistribute connections across different sides (or merge duplicate same-direction flows in JSON; bidirectional pairs may need a manual `.drawio` tweak until the generator handles return ports automatically)
   - Then return to step 3 and regenerate.

8. **Absorb manual edits**: if the user hand-edits the delivered diagram, compare edited vs generated files, infer visual intent, then update generator, JSON input, and this skill when the intent is reusable.

## Important Files in This Skill

| File | Role |
|------|------|
| `scripts/generate_company_data_flow.py` | Diagram generator |
| `scripts/validate_company_data_flow.py` | Automated validation (JSON report on stdout) |
| `company-standard-data-flow-input-template.json` | Input schema starter |

## References

- Complete reference (spec + rules + checklist + iteration history): [references/complete-reference.md](references/complete-reference.md)

## Repository

Published as part of [fudan6thyear/SKILLS](https://github.com/fudan6thyear/SKILLS).
