#!/usr/bin/env python3
"""
merge_guide.py — append-only merge of new classification records into an
existing skills-guide.yaml.

Usage:
    python3 merge_guide.py --guide skills-guide.yaml --records new-records.json \
        --inventory inventory.json [--dry-run]

See handoff.md section 3 for the full spec.
"""

import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _guide_lib import (  # noqa: E402
    dump_yaml,
    dump_yaml_str,
    load_yaml,
    load_json,
    today,
)


def err(msg, code=2):
    sys.stderr.write(json.dumps({"error": msg}) + "\n")
    sys.exit(code)


def get_or_create_category(categories, cat_index, name, description):
    if name not in cat_index:
        cat = {"name": name, "description": description or "", "tasks": []}
        categories.append(cat)  # new categories appended at the end
        cat_index[name] = {"cat": cat, "tasks": {}}
    else:
        if description and not cat_index[name]["cat"].get("description"):
            cat_index[name]["cat"]["description"] = description
    return cat_index[name]


def get_or_create_task(cat_entry, task_name):
    tasks_idx = cat_entry["tasks"]
    if task_name not in tasks_idx:
        task = {"name": task_name, "skills": []}
        cat_entry["cat"]["tasks"].append(task)  # new tasks appended at the end
        tasks_idx[task_name] = task
    return tasks_idx[task_name]


def add_task_conflict(task, conflict):
    entry = {"between": conflict["between"], "resolution": conflict.get("resolution", "")}
    existing = task.setdefault("conflicts", [])
    key = frozenset(entry["between"])
    for e in existing:
        if frozenset(e.get("between", [])) == key:
            return
    existing.append(entry)


def add_cross_category_conflict(guide, conflict):
    guide.setdefault("cross_category_conflicts", [])
    entry = {
        "between": conflict["between"],
        "categories": conflict.get("categories", []),
        "resolution": conflict.get("resolution", ""),
    }
    existing = guide["cross_category_conflicts"]
    key = frozenset(entry["between"])
    for e in existing:
        if frozenset(e.get("between", [])) == key:
            return
    existing.append(entry)


def build_category_index(guide):
    """Index the *existing* categories/tasks in-place so new records can be
    appended into them without disturbing already-written entries."""
    cat_index = {}
    for cat in guide.get("categories") or []:
        tasks_idx = {t["name"]: t for t in cat.get("tasks") or []}
        cat_index[cat["name"]] = {"cat": cat, "tasks": tasks_idx}
    return cat_index


def find_existing_skill_task(guide, name):
    """Return list of (category_name, task_name) this already-indexed skill
    is routed to, for attaching bidirectional conflict notes."""
    homes = []
    for cat in guide.get("categories") or []:
        for task in cat.get("tasks") or []:
            for sk in task.get("skills") or []:
                if sk.get("name") == name:
                    homes.append((cat["name"], task["name"]))
    return homes


def apply_records(guide, records, inv_hashes, extra_hashes):
    manifest_set = set(guide.get("manifest") or [])
    rejected = [r["name"] for r in records if r["name"] in manifest_set]
    if rejected:
        return None, sorted(set(rejected))

    guide.setdefault("hashes", {})
    guide.setdefault("categories", [])
    guide.setdefault("universal_skills", [])
    guide.setdefault("unrouted", [])
    guide.setdefault("never_use", [])
    guide.setdefault("cross_category_conflicts", [])
    guide.setdefault("needs_review", [])

    cat_index = build_category_index(guide)
    new_names = []
    record_task_homes = {}
    missing_hash_skills = []

    for rec in records:
        name = rec["name"]
        new_names.append(name)

        h = inv_hashes.get(name) or extra_hashes.get(name)
        if h:
            guide["hashes"][name] = h
        else:
            missing_hash_skills.append(name)

        scope = rec.get("scope")
        homes = []

        if scope == "universal":
            guide["universal_skills"].append({
                "name": name,
                "purpose": rec.get("purpose", ""),
                "tasks": rec.get("tasks", []) or [],
                "whole_project": bool(rec.get("whole_project", False)),
                "never_use_for": rec.get("never_use_for", []) or [],
            })

        elif scope == "category":
            for routing in rec.get("routings", []) or []:
                cat_entry = get_or_create_category(
                    guide["categories"], cat_index,
                    routing["category"], routing.get("category_description"),
                )
                task = get_or_create_task(cat_entry, routing["task"])
                skill_entry = {"name": name, "when_to_use": routing.get("when_to_use", "")}
                if routing.get("never_use_when"):
                    skill_entry["never_use_when"] = routing["never_use_when"]
                if routing.get("routing_note"):
                    skill_entry["routing_note"] = routing["routing_note"]
                task["skills"].append(skill_entry)
                homes.append((routing["category"], routing["task"]))

        elif scope == "unrouted":
            guide["unrouted"].append({"name": name, "reason": rec.get("unrouted_reason", "")})

        else:
            return None, [f"record {name!r} has unknown scope {scope!r}"]

        record_task_homes[name] = homes

        if rec.get("never_use"):
            nu = rec["never_use"]
            guide["never_use"].append({
                "skill": name,
                "never_apply_to": nu.get("never_apply_to", []) or [],
                "reason": nu.get("reason", ""),
            })

        for item in rec.get("needs_review", []) or []:
            guide["needs_review"].append({
                "kind": item.get("kind", "needs_user_decision"),
                "detail": item.get("detail", ""),
                "skills": item.get("skills", []) or [],
                "raised": today(),
            })

    if missing_hash_skills:
        return None, [f"missing hash for: {', '.join(sorted(missing_hash_skills))}"]

    # Second pass: conflicts, including bidirectional notes referencing
    # already-existing skills. We NEVER edit an existing skill's own fields —
    # we only append conflict metadata to the task/cross_category_conflicts
    # list the new skill (or the referenced existing skill) lives in.
    for rec in records:
        name = rec["name"]
        for conflict in rec.get("conflicts", []) or []:
            if conflict.get("cross_category"):
                add_cross_category_conflict(guide, conflict)
                continue

            homes = list(record_task_homes.get(name, []))
            if not homes:
                # e.g. a universal/unrouted new record conflicting with a
                # category-bound existing skill — attach at the existing
                # skill's home(s) instead.
                for other in conflict.get("between", []):
                    if other != name:
                        homes.extend(find_existing_skill_task(guide, other))

            if not homes:
                add_cross_category_conflict(guide, conflict)
                continue

            for cat_name, task_name in homes:
                cat_entry = cat_index.get(cat_name)
                if not cat_entry:
                    continue
                task = cat_entry["tasks"].get(task_name)
                if not task:
                    continue
                add_task_conflict(task, conflict)

    guide["manifest"] = sorted(manifest_set | set(new_names))
    guide["skills_indexed"] = len(guide["manifest"])
    guide["updated"] = today()

    return new_names, None


def main():
    ap = argparse.ArgumentParser(description="Append-only merge of new records into an existing guide.")
    ap.add_argument("--guide", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--extra-hashes")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        guide = load_yaml(args.guide)
    except Exception as e:
        err(f"failed to parse --guide {args.guide}: {e}", 2)

    if not isinstance(guide, dict):
        err(f"{args.guide} did not parse to a mapping", 2)

    # Snapshot BEFORE mutation, serialized through the same dumper we'll use
    # for the AFTER state. Diffing dumper-vs-dumper (rather than the raw file
    # vs. the dumper's output) keeps the diff free of incidental reformatting
    # noise from PyYAML's canonical style differing from however the file was
    # originally hand-written/formatted.
    before_text = dump_yaml_str(guide)

    try:
        records = load_json(args.records)
    except Exception as e:
        err(f"failed to parse --records {args.records}: {e}", 2)
    if not isinstance(records, list):
        err("--records must be a JSON array of record objects", 2)

    try:
        inventory = load_json(args.inventory)
    except Exception as e:
        err(f"failed to parse --inventory {args.inventory}: {e}", 2)
    inv_hashes = {s["name"]: s.get("hash") for s in (inventory.get("skills") or []) if s.get("name")}

    extra_hashes = {}
    if args.extra_hashes:
        try:
            extra_hashes = load_json(args.extra_hashes)
        except Exception as e:
            err(f"failed to parse --extra-hashes {args.extra_hashes}: {e}", 2)

    new_names, problem = apply_records(guide, records, inv_hashes, extra_hashes)
    if problem is not None:
        print(json.dumps({"error": "records rejected", "skills": problem}, indent=2))
        return 1

    if args.dry_run:
        after_text = dump_yaml_str(guide)
        diff = difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=args.guide,
            tofile=args.guide + " (proposed)",
        )
        sys.stdout.writelines(diff)
        return 0

    dump_yaml(guide, args.guide)
    print(json.dumps({
        "guide": args.guide,
        "added": new_names,
        "skills_indexed": guide["skills_indexed"],
        "updated": guide["updated"],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}) + "\n")
        sys.exit(2)
