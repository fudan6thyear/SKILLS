import argparse
import json
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_company_data_flow as generator
import validate_company_data_flow as validator


def load_manifest(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_expectations(case, report):
    errors = []
    expected_overall = case.get("expected_overall")
    if expected_overall and report.get("overall") != expected_overall:
        errors.append(
            f"expected overall={expected_overall}, got {report.get('overall')}"
        )

    expected_checks = case.get("expected_checks") or {}
    report_checks = {c["id"]: c["status"] for c in report.get("checks", [])}
    for check_id, expected_status in expected_checks.items():
        actual = report_checks.get(check_id)
        if actual != expected_status:
            errors.append(
                f"expected {check_id}={expected_status}, got {actual}"
            )
    return errors


def run_case(case, fixtures_root):
    json_path = fixtures_root / case["json"]
    mode = case["mode"]
    if mode == "validate_existing":
        drawio_path = fixtures_root / case["drawio"]
        report = validator.validate(str(drawio_path), str(json_path))
        return report

    if mode == "generate_and_validate":
        data = generator.load_input(str(json_path))
        with tempfile.TemporaryDirectory(prefix="company-dfd-fixture-") as tmpdir:
            out = Path(tmpdir) / f"{case['id']}.drawio"
            xml = generator.build_diagram(data)
            generator.write_output(xml, str(out))
            report = validator.validate(str(out), str(json_path))
            return report

    raise ValueError(f"Unsupported fixture mode: {mode}")


def main():
    parser = argparse.ArgumentParser(description="Run company-standard-data-flow regression fixtures.")
    parser.add_argument(
        "--manifest",
        default=str(SKILL_ROOT / "fixtures" / "manifest.json"),
        help="Fixture manifest path.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    fixtures_root = manifest_path.parent
    cases = load_manifest(manifest_path)

    failures = []
    for case in cases:
        report = run_case(case, fixtures_root)
        errors = check_expectations(case, report)
        status = "PASS" if not errors else "FAIL"
        print(f"[{status}] {case['id']}: overall={report.get('overall')}")
        if errors:
            for err in errors:
                print(f"  - {err}")
            failures.append(case["id"])

    if failures:
        print(f"\nRegression mismatches: {', '.join(failures)}")
        sys.exit(1)

    print(f"\nAll {len(cases)} regression fixtures matched expectations.")


if __name__ == "__main__":
    main()
