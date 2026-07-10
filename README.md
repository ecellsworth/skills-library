# skills-toolkit

Two Claude skills for building and using a `skills-guide.yaml` knowledge base of your installed skills:

- **`skills-auditor`** (`skills-auditor/`) — generates, updates, and validates `skills-guide.yaml`, a structured map of what each installed skill does and when to use it.
- **`skill-selector`** (`skills-selector/`) — breaks a prompt into tasks and assigns the best-fit skill to each one, using `skills-guide.yaml` as its source of truth when one exists.

They're designed to be used together, but each works standalone.

## Install

### Option 1: `npx skills` (works with Claude Code, Cursor, Codex, and other agents)

```bash
npx skills add ecellsworth/skills-library
```

This walks the repo for `SKILL.md` files and installs the ones you pick. No extra setup needed — it finds `skills-auditor/SKILL.md` and `skills-selector/SKILL.md` via its recursive fallback scan even though they aren't under a folder named `skills/`.

To install just one:

```bash
npx skills add ecellsworth/skills-library --skill skills-auditor
```

### Option 2: Claude Code's native plugin marketplace

```
/plugin marketplace add ecellsworth/skills-library
/plugin install skills-auditor@skills-toolkit
/plugin install skill-selector@skills-toolkit
```

This reads `.claude-plugin/marketplace.json` at the repo root, which points at the two skill folders directly.

## Usage

Once installed, invoke with:

```
/skills-auditor guide      # generate skills-guide.yaml from scratch
/skills-auditor update     # add newly installed skills to an existing guide
/skills-auditor validate   # check the guide against the installed library

/skill-selector guide (your prompt)   # route a prompt using skills-guide.yaml
/skill-selector (your prompt)         # route a prompt by reasoning over the full skill library
```

See each skill's own `README.md` for the full schema and bundled scripts.

## License

MIT.
