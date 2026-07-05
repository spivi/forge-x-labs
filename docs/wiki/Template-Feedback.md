# Template Feedback for Owner

Feedback on the base agentic dev-template, gathered while adapting it into `cloudforge`.
Overall the template is **solid and the CI is thoughtfully template-aware** — the notes
below are cleanup-level, not blocking. **Nothing here blocked the MVP.**

## What was rough

### 1. `app/` is hard-wired; a `src/` layout fights the template
**Rough:** CI (`--cov=app`, `mypy app/`), the coverage gate, and the console-script
contract (`{{PROJECT_NAME}} = "app.cli:app"`) all assume a top-level `app/` package. A
project spec that wants `src/<pkg>/` conflicts in ~4 places.
**Impact:** Had to reconcile the product's suggested `src/cloudforge/` against the template
and settle on `app/cloudforge/` (decision FXL-D001) to keep CI edit-free.
**Suggestion:** Document the `app/`-layout assumption prominently (README + CLAUDE.md), or
parameterize the package path in one place that CI/mypy/coverage read.
**Severity:** cleanup.

### 2. 55 files ship un-substituted `{{PLACEHOLDER}}` tokens
**Rough:** Identity tokens (`{{PROJECT_NAME}}`, `{{PROJECT_ID}}`, `{{TICKET_PREFIX}}`,
`{{SETUP_DATE}}`, author) are coherent only after `setup.sh` runs interactively. Some tokens
are *literal documentation examples* (e.g. "use `{{TICKET_PREFIX}}-NNN`") mixed in with real
identity tokens, so a blanket substitution is unsafe.
**Impact:** For agent-driven adaptation I substituted only the identity-critical files by
hand and left `setup.sh`/`ci.yml`/skill-prose tokens alone.
**Suggestion:** A non-interactive `setup.sh --defaults name=… id=… prefix=…` mode, and a
clear separation between "identity tokens" and "documentation examples."
**Severity:** cleanup.

### 3. The agentic scaffolding vastly outweighs an empty product
**Rough:** 19 skills, 9 agent defs, ~35 scripts, a full `lemmings/` pipeline simulator, and
KPI ledgers ship on top of a 0-byte `app/__init__.py`. It is easy for the scaffolding to
dominate a new product's mental model.
**Impact:** Deliberately kept the scaffolding **inert** and focused on the product slice.
**Suggestion:** Offer a "lite" profile (or a documented "leave inert until you need it"
posture) so new projects aren't pressured to wire up the whole autonomous pipeline on day
one.
**Severity:** cleanup.

### 4. Local Python 3.14 vs. project `^3.12` / mypy `python_version = 3.12`
**Rough:** The default interpreter here is 3.14, but the project pins `^3.12` and mypy
targets 3.12 — a strict typecheck can surface 3.14-only differences.
**Impact:** Created the venv explicitly on 3.12 (`poetry env use 3.12`).
**Suggestion:** Have `setup.sh` (and the README quickstart) pin the venv to the mypy target
version, and note it.
**Severity:** cleanup.

### 5. Ruff `TCH`/`TC` conflicts with Pydantic v2 runtime annotations
**Rough:** The default ruff `select` includes `TCH`, which pushes type-only imports into
`if TYPE_CHECKING:` blocks. For a Pydantic-heavy codebase this is actively wrong —
`model_validate` needs field-type imports importable at runtime, so the guarded imports
would break validation.
**Impact:** Dropped `TCH` from `select` with an explanatory comment.
**Suggestion:** Drop `TCH` from the default `select`, or ship a documented note that
Pydantic projects should remove it.
**Severity:** cleanup.

## What was good (explicitly)

- **CI is template-aware** — it detects un-substituted `{{` tokens and runs only
  placeholder-safe gates until `setup.sh` fills them. This let the repo stay green during
  adaptation. Nice touch.
- **`flavors/cli/`** already encodes the exact Typer + Rich + `[tool.poetry.scripts]`
  convention this project needed — a clean reference.
- **Rules** (`general.md`, `python.md`, `testing.md`) are concrete and portable; the
  30-line/200-line/3-param limits and Mandrake testing translated directly to the product.
- **`.gitignore`, pre-commit, sign-off hook, and the KPI/ledger seams** are coherent and
  didn't get in the way.

## Bottom line

Blocking issues: **none.** All feedback is cleanup/ergonomics. The biggest single win would
be documenting the `app/`-layout assumption and adding a non-interactive `setup.sh` mode so
agent-driven adaptation doesn't have to hand-substitute placeholders.
