---
name: skill-selector
description: The primary skill for breaking down a user prompt into ordered tasks and assigning the most appropriate skills. Supports two modes: "skill-selector guide (prompt)" uses skills-guide.yaml as the primary source of truth for consistent, documented assignments. "skill-selector (prompt)" uses the full skill library with strong on-the-fly reasoning. Automatically detects skills-guide.yaml when present.
---

# Skill Selector (YAML Edition)

You are the **primary tool** for decomposing complex requests into clear, ordered tasks and assigning the best skills to each task.

This skill supports two operating modes:

- **Guide Mode** (`skill-selector guide (prompt)`): Uses an existing `skills-guide.yaml` as the primary source of truth.
- **Library Mode** (`skill-selector (prompt)`): Reasons over the full set of installed skills with strong structured evaluation.

## Mode Detection

- **Guide Mode** if the user explicitly says "guide", **or** if `skills-guide.yaml` exists in the current working directory or project root.
- **Library Mode** otherwise.

If Guide Mode is requested but no guide exists, warn the user and fall back to Library Mode (or suggest running `skills-auditor guide`).

## Token-Efficient Guide Reading

Never read the entire `skills-guide.yaml` when `scripts/query_guide.py` (in this skill's directory) is available. Query it for: the `manifest`, `conflict_policy`, `needs_review`, and only the category subtrees matching the prompt's keywords. Fall back to reading the full file only if the script is missing or fails, and note the fallback.

---

## Core Principles (apply to both modes)

**Purpose, not proximity.** Only assign a skill when it has a clear, specific reason to improve the outcome of that exact task.

**Skills are optional.** It is valid and often preferable to assign no skill to a task. In such cases, strengthen the task instructions instead.

**Minimalism.** Prefer the smallest number of high-quality assignments over many overlapping ones.

**Scoped application.** Skills must be attached to specific tasks. Never apply skills broadly across an entire prompt unless the skill is explicitly designed as whole-project.

**Conflict awareness.** When two skills perform similar work differently, choose only the single best one using the Conflict Policy below.

## Conflict Policy (shared with skills-auditor)

In Guide Mode, read the ladder from the guide's `conflict_policy:` block. If the guide predates that block, or in Library Mode, use this identical fallback. Apply rungs in order; stop at the first that decides:

1. **Explicit user preference** (in the prompt, or recorded in the guide).
2. **Documented conflict resolution** in the guide (task-level `conflicts` or `cross_category_conflicts`).
3. **Tighter category match** — a category-bound skill beats a universal skill for tasks inside its category.
4. **Tighter task match** — the skill whose trigger description names this task most specifically wins.
5. **Narrower scope wins** — the skill with the more constrained trigger description wins over the broader one.
6. **Still tied** — assign neither automatically; note the tie in the output, pick the safer/narrower option only if the task cannot proceed without a skill, and emit a Guide Update Suggestion so the auditor can record a resolution.

Never decide on subjective grounds like "more capable." Never silently resolve a conflict the guide is silent on — always disclose which rung decided it.

---

## Guide Mode Procedure (Recommended when skills-guide.yaml exists)

1. **Locate and read the guide (query, don't slurp)**
   - Find `skills-guide.yaml` in current directory → project root.
   - Via `scripts/query_guide.py` (or fallback full read), load `manifest`, `conflict_policy`, `needs_review`, and the relevant category/task subtrees.

2. **Staleness guard (mandatory, before any assignment)**
   - Spot-check that every skill you are about to assign is actually installed. Never assign a skill that is in the guide but no longer installed — note it as drift instead.
   - Check for installed skills relevant to the prompt that are absent from the `manifest` (new installs the guide doesn't know about). Treat these as Library-Mode candidates, marked `Source: Reasoning (unindexed)`.
   - If either form of drift is found, or the guide's `generated`/`updated` date is clearly older than recent skill installs, add a **Staleness warning** to the output and recommend `/skills-auditor update` (or `validate`).

3. **Check `needs_review`**
   - If any open item involves a skill or conflict pair relevant to this prompt, warn the user in the output and proceed using the Conflict Policy.

4. **Decompose the prompt**
   - Break the request into a small number of ordered, atomic tasks.
   - For each task clearly define: name, purpose, inputs, expected outputs, dependencies, and stage.

5. **Capability-aware skill assignment (using the guide)**
   - For each task, first consult the relevant category and task entry in the guide.
   - Respect **scope rules** strictly (never assign a category-bound skill outside its documented categories).
   - **Multi-routed skills**: when a skill appears in multiple places in the guide, use the routing whose category matches this task's context, and follow that entry's `when_to_use`/`never_use_when` and `routing_note`.
   - Resolve overlaps with the **Conflict Policy** (documented resolutions are rung 2 and take precedence over your own reasoning).
   - Only fall back to general reasoning for tasks or skills not covered in the guide, and mark those assignments as such.

6. **Handle gaps responsibly**
   - If no suitable skill exists in the guide for a task:
     - Clearly note the gap.
     - Optionally suggest searching external skill sources.
     - Never auto-install third-party skills.
     - Strengthen the task instructions so the agent can still perform well unaided.

7. **Output with transparency and feedback**
   - Use the standard output format.
   - Clearly mark which assignments came from the guide vs. additional reasoning.
   - Include notes on any conflicts resolved (and which policy rung decided each) or gaps identified.
   - End with a **Guide Update Suggestions** block (see Output Format) whenever this run produced knowledge the guide lacks: unindexed skills used, undocumented conflicts resolved, gaps found, or drift detected. This block is formatted for direct hand-off to `/skills-auditor update`.

---

## Library Mode Procedure (Full skill library reasoning)

1. **Decompose the prompt**
   - Create ordered, atomic tasks with purpose, inputs, expected outputs, dependencies, and stage.

2. **Structured per-task evaluation**
   For each task, evaluate candidate skills using these criteria (in priority order):

   - **Outcome Alignment** — How directly does the skill support the specific expected result of this task?
   - **Specific Purpose Match** — Does the skill have a non-generic, clear reason to be used for this exact task?
   - **Stage Fit** — Is the skill appropriate for this stage of work?
   - **Uniqueness / Non-Duplication** — Does it avoid performing work already assigned to another skill?
   - **Gap-Filling** — Does it cover something other selected skills do not?
   - **Minimalism** — Prefer the smallest effective set of skills.

3. **Make justified assignments**
   - Select the single best skill (or minimal complementary set) per task, resolving overlaps with the Conflict Policy (rungs 3–6, since no guide is available).
   - Explicitly justify the choice, especially when similar skills exist.
   - Reject any skill that lacks a strong, specific purpose for the task.

4. **Output**
   - Use the same structured format as Guide Mode (without "Source: Guide" markers).
   - If the session would benefit from a persistent guide (repeated conflicts, large library), suggest running `/skills-auditor guide`.

---

## Output Format (both modes)

```markdown
# Task Plan: short descriptive title

**Mode**: Guide Mode | Library Mode
**Guide used**: (path or "None")
**Staleness warning**: (none | description of drift + recommendation)
**Open needs_review items relevant to this prompt**: (none | list)

## Task 1: (Task Name)
**Purpose**: ...
**Expected Output**: ...
**Dependencies**: ...
**Stage**: ...
**Skills**: skill-name (or "none — reason")
**Justification**: ...
**Source**: Guide | Reasoning | Reasoning (unindexed)   (Guide Mode only)

## Task 2: ...

## Summary
- Total tasks: X
- Skills assigned: Y
- Tasks with no skill: Z
- Conflicts resolved: pair → chosen skill (policy rung N)
- Gaps identified: ...
- Notes: ...

## Guide Update Suggestions   (omit only if empty)
Hand this block to /skills-auditor update to keep the guide current.
- kind: unindexed_skill | undocumented_conflict | gap | drift | stale_entry
  detail: ...
  skills: [ ... ]
  suggested_resolution: ...
```

---

## Final Validation Checklist

- [ ] Every task has a clear purpose and measurable expected output.
- [ ] Skills are only assigned when they have a specific, justified purpose for that task.
- [ ] Every assigned skill was verified as actually installed (Guide Mode staleness guard).
- [ ] No two conflicting skills are assigned to the same task; each resolution cites its policy rung.
- [ ] Category-bound skills respect documented scope (Guide Mode).
- [ ] Multi-routed skills were resolved to the routing matching the task's category.
- [ ] The plan follows minimalism principles.
- [ ] Output is directly usable by another agent.
- [ ] Gaps, conflicts, drift, and relevant needs_review items are clearly noted.
- [ ] Guide Update Suggestions block emitted if this run produced knowledge the guide lacks.

---

## Anti-Patterns to Avoid

- Do not apply skills broadly to the entire prompt.
- Do not assign a skill just because it is related to the topic.
- Do not ignore clear guidance in `skills-guide.yaml` without strong justification (Guide Mode).
- Do not assign a skill from the guide without confirming it is still installed.
- Do not read the full skills-guide.yaml when query_guide.py is available.
- Do not resolve conflicts on subjective grounds ("more capable") or without citing a policy rung.
- Do not auto-install external skills when gaps are found.
- Do not let reasoning-derived decisions evaporate — emit them as Guide Update Suggestions.
