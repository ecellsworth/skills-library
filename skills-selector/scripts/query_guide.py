#!/usr/bin/env python3
"""
query_guide.py — return only the slices of skills-guide.yaml that
skill-selector needs, instead of the full ~1,400-line file.

Usage:
    python3 query_guide.py --guide skills-guide.yaml meta
    python3 query_guide.py --guide skills-guide.yaml manifest
    python3 query_guide.py --guide skills-guide.yaml categories
    python3 query_guide.py --guide skills-guide.yaml match KEYWORD...
    python3 query_guide.py --guide skills-guide.yaml skill NAME

Deliberately standalone (no import from skills-auditor/scripts) per
handoff.md's "create exactly these" file list — stdlib + PyYAML only.

`match` semantics: a category task is included if ANY of the given keywords
case-insensitively substring-matches that task's own name, OR its parent
category's name/description, OR any of its skills' name/when_to_use. When a
task matches via the category/task-level text, ALL of that task's skills are
included (not just the ones whose own text happens to match); when it only
matches via a specific skill's name/when_to_use, only that skill is
included. Multiple keywords are OR'd together. This mirrors "find everything
relevant to any of these words" rather than requiring every word to hit.
"""

import argparse
import json
import sys
import os

try:
    import yaml
except ImportError:
    sys.stderr.write(json.dumps({"error": "PyYAML is required (pip install pyyaml)"}) + "\n")
    sys.exit(2)


def err(msg, code=2):
    sys.stderr.write(json.dumps({"error": msg}) + "\n")
    sys.exit(code)


def load_guide(path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def cmd_meta(guide):
    return {
        "generated": guide.get("generated"),
        "updated": guide.get("updated"),
        "skills_indexed": guide.get("skills_indexed"),
        "conflict_policy": guide.get("conflict_policy"),
        "needs_review": guide.get("needs_review", []),
    }


def cmd_manifest(guide):
    return sorted(guide.get("manifest") or [])


def cmd_categories(guide):
    return [
        {"name": c.get("name"), "description": c.get("description")}
        for c in (guide.get("categories") or [])
    ]


def _hit(text, keywords):
    if text is None:
        return False
    t = str(text).lower()
    return any(k in t for k in keywords)


def cmd_match(guide, keywords):
    keywords = [k.lower() for k in keywords]

    matched_categories = []
    matched_skill_names = set()

    for cat in guide.get("categories") or []:
        cat_hit = _hit(cat.get("name"), keywords) or _hit(cat.get("description"), keywords)
        out_tasks = []
        for task in cat.get("tasks") or []:
            task_hit = cat_hit or _hit(task.get("name"), keywords)
            skills = task.get("skills") or []

            if task_hit:
                included_skills = skills
            else:
                included_skills = [
                    sk for sk in skills
                    if _hit(sk.get("name"), keywords) or _hit(sk.get("when_to_use"), keywords)
                ]

            if included_skills:
                out_tasks.append({
                    "name": task.get("name"),
                    "skills": included_skills,
                    "conflicts": task.get("conflicts", []),
                })
                matched_skill_names.update(sk["name"] for sk in included_skills if sk.get("name"))

        if out_tasks:
            matched_categories.append({
                "name": cat.get("name"),
                "description": cat.get("description"),
                "tasks": out_tasks,
            })

    matched_universal = []
    for s in guide.get("universal_skills") or []:
        hay = [s.get("name"), s.get("purpose")] + list(s.get("tasks") or [])
        if any(_hit(h, keywords) for h in hay):
            matched_universal.append(s)
            if s.get("name"):
                matched_skill_names.add(s["name"])

    if not matched_categories and not matched_universal:
        return {"matches": []}

    ccc = [
        c for c in (guide.get("cross_category_conflicts") or [])
        if set(c.get("between") or []) & matched_skill_names
    ]
    nr = [
        n for n in (guide.get("needs_review") or [])
        if set(n.get("skills") or []) & matched_skill_names
    ]

    return {
        "meta": {
            "generated": guide.get("generated"),
            "updated": guide.get("updated"),
            "skills_indexed": guide.get("skills_indexed"),
        },
        "conflict_policy": guide.get("conflict_policy"),
        "categories": matched_categories,
        "universal_skills": matched_universal,
        "cross_category_conflicts": ccc,
        "needs_review": nr,
    }


def cmd_skill(guide, name):
    result = {
        "name": name,
        "universal": None,
        "routings": [],
        "unrouted": None,
        "conflicts": [],
        "cross_category_conflicts": [],
        "never_use": None,
        "needs_review": [],
    }

    for s in guide.get("universal_skills") or []:
        if s.get("name") == name:
            result["universal"] = s

    for cat in guide.get("categories") or []:
        for task in cat.get("tasks") or []:
            for sk in task.get("skills") or []:
                if sk.get("name") == name:
                    entry = {"category": cat.get("name"), "task": task.get("name")}
                    entry.update(sk)
                    result["routings"].append(entry)
            for c in task.get("conflicts") or []:
                if name in (c.get("between") or []):
                    entry = {"category": cat.get("name"), "task": task.get("name")}
                    entry.update(c)
                    result["conflicts"].append(entry)

    for s in guide.get("unrouted") or []:
        if s.get("name") == name:
            result["unrouted"] = s

    for c in guide.get("cross_category_conflicts") or []:
        if name in (c.get("between") or []):
            result["cross_category_conflicts"].append(c)

    for nu in guide.get("never_use") or []:
        if nu.get("skill") == name:
            result["never_use"] = nu

    for nr in guide.get("needs_review") or []:
        if name in (nr.get("skills") or []):
            result["needs_review"].append(nr)

    return result


def main():
    ap = argparse.ArgumentParser(description="Query slices of a skills-guide.yaml.")
    ap.add_argument("--guide", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("meta")
    sub.add_parser("manifest")
    sub.add_parser("categories")
    p_match = sub.add_parser("match")
    p_match.add_argument("keywords", nargs="+")
    p_skill = sub.add_parser("skill")
    p_skill.add_argument("skill_name")
    args = ap.parse_args()

    if not os.path.exists(args.guide):
        err(f"guide not found: {args.guide}", 2)

    try:
        guide = load_guide(args.guide)
    except Exception as e:
        err(f"failed to parse --guide {args.guide}: {e}", 2)

    if args.cmd == "meta":
        out = cmd_meta(guide)
    elif args.cmd == "manifest":
        out = cmd_manifest(guide)
    elif args.cmd == "categories":
        out = cmd_categories(guide)
    elif args.cmd == "match":
        out = cmd_match(guide, args.keywords)
    elif args.cmd == "skill":
        out = cmd_skill(guide, args.skill_name)
    else:  # pragma: no cover — argparse enforces valid choices
        err(f"unknown command {args.cmd!r}", 2)

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}) + "\n")
        sys.exit(2)
