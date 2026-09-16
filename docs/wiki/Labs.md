# Labs

`cloudforge lab` splits a generated scenario into a **student pack** (no
answer key) and an **instructor pack** (grade key). `cloudforge grade`
scores a guessed path as a subsequence of a ground-truth path's node
list. A wrong answer exits 0. A missing instructor key exits 1.

## Student pack

Under `DIR/student/`:

- `brief.md`: investigation prompt. Must not name `can_pass_role` or the
  critical-path node-id chain.
- `estate.json` / `estate.html`: resources and relationships. **No**
  `security` objects (no `criticality`, no edge `risk`).
- `terraform/`: never-applied HCL, same as the instructor tree.
- `scenario.yaml`: intent only.

Must **not** contain `expected_findings.json`, `ground_truth_paths.json`,
`report.md`, `grade_key.json`, or `graph.json`.

## Instructor pack

Under `DIR/instructor/`: full `graph.json`, findings, paths, `report.md`,
`grade_key.json`.

`grade` reads **only** `instructor/grade_key.json`. A student tree alone
cannot score itself.

## Cohort

`lab-cohort` maps each name in a text file to a stable seed (`adler32`,
not Python `hash()`), writes `out/<name>/`, and `roster.json`.
`grade-cohort` writes `results.md`.

## Workbench

`cloudforge challenge` writes a standalone `estate.html`. The in-browser
scorer uses the same path/finding math as `cloudforge grade`.

## Safety

Same as the rest of cloudforge: no AWS credentials, never `terraform apply`,
dummy account ids only. See [Safety and Scope](Safety-and-Scope.md).
