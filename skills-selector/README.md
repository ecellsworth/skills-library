# skill-selector

**The primary skill for breaking down prompts into tasks and assigning the best skills.**

> Note: this skill's `name:` is `skill-selector`, but it lives in the `skills-selector/` folder (extra "s") — don't rename the folder, `skills-auditor`'s handoff and both SKILL.md files reference these exact paths.

## Purpose

`skill-selector` is the recommended tool for turning a user request into a clear, ordered set of tasks with the most appropriate skills assigned to each task.

It supports two modes:
- **Guide Mode**: Uses your `skills-guide.yaml` as the source of truth for consistent, documented decisions.
- **Library Mode**: Reasons over all installed skills when you want speed or don't have a guide yet.

## When to Use

| Situation                              | Recommended Mode     | Why |
|----------------------------------------|-----------------------|-----|
| You have a `skills-guide.yaml`         | Guide Mode           | Highest consistency with your documented rules |
| Important or complex projects          | Guide Mode           | Best long-term consistency |
| Quick daily prompts                    | Guide Mode (if guide exists) or Library Mode | Good balance of speed and quality |
| You don't have a guide yet             | Library Mode         | Works immediately |
| You want maximum speed                 | Library Mode         | No need to consult the guide |

## How to Use

### Guide Mode - References a `skills-guide.yaml` file within your local directory

```text
skill-selector guide <your prompt>
```

Example:
```text
skill-selector guide Build a modern SaaS dashboard with charts and user settings
```

> **Important**: You must place a `skills-guide.yaml` file in the project folder (or current working directory) before running Guide Mode.
> If you don't have one yet, first run `skills-auditor guide` to create it.

### Library Mode - Scans your agent's skill library

```text
skill-selector <your prompt>
```

Example:
```text
skill-selector Create a landing page with smooth animations
```

## Bundled Script: `scripts/query_guide.py`

Guide Mode never reads the full `skills-guide.yaml` when this script is available — a mature guide can run well over 1,000 lines, and most prompts only touch one or two categories. Instead it queries exactly the slice it needs:

```bash
python3 skills-selector/scripts/query_guide.py --guide skills-guide.yaml meta
python3 skills-selector/scripts/query_guide.py --guide skills-guide.yaml manifest
python3 skills-selector/scripts/query_guide.py --guide skills-guide.yaml categories
python3 skills-selector/scripts/query_guide.py --guide skills-guide.yaml match marketing seo
python3 skills-selector/scripts/query_guide.py --guide skills-guide.yaml skill pptx
```

| Command | Returns |
|---|---|
| `meta` | `generated`, `updated`, `skills_indexed`, `conflict_policy`, `needs_review` — always cheap to fetch first |
| `manifest` | The sorted list of every indexed skill name, for the staleness guard |
| `categories` | Category names + descriptions only (no tasks/skills) — for a quick map of the guide |
| `match KEYWORD...` | The full subtree of every category task whose category/task/skill name or `when_to_use` text matches any keyword, plus matching `universal_skills`, plus any `cross_category_conflicts` / `needs_review` items touching those skills, plus `conflict_policy` and `meta` — one call is enough for most prompts |
| `skill NAME` | Every routing, conflict, `never_use`, and `needs_review` entry that mentions this exact skill name — useful once a candidate skill is already known |

`match` with no hits returns `{"matches": []}` (exit 0) rather than an error — the selector should fall back to `categories` plus a second, broader `match` call. The script works against both the new schema and legacy guides (missing sections simply come back empty) and never makes classification judgments — it only slices and returns what's already in the file.

If `query_guide.py` is missing or fails, the skill falls back to reading the full file and notes the fallback in its output.

## Output

`skill-selector` produces a structured task plan with:
- Ordered tasks
- Clear purpose and expected outputs for each task
- Specific skills assigned (or "none" with a reason)
- Justifications for assignments, each conflict resolution citing the Conflict Policy rung that decided it
- A **Staleness warning** when an assigned skill is no longer installed, or an installed skill relevant to the prompt is missing from the guide
- Notes on conflicts resolved and gaps
- A **Guide Update Suggestions** block (when relevant) formatted for direct hand-off to `/skills-auditor update`

## Where Should `skills-guide.yaml` Live?

Both `skill-selector` and `skills-auditor` look for the guide in this order:

1. Current working directory
2. Project root

### Recommended Locations

| Rank | Location | Recommendation | Notes |
|------|----------|----------------|-------|
| 1 | **Project root** (`skills-guide.yaml`) | Best for most people | Simple and highly discoverable |
| 2 | **`.skills/skills-guide.yaml`** inside the project | Excellent | Cleaner project structure |
| 3 | Global location (e.g. `~/.skills/skills-guide.yaml`) | Only if all projects share the same rules | Less flexible |

**Strong recommendation**: Keep `skills-guide.yaml` inside the **project folder** (or in a `.skills/` subfolder). This allows different projects to have different skill usage rules and makes it easy to version-control the guide with your code.

---

Use skills-auditor to create a `skills-guide.yaml` file to maintain locally to prevent the agent from parsing your entire library and eating tokens.

## How to Use with skills-auditor

| Workflow Step                    | Tool                    | Purpose |
|----------------------------------|--------------------------|--------|
| 1. Create your skill knowledge base | `skills-auditor guide`     | Build `skills-guide.yaml` once |
| 2. Keep the guide up to date     | `skills-auditor update`    | Add newly installed skills |
| 3. Check the guide is still accurate | `skills-auditor validate` | Catch drift, routing violations, stale references |
| 4. Decompose prompts + assign skills | `skill-selector guide` | Primary tool (uses the guide, via `query_guide.py`) |
| 5. Quick work without the guide  | `skill-selector`           | Fast Library Mode |

**Recommended daily practice:**
- Use `skill-selector guide` as your main tool for breaking down prompts.
- Only use `skills-auditor` when you need to create, update, or validate `skills-guide.yaml`.

---

**Best Practice**: After setting up your guide with `skills-auditor`, primarily use `skill-selector` (in Guide Mode) for prompt decomposition and skill assignment.
