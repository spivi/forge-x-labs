# Review Pack Template

One scenario, one sheet. Two halves: a **reviewer view** (ground truth hidden)
and a **reveal** (the answer key). Score the top half blind, then scroll to
the reveal. Target: under 20 minutes.

Every field comes from real generated artifacts. Nothing is invented.

| Sheet field | Source artifact |
|-------------|-----------------|
| Summary | `report.md` Summary |
| Generated resources | `report.md` / `graph.json` nodes |
| Risk narrative | `report.md` framing (paraphrased so it does not leak the edge list) |
| Findings (reviewer view) | family + severity + resources only |
| Reveal: critical path | `ground_truth_paths.json` |
| Reveal: expected findings + why | full `expected_findings.json` |
| Reveal: remediation order | `report.md` |
| Reveal: decoy note | mutated variant vs base |

See [`review-pack-sample/`](review-pack-sample/) for 10 filled-in sheets.

## Template (copy per scenario)

```markdown
# Review Sheet: <scenario_id>

## Reviewer view: score this half BLIND

**Scenario:** <family> / <cloud> / <environment> / <company profile / app>
**Size:** <N resources>, <M edges>

**Generated resources**
<one line per resource: `id` - Type name (sensitivity)>

**Risk narrative (as an analyst would read it)**
<2-4 sentences. Do not name the exact critical-path edge list.>

**Findings surfaced (family, severity, resources, expected scanner visibility)**
<one line per finding. Withhold the "why" and remediation until reveal.>

**Blind scoring** (see rubric anchors)
- Realism [1-5]: ___    Clarity [1-5]: ___    Training [1-5]: ___
- Scanner-benchmark [1-5]: ___    Ground-truth trust [1-5]: ___

**Open questions**
- Real SaaS/cloud env? ___
- Risk chain plausible? ___
- Findings too toy-like? ___
- Remediation order correct? ___
- Benchmark a scanner? ___   Train an analyst? ___
- What is missing? ___

---

## Reveal: read only AFTER scoring the reviewer view

**Ground-truth critical path** (<severity>)
<node -> node -> node>
<the explanation string>

**Expected findings and why**
<one line per finding: severity, family, rationale, remediation>

**Remediation order (highest risk first)**
<numbered list from report.md>

**Decoy / mutation note** (mutated variants only)
<which resource is a benign distractor; confirm the critical path is
byte-identical to the base>

**Coherence check**
- Did the reveal match your blind read?  y / n  why: ___
```

## Format rules

- One page. Trim the resource list to the ones that carry the risk plus
  enough context to be realistic.
- Ground truth stays below the divider.
- Findings are teasers above, full below.
- Bullets and short lines. No long paragraphs.
