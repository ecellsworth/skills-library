---
name: skills-auditor
description: Create, maintain, and validate a skills-guide.yaml knowledge base that maps installed skills to categories and tasks. Use when the user invokes /skills-auditor guide, /skills-auditor update, or /skills-auditor validate, asks to generate, update, check, or repair a skills guide, wants to add newly installed skills to the guide, or needs a structured reference for skill routing. Also trigger on phrases like "audit my skills", "create skills guide", "update skills guide", or "validate skills guide".
---

# Skills Auditor

This skill creates and maintains a structured **`skills-guide.yaml`** file — the single source of truth that documents how installed skills should be used.

`skills-auditor` focuses on **knowledge management**. The recommended tool for breaking down prompts and assigning skills is **`skill-selector`** (especially in Guide Mode).

This skill has three functions:
- `guide` — Generate `skills-guide.yaml` from scratch
- `update` — Incrementally add newly installed skills to an existing guide
- `validate` — Check the guide against the installed library and the schema; repair with user approval

Never run one when another was requested.

## Bundled Scripts (use when present)

Mechanical work must be done by the scripts in this skill's `scripts/` directory, not by re-emitting YAML from the model. If a script is missing or fails, fall back to doing that step manually and note the fallback in the run summary.

| Script | Used by | Purpose |
|---|---|---|
| `scripts/inventory.py` | guide, update, validate | Scan installed skills; emit name + description (+ hash) as JSON. Avoids reading full SKILL.md bodies. |
| `scripts/build_guide.py` | guide | Assemble a complete skills-guide.yaml from per-skill JSON classification records. |
| `scripts/merge_guide.py` | update | Append new classification records into an existing guide; sort manifest; update counts/dates/hashes. |
| `scripts/validate_guide.py` | validate (and after every guide/update run) | Schema check, drift detection, duplicate/orphan detection. |

Token rule: the model's job is **classification judgment only** — emit compact per-skill JSON records and let scripts read/write the YAML. Never output the full guide file in a response. Only read a skill's full SKILL.md body when its frontmatter description is too ambiguous to classify.

## Core Principles

**Purpose, not proximity.** A skill is recorded for a task only when it is required for that specific task and will improve the result.

**Scope: universal vs. category-bound.** Every skill is one of:
- *Universal* — applicable to any project category (planning, documentation, review, etc.)
- *Category-bound* — designed for a specific domain and must never be used outside it. Tool-specific skills (e.g., a particular browser-automation or charting library) are category-bound to their tool's domain, not universal, even if the tool could be used in many projects.

**Multi-routing policy.** A skill MAY appear in more than one place when each routing independently satisfies "purpose, not proximity":
- Allowed: universal + category (only when the category entry adds task-specific guidance beyond the universal entry), or two categories (when the skill genuinely serves both domains).
- Forbidden: appearing in both a category and `unrouted`. `unrouted` is strictly for skills with no routing anywhere else.
- Every multi-routed skill must carry a `routing_note` on each entry explaining why that routing exists, so `skill-selector` can pick the routing whose category matches the task context.

**Conflicts.** When two skills perform the same task differently, record a clear resolution so that downstream tools (`skill-selector`) can choose consistently using the Conflict Policy below.

**Skills are optional.** Not every task needs a skill. It is valid to leave a task without an assigned skill.

## Conflict Policy (shared with skill-selector)

This ladder is written into the guide's top-level `conflict_policy:` block so both skills read the same rules. Apply rungs in order; stop at the first that decides:

1. **Explicit user preference** recorded in the guide.
2. **Documented conflict resolution** in the guide (task-level `conflicts` or `cross_category_conflicts`).
3. **Tighter category match** — a category-bound skill beats a universal skill for tasks inside its category.
4. **Tighter task match** — the skill whose trigger description names this task most specifically wins.
5. **Narrower scope wins** — the skill with the more constrained trigger description (fewer domains, more preconditions) wins over the broader one.
6. **Still tied** — assign neither automatically. Record the pair under `needs_review` with status `needs_user_decision` and ask the user.

Never use subjective criteria such as "more capable" or "better" — every rung above is decidable from the skill descriptions and the guide.

## Classification Procedure

For every skill, follow these two phases:

### Phase 1: Capability Extraction
Extract:
- Primary actions/verbs (3–6 specific verbs)
- Typical inputs
- Typical outputs
- Strong domain signals or assumptions
- Explicit "never" or constraint statements

### Phase 2: Mapping
Determine:
- **Scope**: Universal or Category-bound (list categories)
- **Recommended tasks**: Specific and concrete
- **Never use for**: Specific plausible misuse cases
- **Conflicts**: Other skills that overlap and how to choose between them

Be conservative. Do not list a skill for a task if the relationship is only tangential.

### Phase 3: Active Conflict Detection (mandatory)

Conflicts must be found systematically, not just when noticed:

1. Within every task entry, compare each pair of assigned skills' primary verbs (from Phase 1).
2. If a pair shares 2+ primary verbs or the same input→output shape, you MUST record either:
   - a `conflicts` entry with a resolution decided by the Conflict Policy, or
   - an explicit `complementary: true` note stating how the two divide the work.
3. If a detected overlap crosses category boundaries, record it in the top-level `cross_category_conflicts:` section — never arbitrarily inside one category.
4. Any overlap the policy cannot decide goes to `needs_review` as `needs_user_decision`.

## Few-Shot Classification Examples

**Example 1: `impeccable`**
- Capabilities: Refines UI micro-interactions, improves polish and delight
- Scope: Category-bound (Web UI / Frontend Development)
- Recommended tasks: Polishing production UI components, adding micro-interactions
- Never use for: Backend logic, content writing, data analysis
- Conflicts: Prefer `impeccable` over `frontend-design` when polish and micro-interactions matter more than initial structure

**Example 2: `brainstorming`**
- Capabilities: Explores ideas, generates options, helps define goals
- Scope: Universal
- Recommended tasks: Early project discovery, breaking down ambiguous requests
- Never use for: Final implementation or code writing
- Conflicts: None

**Example 3: `debug`**
- Capabilities: Reproduces bugs, isolates root causes, proposes fixes
- Scope: Category-bound (Code Quality / Software Development)
- Recommended tasks: Troubleshooting runtime errors, fixing failing tests
- Never use for: UI design, documentation writing, project planning
- Conflicts: Prefer over general code review skills when the goal is diagnosis

---

## Function 1: `/skills-auditor guide`

Generate a new `skills-guide.yaml` in the current working directory (or project root).

Run only when the user explicitly invokes it. If a `skills-guide.yaml` already exists, ask before overwriting.

### Procedure

1. **Inventory** via `scripts/inventory.py` (fallback: list installed skills and read frontmatter only). The inventory — not memory, not a partial listing — defines the complete set to index.
2. **Classify** every skill using the Classification Procedure (Phases 1–3), emitting one compact JSON record per skill.
3. **Build** the file via `scripts/build_guide.py` from the records (fallback: write the YAML manually following the schema).
4. **Validate** immediately via `scripts/validate_guide.py`. Fix any structural findings before presenting.
5. **Report** per the Reporting Rules below: total skills, categories, conflict clusters, and every `needs_review` item.

### skills-guide.yaml Schema

```yaml
# Skills Guide
# Single source of truth used by skill-selector and skills-auditor.
# Generated by skills-auditor. Edit via /skills-auditor update or validate.

generated: YYYY-MM-DD
updated: null
skills_indexed: 0

conflict_policy:
  # Decidable tie-breaker ladder shared by skills-auditor and skill-selector.
  # Apply in order; stop at the first rung that decides.
  - explicit user preference recorded in this guide
  - documented conflict resolution (task-level or cross_category_conflicts)
  - tighter category match (category-bound beats universal inside its category)
  - tighter task match (description names the task most specifically)
  - narrower scope wins (more constrained trigger description)
  - still tied -> assign neither; record under needs_review as needs_user_decision

manifest:
  - skill-name-1
  - skill-name-2
  # alphabetical list of every skill indexed

hashes:
  # skill-name: first 12 hex chars of sha256 of the skill's frontmatter description,
  # written at index time. Maintained by scripts; used by validate to detect
  # skills whose descriptions changed after indexing.
  skill-name-1: a1b2c3d4e5f6

universal_skills:
  - name: brainstorming
    purpose: Early project discovery and idea exploration
    tasks:
      - Breaking down ambiguous requests
      - Generating alternatives
    whole_project: false
    never_use_for:
      - Final implementation
      - Code writing

categories:
  - name: Web UI / Frontend Development
    description: Projects involving user interfaces, components, and frontend experiences
    tasks:
      - name: Visual design direction
        skills:
          - name: frontend-design
            when_to_use: Initial structure, layout systems, component hierarchy
            never_use_when: When heavy polish or motion is the priority
          - name: impeccable
            when_to_use: Adding polish, micro-interactions, and delight
            never_use_when: Early structural decisions
            routing_note: null  # required when the skill is routed in more than one place
        conflicts:
          - between: [frontend-design, impeccable]
            resolution: Use frontend-design first for structure, then impeccable for polish

cross_category_conflicts:
  # Home for overlaps spanning two categories — never file these inside one category.
  - between: [pptx, frontend-slides]
    categories: [Document Generation, Visual & UI Design]
    resolution: pptx when a literal .pptx file is the deliverable; frontend-slides for HTML presentations

never_use:
  - skill: debug
    never_apply_to:
      - UI design
      - Documentation writing
    reason: Domain mismatch

unrouted:
  # ONLY skills that appear nowhere else. A skill may never be both routed and unrouted.
  - name: example-skill
    reason: Unclear domain fit

needs_review:
  # Open items requiring user judgment. skill-selector warns about relevant open items.
  # Cleared only by an explicit user decision (recorded via update/validate).
  - kind: needs_user_decision | drift | ambiguous_classification | stale_entry
    detail: Description of the open question
    skills: [skill-a, skill-b]
    raised: YYYY-MM-DD
```

Every installed skill must appear in the manifest, in `hashes`, and in at least one of Universal, a Category, or Unrouted.

---

## Function 2: `/skills-auditor update`

Incrementally add newly installed skills to an existing `skills-guide.yaml`. This is the primary ongoing command after the initial `guide` run.

### Procedure

1. Locate `skills-guide.yaml` (current directory → project root). If none exists, tell the user to run `/skills-auditor guide` first.
2. Run `scripts/inventory.py` and diff against `manifest` (fallback: manual diff). This catches new skills; report — but do not remove — any manifest entries that are no longer installed (removal belongs to `validate`).
3. **Ingest selector feedback**: if the user supplies a "Guide Update Suggestions" block produced by `skill-selector`, treat each suggestion as a proposed change alongside the new skills.
4. Classify only the new skills using the Classification Procedure (Phases 1–3), including conflict checks against already-indexed skills in the same tasks.
5. **Show Proposed Changes** and ask for confirmation before writing.
6. Merge via `scripts/merge_guide.py` (fallback: manual append):
   - Add new skills to the appropriate sections with bidirectional conflict notes.
   - Append names to `manifest` (alphabetical) and hashes to `hashes`.
   - Update `updated` and `skills_indexed`.
7. Run `scripts/validate_guide.py` and present a summary of what was added plus any findings.

**Hard rules for update:**
- Never modify or rewrite entries for skills already in the Manifest, except: (a) adding a bidirectional conflict note to an existing entry when a new skill conflicts with it, and (b) applying a user-approved suggestion from a selector feedback block.
- Never regenerate the entire guide.
- Only append new information.

---

## Function 3: `/skills-auditor validate`

Check the guide against reality and the schema. This is the only function permitted to modify existing entries — and only with explicit user approval per change.

### Checks (run `scripts/validate_guide.py`; fallback: perform manually)

1. **Schema**: YAML parses; required top-level keys present; every routed skill entry has required fields.
2. **Drift — missing**: installed skills absent from `manifest` → propose running `update`.
3. **Drift — stale**: manifest entries no longer installed → propose removal (flagged, user-approved).
4. **Drift — changed**: current description hash ≠ stored hash → propose reclassification of that skill.
5. **Structure**: manifest sorted/deduped; `skills_indexed` matches; every manifest entry routed somewhere; every routed name in manifest.
6. **Routing rules**: no skill in both a category and `unrouted`; every multi-routed skill has `routing_note` on each entry.
7. **Conflicts**: every `conflicts`/`cross_category_conflicts` entry references skills that exist in the guide; no undecided overlaps missing from `needs_review`.

### Repair

- Present all findings grouped by check, with a proposed fix for each.
- Apply only user-approved fixes. Stale-entry removal and reclassification always require approval; purely mechanical fixes (sort order, counts) may be applied automatically and reported.
- Record anything the user defers under `needs_review`.

---

## Reporting Rules (all functions)

1. **Always** surface issues in the chat summary — never complete a run silently when findings exist.
2. **Persist open items** in the guide's `needs_review:` section, not in a separate document. This keeps issues machine-readable so `skill-selector` can warn about them at assignment time.
3. When a run produces findings, also write **`skills-guide-report.md`** next to the guide — overwritten every run so exactly one report exists, containing: run type, date, findings by check, actions taken, and open `needs_review` items. Do not create this file on clean runs; delete a stale one if the current run is clean.
4. Never name the report `readme.md` — it would collide with skill READMEs and go stale.

---

## Notes on the Audit Function

The original `audit` function is retired. For breaking down prompts and assigning skills, use **`skill-selector guide`** instead. It is the recommended primary tool for that workflow.
