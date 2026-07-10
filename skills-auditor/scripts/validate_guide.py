#!/usr/bin/env python3
"""
validate_guide.py — the validate function's engine; also run automatically
after guide/update.

Usage:
    python3 validate_guide.py --guide skills-guide.yaml [--inventory inventory.json] \
        [--report skills-guide-report.md] [--fix-mechanical]

See handoff.md section 4 for the full spec.
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _guide_lib import (  # noqa: E402
    dump_yaml,
    load_yaml,
    load_json,
    today,
    validate,
    write_report_md,
)


def err(msg, code=2):
    sys.stderr.write(json.dumps({"error": msg}) + "\n")
    sys.exit(code)


def fix_mechanical(guide: dict):
    """Auto-fix ONLY sort order, dedupe, and skills_indexed. Never touch
    routing, hashes, or entries. Returns list of human-readable fix strings."""
    fixed = []
    manifest = guide.get("manifest") or []
    deduped_sorted = sorted(set(manifest))
    if deduped_sorted != manifest:
        guide["manifest"] = deduped_sorted
        fixed.append("sorted and deduplicated manifest")
    if guide.get("skills_indexed") != len(guide.get("manifest") or []):
        guide["skills_indexed"] = len(guide.get("manifest") or [])
        fixed.append("corrected skills_indexed count")
    return fixed


def main():
    ap = argparse.ArgumentParser(description="Validate a skills-guide.yaml.")
    ap.add_argument("--guide", required=True)
    ap.add_argument("--inventory")
    ap.add_argument("--report")
    ap.add_argument("--fix-mechanical", action="store_true")
    args = ap.parse_args()

    try:
        guide = load_yaml(args.guide)
    except Exception as e:
        err(f"failed to parse --guide {args.guide}: {e}", 2)

    if not isinstance(guide, dict):
        err(f"{args.guide} did not parse to a mapping", 2)

    inventory = None
    if args.inventory:
        try:
            inventory = load_json(args.inventory)
        except Exception as e:
            err(f"failed to parse --inventory {args.inventory}: {e}", 2)

    mechanical_fixes = []
    if args.fix_mechanical:
        mechanical_fixes = fix_mechanical(guide)
        if mechanical_fixes:
            dump_yaml(guide, args.guide)

    findings = validate(guide, inventory)
    clean = len(findings) == 0

    if args.report:
        write_report_md(findings, args.report, run_type="validate", guide_path=args.guide)

    result = {
        "guide": args.guide,
        "checked": today(),
        "clean": clean,
        "findings": findings,
    }
    if mechanical_fixes:
        result["mechanical_fixes"] = mechanical_fixes

    print(json.dumps(result, indent=2, default=str))
    return 0 if clean else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}) + "\n")
        sys.exit(2)
