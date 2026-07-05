# Review Pack Template

> The per-scenario **1-page** format used by the quality panel
> ([`review-rubric.md`](review-rubric.md)). One scenario = one sheet. The sheet has two
> halves: a **reviewer view** (what an analyst or scanner would see — ground truth *hidden*)
> and a **reveal** (the answer key). Score the top half blind, then scroll to the reveal.
> Target: a reviewer scores the whole sheet in **under 20 minutes**.

Every field on the sheet comes from a scenario's **real generated artifacts** — nothing is
invented:

| Sheet field | Source artifact |
|-------------|-----------------|
| Summary | `report.md` → *Summary* |
| Generated resources | `report.md` → *Generated Resources* / `graph.json` nodes |
| Risk narrative | `report.md` framing + the critical-path explanation (paraphrased so it doesn't leak the exact edge list) |
| Findings (reviewer view) | `expected_findings.json` — **family + severity + resources only**, with `ground_truth` and `remediation` withheld |
| Reveal: critical path | `ground_truth_paths.json` |
| Reveal: expected findings + why | `expected_findings.json` — full records |
| Reveal: remediation order | `report.md` → *Remediation Order* |
| Reveal: decoy note | diff of a mutated variant against its base (the benign extra node) |

See [`review-pack-sample/`](review-pack-sample/) for 10 filled-in sheets generated this way.

---

## Template (copy per scenario)

```markdown
# Review Sheet — <scenario_id>

## Reviewer view  — score this half BLIND (do not scroll to the reveal)

**Scenario:** <family> · <cloud> · <environment> · <company profile / app>
**Size:** <N resources>, <M edges>

**Generated resources**
<one line per resource: `id` — Type name (sensitivity)>

**Risk narrative (as an analyst would read it)**
<2–4 sentences: what this estate is, where the risk appears to be — WITHOUT naming the
exact critical-path edge list or the answer key.>

**Findings surfaced (family · severity · resources) — expected scanner visibility**
<one line per finding: severity · family · (resource ids) · visibility>
<NB: the "why" and the remediation text are withheld until the reveal.>

**Blind scoring** (see rubric anchors)
- Realism [1–5]: ___    Clarity [1–5]: ___    Training [1–5]: ___
- Scanner-benchmark [1–5]: ___    Ground-truth trust [1–5]: ___

**Open questions**
- Real SaaS/cloud env? ___
- Risk chain plausible? ___
- Findings too toy-like? ___
- Remediation order correct? ___
- Benchmark a scanner? ___   Train an analyst? ___
- What is missing? ___

---

## Reveal  — read only AFTER scoring the reviewer view

**Ground-truth critical path** (<severity>)
<node → node → node chain from ground_truth_paths.json>
<the explanation string>

**Expected findings — and why**
<one line per finding: severity · family — ground_truth rationale → remediation>

**Remediation order (highest risk first)**
<numbered list from report.md>

**Decoy / mutation note** (mutated variants only)
<which resource is a benign distractor; confirmation the critical path is byte-identical to
the base scenario — i.e. the mutation preserved ground truth.>

**Coherence check**
- Was the scenario coherent (did the reveal match your blind read)?  y / n — why: ___
```

---

## Format rules that keep it under 20 minutes

- **One page.** If a sheet spills past a screen, trim the resource list to the ones that
  carry the risk plus enough context to be realistic — never pad.
- **Ground truth strictly below the divider.** The reviewer view must be scoreable with the
  reveal folded away. Do not leak the exact edge list or the finding rationales upward.
- **Findings are teasers above, full below.** Above the divider: severity + family +
  resources + visibility (what a scanner would emit). Below: the `ground_truth` "why" and
  the remediation. This is what makes the blind pass a real test.
- **Scannable, not prose-heavy.** Bullets and short lines. A reviewer skims resources, reads
  four sentences of narrative, and scores — no long paragraphs.
