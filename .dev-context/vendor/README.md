# Vendored third-party components

Owned local clones of external tools we run via `--plugin-dir` and customize in place.
Each is pinned to a known-good upstream commit; upstream drift is a deliberate `git pull`,
never a surprise.

## claude-council

- **Upstream:** https://github.com/hex/claude-council (MIT)
- **Pinned commit:** `63a0568ec03bb91f7d628b55ed46ec3eeaa19d94` (tag `v2026.6.9`)
- **Cloned:** 2026-07-02
- **Why vendored:** the plugin has **no config override** — `config/roles.json` and
  `prompts/synthesis.md` are only editable in place. We run our customized copy via
  `claude --plugin-dir .dev-context/vendor/claude-council` (do NOT clone into
  `~/.claude/plugins/`, which is a managed cache).

### Our edits (the ONLY files we modify — keep diffs small so upstream stays mergeable)
- `config/roles.json` — added the `correctness-falsifiability` and `coherence-scope`
  member roles + the `doc-review` preset (used for plan/EVR/summary review).
- `prompts/synthesis.md` — the chair synthesizes through the **Architectural
  Methodologist** persona, appends a mandatory non-approval line, and emits a
  machine-readable ```council-autofix``` block listing ONLY blocker fixes (read by the
  wrapper's optional auto-draft step; see `COUNCIL_AUTOFIX`).

Everything else is upstream-as-is. To update: `git fetch && git checkout <new-tag>`,
re-apply the two edits above (they are additive/low-conflict), and bump the pin here.

### How it is invoked
Not directly — through `.dev-context/council.env` + `scripts/council-review.sh`
(the single place the model/cost policy lives) and the `council-on-doc-write.sh` hook.
Members = `codex` + `antigravity` (both keyless CLI subscription auth — no API keys);
chair = Claude (Sonnet; Opus gated). See the project plan.

> The second member was switched from the plugin's `gemini` REST provider (which needs
> `GEMINI_API_KEY`) to `antigravity` (Google's `agy` CLI, keyless) because the gemini
> CLI's individual keyless tier was discontinued. In the plugin's shadow-pair policy,
> `antigravity` is the CLI shadow of `gemini`, so `--providers=codex,antigravity` is the
> supported keyless roster. Requires the `agy` binary (`brew install --cask antigravity-cli`).

> Nested-repo note: this clone keeps its own `.git`. It is git-ignored by the parent
> `dev-template` repo (see `.gitignore`) and reconstructed from the pin above via the
> bootstrap step — it is intentionally NOT committed as content into dev-template.
