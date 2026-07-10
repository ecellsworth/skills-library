#!/usr/bin/env python3
"""
build_guide.py — assemble a complete skills-guide.yaml from per-skill
classification records emitted by the model.

Usage:
    python3 build_guide.py --records records.json --inventory inventory.json \
        --out skills-guide.yaml [--force] [--extra-hashes extra.json]

See handoff.md section 2 for the full spec.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _guide_lib import (  # noqa: E402
    CONFLICT_POLICY,
    dump_yaml,
    has_fail,
    load_json,
    ordered_guide,
    today,
    validate,
)


def err(msg, code=2):
    sys.stderr.write(json.dumps({"error": msg}) + "\n")
    sys.exit(code)


def get_or_create_category(categories, cat_index, name, description):
    if name not in cat_index:
        cat = {"name": name, "description": description or "", "tasks": []}
        categories.append(cat)
        cat_index[name] = {"cat": cat, "tasks": {}}
    else:
        if description and not cat_index[name]["cat"].get("description"):
            cat_index[name]["cat"]["description"] = description
    return cat_index[name]


def get_or_create_task(cat_entry, task_name):
    tasks_idx = cat_entry["tasks"]
    if task_name not in tasks_idx:
        task = {"name": task_name, "skills": []}
        cat_entry["cat"]["tasks"].append(task)
        tasks_idx[task_name] = task
    return tasks_idx[task_name]


def add_task_conflict(task, conflict):
    entry = {"between": conflict["between"], "resolution": conflict.get("resolution", "")}
    existing = task.setdefault("conflicts", [])
    key = frozenset(entry["between"])
    for e in existing:
        if frozenset(e.get("between", [])) == key:
            return  # already recorded, avoid duplicates
    existing.append(entry)


def add_cross_category_conflict(guide, conflict):
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


def build(records, inventory, extra_hashes):
    guide = {
        "generated": today(),
        "updated": None,
        "skills_indexed": 0,
        "conflict_policy": list(CONFLICT_POLICY),
        "manifest": [],
        "hashes": {},
        "universal_skills": [],
        "categories": [],
        "cross_category_conflicts": [],
        "never_use": [],
        "unrouted": [],
        "needs_review": [],
    }

    inv_hashes = {s["name"]: s.get("hash") for s in (inventory.get("skills") or []) if s.get("name")}
    extra_hashes = extra_hashes or {}

    cat_index = {}
    manifest = []
    missing_hash_skills = []

    # Track which (category, task) each record routed to, for attaching
    # same-category conflicts to every task the record actually landed in.
    record_task_homes = {}

    for rec in records:
        name = rec["name"]
        manifest.append(name)

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
            err(f"record {name!r} has unknown scope {scope!r} (expected universal|category|unrouted)", 2)

        record_task_homes[name] = homes

        # never_use
        if rec.get("never_use"):
            nu = rec["never_use"]
            guide["never_use"].append({
                "skill": name,
                "never_apply_to": nu.get("never_apply_to", []) or [],
                "reason": nu.get("reason", ""),
            })

        # needs_review
        for item in rec.get("needs_review", []) or []:
            guide["needs_review"].append({
                "kind": item.get("kind", "needs_user_decision"),
                "detail": item.get("detail", ""),
                "skills": item.get("skills", []) or [],
                "raised": today(),
            })

    # Second pass: attach conflicts now that every record's task homes are known
    for rec in records:
        name = rec["name"]
        for conflict in rec.get("conflicts", []) or []:
            if conflict.get("cross_category"):
                add_cross_category_conflict(guide, conflict)
            else:
                homes = record_task_homes.get(name, [])
                if not homes:
                    # Conflict declared by a universal/unrouted record with no
                    # category task to attach to — fall back to cross-category
                    # so the information isn't silently dropped.
                    add_cross_category_conflict(guide, conflict)
                    continue
                for cat_name, task_name in homes:
                    cat_entry = cat_index[cat_name]
                    task = cat_entry["tasks"][task_name]
                    add_task_conflict(task, conflict)

    if missing_hash_skills:
        err(
            "missing hash for skill(s) not found in --inventory or --extra-hashes: "
            + ", ".join(sorted(missing_hash_skills)),
            2,
        )

    manifest = sorted(manifest)
    guide["manifest"] = manifest
    guide["skills_indexed"] = len(manifest)

    return ordered_guide(guide)


def main():
    ap = argparse.ArgumentParser(description="Assemble skills-guide.yaml from classification records.")
    ap.add_argument("--records", required=True)
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--extra-hashes")
    args = ap.parse_args()

    if os.path.exists(args.out) and not args.force:
        err(f"{args.out} already exists; pass --force to overwrite", 2)

    try:
        records = load_json(args.records)
    except Exception as e:
        err(f"failed to parse --records {args.records}: {e}", 2)
    try:
        inventory = load_json(args.inventory)
    except Exception as e:
        err(f"failed to parse --inventory {args.inventory}: {e}", 2)

    extra_hashes = {}
    if args.extra_hashes:
        try:
            extra_hashes = load_json(args.extra_hashes)
        except Exception as e:
            err(f"failed to parse --extra-hashes {args.extra_hashes}: {e}", 2)

    if not isinstance(records, list):
        err("--records must be a JSON array of record objects", 2)

    guide = build(records, inventory, extra_hashes)

    dump_yaml(guide, args.out)

    findings = validate(guide, inventory)
    if has_fail(findings):
        print(json.dumps({"written": args.out, "clean": False, "findings": findings}, indent=2, default=str))
        return 1

    print(json.dumps({
        "written": args.out,
        "skills_indexed": guide["skills_indexed"],
        "clean": True,
        "findings": findings,  # warn-level only, if any
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
