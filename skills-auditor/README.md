# skills-auditor

**The skill for creating, maintaining, and validating your skills knowledge base (`skills-guide.yaml`).**

## Purpose

`skills-auditor` helps you build and maintain a structured `skills-guide.yaml` file that documents how your installed skills should be used. This guide acts as a single source of truth for consistent skill assignment across projects.

Its main functions are:
- `guide` — Create `skills-guide.yaml` from scratch
- `update` — Incrementally add newly installed skills to an existing guide
- `validate` — Check the guide against the installed library and the schema; repair with user approval

> **Note**: For breaking down prompts and assigning skills, the recommended tool is now **`skill-selector`** (especially in Guide Mode).

## Bundled Scripts

All mechanical YAML work — inventorying, assembling, merging, and checking — is done by scripts in `scripts/`, not by the model re-emitting YAML by hand. The model's job is classification judgment only: it reads skill descriptions and emits compact per-skill JSON records; the scripts turn those records into a valid guide.

| Script | Used by | Purpose |
|---|---|---|
| `scripts/inventory.py` | guide, update, validate | Scan installed skills; emit name + description + hash as JSON, reading only SKILL.md frontmatter (never the full body). |
| `scripts/build_guide.py` | guide | Assemble a complete `skills-guide.yaml` from per-skill JSON classification records. |
| `scripts/merge_guide.py` | update | Append new classification records into an existing guide; updates manifest/hashes/counts/dates. Supports `--dry-run` to preview a diff before writing. |
| `scripts/validate_guide.py` | validate (and automatically after every guide/update run) | Schema check, installed-vs-indexed drift detection, duplicate/orphan/routing checks. Supports `--fix-mechanical` for safe auto-fixes and `--report` to write a findings report. |

All four scripts are Python 3.9+, stdlib + PyYAML only, and safe to run directly:

```bash
python3 skills-auditor/scripts/inventory.py --skills-dir ~/.claude/skills
python3 skills-auditor/scripts/build_guide.py --records records.json --inventory inventory.json --out skills-guide.yaml
python3 skills-auditor/scripts/merge_guide.py --guide skills-guide.yaml --records new-records.json --inventory inventory.json --dry-run
python3 skills-auditor/scripts/validate_guide.py --guide skills-guide.yaml --inventory inventory.json --report skills-guide-report.md
```

If a script is missing or fails, the skill falls back to doing that step manually and notes the fallback in its run summary — the scripts are an optimization, not a hard dependency.

## Main Functions

### 1. `/skills-auditor guide`
Creates a new `skills-guide.yaml` file by inventorying and classifying all your installed skills, then assembling it with `build_guide.py`. Runs `validate_guide.py` immediately afterward and fixes any structural findings before presenting the result.

Use this when:
- Setting up for the first time
- You want to rebuild your knowledge base

### 2. `/skills-auditor update`
Inventories, diffs against the existing manifest, classifies only the newly installed skills, and appends them via `merge_guide.py` (never rewriting existing entries). Shows a proposed diff for confirmation before writing.

Use this when:
- You install new skills
- You want to keep your guide current with minimal effort

### 3. `/skills-auditor validate`
Runs `validate_guide.py` against the guide (and, if available, a fresh inventory) to check schema correctness, drift, structure, routing rules, and conflict references. This is the only function permitted to modify existing entries — and only with explicit user approval per change, except for purely mechanical fixes (sort order, counts), which `--fix-mechanical` applies automatically.

Use this when:
- You want to confirm the guide still matches what's installed
- You suspect the guide has drifted, has duplicate/orphaned routing, or references a skill that no longer exists

## Core Principles

**Purpose, not proximity.** A skill is recorded for a task only when it is required for that specific task and will improve the result.

**Scope: universal vs. category-bound.** Every skill is one of:
- *Universal* — applicable to any project category
- *Category-bound* — designed for a specific domain and must never be used outside it

**Multi-routing policy.** A skill may appear in more than one place (universal + category, or two categories) only when each routing independently earns its place. Every multi-routed skill must carry a non-null `routing_note` on each entry. A skill may never appear in both a category and `unrouted` — `validate_guide.py`'s `routing` check enforces both rules.

**Conflict Policy.** A shared, decidable 6-rung tie-breaker ladder (explicit preference → documented resolution → tighter category match → tighter task match → narrower scope → still tied, defer to `needs_review`) is written into the guide's `conflict_policy:` block so `skill-selector` reads the same rules `skills-auditor` used to write it. See SKILL.md for the full ladder.

## Output

`skills-auditor` generates or updates a `skills-guide.yaml` file containing:

- `manifest` — alphabetical list of every indexed skill
- `hashes` — a short content hash per skill (from its frontmatter description), used to detect when a skill's description changes after indexing
- `conflict_policy` — the shared tie-breaker ladder
- `universal_skills` — skills usable across any project category
- `categories` → `tasks` → `skills` — category-bound skills with `when_to_use` / `never_use_when` / (when multi-routed) `routing_note`, plus task-level `conflicts`
- `cross_category_conflicts` — overlaps that span two categories, kept out of any single category's task list
- `never_use` — explicit misuse guardrails
- `unrouted` — skills with no routing anywhere else
- `needs_review` — open items (undecided conflicts, ambiguous classifications, drift) that only a user decision can close

The file is written in **YAML** for maximum reliability when agents parse it, while remaining readable by humans. `validate_guide.py` and `merge_guide.py` write it with a stable dumper configuration (`sort_keys=False, default_flow_style=False, allow_unicode=True`) so repeated runs produce clean, minimal diffs.

### Legacy guides

A `skills-guide.yaml` written before this schema update (missing `conflict_policy`, `hashes`, `cross_category_conflicts`, or `needs_review`) still validates — `validate_guide.py` flags the gap as a `legacy_schema` **warning**, not a failure. Running `merge_guide.py` against a legacy guide automatically adds the missing sections as it merges in new skills.

## Where Should `skills-guide.yaml` Live?

Both `skills-auditor` and `skill-selector` look for the guide in this order:

1. Current working directory
2. Project root

### Recommended Locations

| Rank | Location | Recommendation | Notes |
|------|----------|----------------|-------|
| 1 | **Project root** (`skills-guide.yaml`) | Best for most people | Simple and highly discoverable |
| 2 | **`.skills/skills-guide.yaml`** inside the project | Excellent | Cleaner project structure |
| 3 | Global location (e.g. `~/.skills/skills-guide.yaml`) | Only if all projects share the same rules | Less flexible |

**Strong recommendation**: Keep `skills-guide.yaml` inside the **project folder** (or in a `.skills/` subfolder). This allows different projects to have different skill usage rules and makes it easy to version-control the guide with your code.

When you run `skills-auditor guide`, it will create the file in the current working directory by default. You can then move it into a `.skills/` folder if preferred.

---

### Recommended Workflow

Use this skill in combination with `skill-selector`

1. **Initial Setup**
   - Run `skills-auditor guide` to create your `skills-guide.yaml` (preferably in the project root or `.skills/` folder)

2. **Daily / Regular Use**
   - Use `skill-selector guide <prompt>` as your primary tool for breaking down requests

3. **When You Install New Skills**
   - Run `skills-auditor update` to add them to the guide

4. **Periodically, or When Something Feels Off**
   - Run `skills-auditor validate` to catch drift, routing violations, and stale references before they cause a bad assignment

## Summary

| Skill              | Primary Responsibility                              | Recommended Usage Frequency |
|--------------------|-------------------------------------------------------|-----------------------------|
| `skills-auditor`   | Create, maintain, and validate `skills-guide.yaml`     | Occasional (setup + updates + periodic validation) |
| `skill-selector`   | Decompose prompts + assign skills                      | Frequent (daily work)       |

**Best Practice**: Treat `skills-auditor` as your **knowledge base manager** — including its own QA via `validate` — and `skill-selector` as your **main working tool** for prompt decomposition and skill assignment.
