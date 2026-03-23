# company-standard-data-flow

Cursor skill: company-standard **Data Flow Diagram (DFD)** in native **draw.io** XML, with layout rules, routing, numbered data dots, and a **Python validator** (HC-1–HC-5 + checklist).

## Quick start

1. Copy this folder to `~/.cursor/skills/company-standard-data-flow/` (see `SKILL.md`).
2. Copy `company-standard-data-flow-input-template.json`, fill entities / flows / data items.
3. Run:

```bash
python scripts/generate_company_data_flow.py your-input.json -o your-output.drawio
python scripts/validate_company_data_flow.py your-output.drawio your-input.json
```

Requires Python 3. Optional: `pyyaml` for YAML input.

## Contents

- `SKILL.md` — agent instructions and hard constraints
- `references/complete-reference.md` — full spec, validation, iteration notes
- `scripts/` — generator + validator
- `company-standard-data-flow-input-template.json` — JSON template

Upstream collection: [fudan6thyear/SKILLS](https://github.com/fudan6thyear/SKILLS).
