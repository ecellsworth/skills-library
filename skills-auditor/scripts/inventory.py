#!/usr/bin/env python3
"""
inventory.py — enumerate installed skills and emit name + description + hash,
without the model reading full SKILL.md bodies.

Usage:
    python3 inventory.py [--skills-dir PATH ...] [--names-only]

See handoff.md section 1 for the full spec.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _guide_lib import sha256_12, today  # noqa: E402

try:
    import yaml
except ImportError:
    sys.stderr.write(json.dumps({"error": "PyYAML is required (pip install pyyaml)"}) + "\n")
    sys.exit(2)


def parse_frontmatter(skill_md_path: Path):
    """Read only the YAML frontmatter (between the first two '---' lines).
    Returns a dict, or None if the file has no valid frontmatter block."""
    try:
        text = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None

    fm_text = "\n".join(lines[1:end_idx])
    try:
        fm = yaml.safe_load(fm_text)
    except Exception:
        return {}
    return fm if isinstance(fm, dict) else {}


def gather_roots(cli_dirs):
    roots = []
    env_dirs = os.environ.get("SKILLS_DIRS", "")
    if env_dirs:
        roots.extend([p for p in env_dirs.split(":") if p])
    roots.extend(cli_dirs or [])
    roots.append(str(Path.home() / ".claude" / "skills"))
    roots.append(str(Path.cwd() / ".claude" / "skills"))
    return roots


def scan(roots):
    seen = {}
    scanned = []
    for root in roots:
        rp = Path(root)
        if not rp.is_dir():
            continue
        scanned.append(str(rp))
        try:
            children = sorted(rp.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            fm = parse_frontmatter(skill_md)
            if fm is None:
                continue
            name = fm.get("name") or child.name
            if name in seen:
                continue  # first hit wins (root precedence order)
            desc = "" if fm.get("description") is None else str(fm.get("description"))
            seen[name] = {
                "name": name,
                "description": desc,
                "hash": sha256_12(desc),
                "path": str(skill_md),
            }
    return seen, scanned


def main():
    ap = argparse.ArgumentParser(description="Enumerate installed skills as JSON.")
    ap.add_argument("--skills-dir", action="append", default=[], help="Additional skill root (repeatable)")
    ap.add_argument("--names-only", action="store_true", help="Emit a sorted JSON array of names only")
    args = ap.parse_args()

    roots = gather_roots(args.skills_dir)
    seen, scanned = scan(roots)
    names = sorted(seen.keys())

    if args.names_only:
        print(json.dumps(names))
        return 0

    out = {
        "generated": today(),
        "roots_scanned": scanned,
        "count": len(names),
        "skills": [seen[n] for n in names],
        "note": "Skills installed via plugins/MCP may not appear here; caller must merge its own listing.",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # I/O or usage error
        sys.stderr.write(json.dumps({"error": str(e)}) + "\n")
        sys.exit(2)
