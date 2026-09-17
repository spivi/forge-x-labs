# Labs

`cloudforge lab` splits a generated scenario into a **student pack** (no
answer key) and an **instructor pack** (grade key). `cloudforge grade`
scores a guessed path against every labeled path. A wrong answer exits 0.
A missing instructor key exits 1.

## Grade rule

A labeled path is a hit when the guess names its entry (the first node),
its access-granting hop and its target (the sink), in that order; every
other path node is optional. The hop is the first identity after the entry,
or the exposed resource when the path has none (a public bucket, a shared
snapshot, a wildcard queue); on a two-node path the sink itself opens the
way. The grade also reports coverage, the path nodes the guess named over
the path length (`found 5 of 8`), and `full path yes` when every path node
was named in order. Guessed nodes on no labeled path are extras, as are
wrong finding families. The grade key records `hop`, `target` and
`sink_kind` per path; a key written before those fields existed grades with
the second node as the hop and the last as the target, which is where the
type-aware rule lands on every family. The workbench's in-browser evaluator
applies the same rule.

## Difficulty

`difficulty` used to set how many decoys and false positives sat around a
fixed path. It now shapes the path itself, drawn per `(spec, seed)` inside a
band. Easy is the family's direct chain and never branches. Medium draws 0 to
3 intermediate identity hops for an identity-chain family, may add an
identity route next to a resource-shaped family's public one (a second,
high-severity path to the same sink), and adds a dead-end branch from the
entry half the time. Hard draws 2 to 6 hops, always branches, and gives every
resource-shaped family a lookalike of its exposed resource that is blocked by
a control the student has to read. Counting cards tells the student nothing:
the same family is 6 nodes at one seed and 10 at another. The scale profile
still bounds the estate; a shape that does not fit is clamped and the clamp
is written into the instructor's `ground_truth_paths.json` notes and
`report.md`.

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

## Roundtable

`cloudforge roundtable` is a SOC tabletop pack. Default track
`identity_federation` rotates four families (Kubernetes IRSA, Azure
managed identity, GCP Workload Identity Pool, AWS GitHub Actions OIDC)
across the roster so the share-out is the same attack class on four
vendors.

Writes `facilitator.md` (90-minute agenda), `roster.json`, and one
student/instructor pack per name. Still never applied.

## Workbench

`cloudforge challenge` writes a standalone `estate.html`. The in-browser
scorer uses the same path/finding math as `cloudforge grade`.

## Safety

Same as the rest of cloudforge: no AWS credentials, never `terraform apply`,
dummy account ids only. See [Safety and Scope](Safety-and-Scope.md).
