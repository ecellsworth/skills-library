#!/usr/bin/env python3
"""
Shared library for skills-auditor scripts (inventory.py, build_guide.py,
merge_guide.py, validate_guide.py).

Not a standalone CLI. Deliberately dependency-free beyond stdlib + PyYAML so
every script that imports it keeps the "stdlib + PyYAML only" contract.

Per handoff.md: "put in a small module or duplicate carefully" — this is the
module. build_guide.py and validate_guide.py both call `validate()` so the
in-process post-build check in build_guide.py is guaranteed to run the exact
same checks validate_guide.py's CLI runs.
"""

import hashlib
import sys
from datetime import date

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write('{"error": "PyYAML is required (pip install pyyaml)"}\n')
    sys.exit(2)


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def today() -> str:
    return date.today().isoformat()


def sha256_12(text) -> str:
    """First 12 hex chars of sha256 of a UTF-8, stripped string."""
    text = "" if text is None else str(text)
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:12]


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        data = {}
    return data


def dump_yaml_str(data) -> str:
    return yaml.dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )


def dump_yaml(data, path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(dump_yaml_str(data))


def load_json(path):
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Shared schema knowledge
# ---------------------------------------------------------------------------

# Copied verbatim from skills-auditor/SKILL.md's conflict_policy YAML block.
CONFLICT_POLICY = [
    "explicit user preference recorded in this guide",
    "documented conflict resolution (task-level or cross_category_conflicts)",
    "tighter category match (category-bound beats universal inside its category)",
    "tighter task match (description names the task most specifically)",
    "narrower scope wins (more constrained trigger description)",
    "still tied -> assign neither; record under needs_review as needs_user_decision",
]

REQUIRED_TOP_LEVEL_KEYS = [
    "generated",
    "updated",
    "skills_indexed",
    "manifest",
    "universal_skills",
    "categories",
    "never_use",
    "unrouted",
]

NEW_SCHEMA_KEYS = ["conflict_policy", "hashes", "cross_category_conflicts", "needs_review"]

TOP_LEVEL_KEY_ORDER = [
    "generated",
    "updated",
    "skills_indexed",
    "conflict_policy",
    "manifest",
    "hashes",
    "universal_skills",
    "categories",
    "cross_category_conflicts",
    "never_use",
    "unrouted",
    "needs_review",
]


def new_empty_guide() -> dict:
    return {
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


def ordered_guide(guide: dict) -> dict:
    """Return a copy of guide with top-level keys in TOP_LEVEL_KEY_ORDER,
    preserving any unknown extra keys at the end."""
    out = {}
    for k in TOP_LEVEL_KEY_ORDER:
        if k in guide:
            out[k] = guide[k]
    for k, v in guide.items():
        if k not in out:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Validation engine (used by validate_guide.py CLI and build_guide.py's
# in-process post-write check)
# ---------------------------------------------------------------------------

def _collect_routing(guide: dict):
    """Returns (universal_names, category_names, unrouted_names, routing_counts)."""
    universal_names = {s.get("name") for s in (guide.get("universal_skills") or []) if s.get("name")}
    category_names = set()
    routing_counts = {}
    for cat in guide.get("categories") or []:
        for task in cat.get("tasks") or []:
            for sk in task.get("skills") or []:
                name = sk.get("name")
                if not name:
                    continue
                category_names.add(name)
                routing_counts[name] = routing_counts.get(name, 0) + 1
    unrouted_names = {s.get("name") for s in (guide.get("unrouted") or []) if s.get("name")}
    return universal_names, category_names, unrouted_names, routing_counts


def validate(guide: dict, inventory: dict = None) -> list:
    """Run all checks from validate_guide.py's spec against a parsed guide
    dict (and optional parsed inventory dict). Returns a list of finding
    dicts: {"check", "severity", "detail", "skills", "proposed_fix"}.
    Pure function — never mutates `guide` or `inventory`.
    """
    findings = []

    # 1. schema
    missing_required = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in guide]
    if missing_required:
        findings.append({
            "check": "schema",
            "severity": "fail",
            "detail": "missing required top-level key(s): " + ", ".join(missing_required),
            "skills": [],
            "proposed_fix": "add the missing top-level key(s)",
        })
    missing_new = [k for k in NEW_SCHEMA_KEYS if k not in guide]
    if missing_new:
        findings.append({
            "check": "legacy_schema",
            "severity": "warn",
            "detail": "guide predates the new schema; missing section(s): " + ", ".join(missing_new),
            "skills": [],
            "proposed_fix": "run build_guide.py, or merge_guide.py, to migrate to the new schema",
        })

    manifest = guide.get("manifest") or []
    manifest_set = set(manifest)

    universal_names, category_names, unrouted_names, routing_counts = _collect_routing(guide)

    # 2/3/4. drift checks (only with --inventory)
    if inventory is not None:
        inv_skills = {s["name"]: s for s in (inventory.get("skills") or []) if s.get("name")}
        inv_names = set(inv_skills.keys())

        missing = inv_names - manifest_set
        if missing:
            findings.append({
                "check": "drift_missing",
                "severity": "warn",
                "detail": f"{len(missing)} installed skill(s) not present in manifest",
                "skills": sorted(missing),
                "proposed_fix": "run /skills-auditor update",
            })

        non_namespaced_manifest = {n for n in manifest_set if ":" not in n}
        stale = non_namespaced_manifest - inv_names
        if stale:
            findings.append({
                "check": "drift_stale",
                "severity": "warn",
                "detail": f"{len(stale)} manifest entr(y/ies) no longer installed",
                "skills": sorted(stale),
                "proposed_fix": "propose removal via /skills-auditor validate (requires user approval)",
            })

        hashes = guide.get("hashes") or {}
        changed = []
        for name, inv in inv_skills.items():
            stored = hashes.get(name)
            current = inv.get("hash")
            if stored and current and stored != current:
                changed.append(name)
        if changed:
            findings.append({
                "check": "drift_changed",
                "severity": "warn",
                "detail": f"{len(changed)} skill(s) whose description hash changed since indexing",
                "skills": sorted(changed),
                "proposed_fix": "reclassify these skills and update their hash",
            })

    # 5. structure
    structure_details = []
    structure_skills = set()
    if manifest != sorted(manifest):
        structure_details.append("manifest is not alphabetically sorted")
    if len(manifest) != len(manifest_set):
        dupes = sorted({n for n in manifest if manifest.count(n) > 1})
        structure_details.append("manifest has duplicate entries: " + ", ".join(dupes))
        structure_skills.update(dupes)
    if guide.get("skills_indexed") != len(manifest):
        structure_details.append(
            f"skills_indexed ({guide.get('skills_indexed')!r}) != len(manifest) ({len(manifest)})"
        )
    all_routed = universal_names | category_names | unrouted_names
    unrouted_from_manifest = manifest_set - all_routed
    if unrouted_from_manifest:
        structure_details.append(
            f"{len(unrouted_from_manifest)} manifest entr(y/ies) not routed anywhere "
            "(not in universal_skills, a category task, or unrouted)"
        )
        structure_skills.update(unrouted_from_manifest)
    routed_not_in_manifest = all_routed - manifest_set
    if routed_not_in_manifest:
        structure_details.append(
            f"{len(routed_not_in_manifest)} routed name(s) not present in manifest"
        )
        structure_skills.update(routed_not_in_manifest)
    if structure_details:
        findings.append({
            "check": "structure",
            "severity": "fail",
            "detail": "; ".join(structure_details),
            "skills": sorted(structure_skills),
            "proposed_fix": "fix manifest sort/dedupe, skills_indexed, and/or routing",
        })

    # 6. routing
    routing_details = []
    routing_skills = set()
    dual = category_names & unrouted_names
    if dual:
        routing_details.append(f"{len(dual)} skill(s) appear in both a category and unrouted")
        routing_skills.update(dual)

    missing_note_skills = set()
    for cat in guide.get("categories") or []:
        for task in cat.get("tasks") or []:
            for sk in task.get("skills") or []:
                name = sk.get("name")
                if not name:
                    continue
                total_routings = routing_counts.get(name, 0) + (1 if name in universal_names else 0)
                if total_routings > 1 and not sk.get("routing_note"):
                    missing_note_skills.add(name)
    if missing_note_skills:
        routing_details.append(
            f"{len(missing_note_skills)} multi-routed skill(s) missing a non-null routing_note"
        )
        routing_skills.update(missing_note_skills)

    if routing_details:
        findings.append({
            "check": "routing",
            "severity": "fail",
            "detail": "; ".join(routing_details),
            "skills": sorted(routing_skills),
            "proposed_fix": "add routing_note to every entry of a multi-routed skill, "
                             "or remove the duplicate category/unrouted listing",
        })

    # 7. conflict_refs
    all_names = manifest_set | universal_names | category_names | unrouted_names
    bad_refs = set()

    def _check_conflicts(conflicts_list):
        for c in conflicts_list or []:
            for n in c.get("between") or []:
                if n not in all_names:
                    bad_refs.add(n)

    for cat in guide.get("categories") or []:
        for task in cat.get("tasks") or []:
            _check_conflicts(task.get("conflicts"))
    _check_conflicts(guide.get("cross_category_conflicts"))

    if bad_refs:
        findings.append({
            "check": "conflict_refs",
            "severity": "fail",
            "detail": f"{len(bad_refs)} conflict 'between' reference(s) name a skill absent from the guide",
            "skills": sorted(bad_refs),
            "proposed_fix": "fix the skill name or remove the stale conflict entry",
        })

    # 8. needs_review_hygiene
    bad_items = []
    for i, item in enumerate(guide.get("needs_review") or []):
        if not item.get("kind") or not item.get("detail") or not item.get("raised"):
            bad_items.append(item)
    if bad_items:
        flat_skills = sorted({s for item in bad_items for s in (item.get("skills") or [])})
        findings.append({
            "check": "needs_review_hygiene",
            "severity": "warn",
            "detail": f"{len(bad_items)} needs_review item(s) missing kind/detail/raised",
            "skills": flat_skills,
            "proposed_fix": "fill in the missing kind/detail/raised fields",
        })

    return findings


def has_fail(findings) -> bool:
    return any(f.get("severity") == "fail" for f in findings)


def write_report_md(findings, path, run_type: str, guide_path: str) -> None:
    """Write (or delete) the skills-guide-report.md per SKILL.md's Reporting
    Rules: only exists when there are findings; overwritten every run."""
    import os

    if not findings:
        if os.path.exists(path):
            os.remove(path)
        return

    by_check = {}
    for f in findings:
        by_check.setdefault(f["check"], []).append(f)

    lines = []
    lines.append("# Skills Guide Report")
    lines.append("")
    lines.append(f"**Run type**: {run_type}")
    lines.append(f"**Date**: {today()}")
    lines.append(f"**Guide**: {guide_path}")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    for check, items in by_check.items():
        lines.append(f"### {check}")
        lines.append("")
        for it in items:
            lines.append(f"- **severity**: {it['severity']}")
            lines.append(f"  **detail**: {it['detail']}")
            if it.get("skills"):
                lines.append(f"  **skills**: {', '.join(it['skills'])}")
            if it.get("proposed_fix"):
                lines.append(f"  **proposed fix**: {it['proposed_fix']}")
        lines.append("")

    lines.append("## Actions Taken")
    lines.append("")
    lines.append("- None applied automatically (see proposed fixes above); "
                  "re-run with --fix-mechanical for mechanical fixes, or approve "
                  "changes via /skills-auditor update or validate.")
    lines.append("")

    lines.append("## Open needs_review Items")
    lines.append("")
    nr_findings = by_check.get("needs_review_hygiene")
    if nr_findings:
        lines.append("- See needs_review_hygiene findings above.")
    else:
        lines.append("- None surfaced by this run.")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
