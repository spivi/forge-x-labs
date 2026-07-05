# Scenario Quality Rubric

> **What this is for.** Tests prove a scenario is *engineering-valid* (schema-valid,
> graph-consistent, ground truth resolves — the machine-checkable half of the 12-point
> definition, [FXL-D003](../.dev-context/DECISIONS.md)). They cannot prove it is
> *product-valid*: realistic, useful for training and scanner benchmarking, and hard to
> fake. This rubric is the **human layer** — the check for "toy-scenario smell" that no
> assertion can catch. It is scored by a panel of reviewers, one scenario at a time, using
> the 1-page sheets in [`review-pack-template.md`](review-pack-template.md).

## Reviewer roles

Each scenario is scored **independently** by three reviewers, each reading from a different
lens. Do **not** confer before scoring — divergence between reviewers is signal, not noise.

| Role | Reads for |
|------|-----------|
| **Cloud-security engineer** | Would this configuration actually exist in a real SaaS/cloud estate? Is the risk chain something you'd fix in a real review? |
| **CSPM / detection engineer** | Would a scanner (checkov, Prowler, a CSPM) plausibly flag these findings? Is the visible/partial/hidden split honest? Is this useful as a benchmark case? |
| **Red-team / cloud-assessment** | Is the critical path exploitable end-to-end? Is the remediation order what an attacker would force you into? Are the false-positives convincing decoys? |

Panel size and convening the panel are a **human step outside the tooling** — this repo
ships the rubric, the template, and a sample pack; it does not simulate reviewers or invent
scores.

## The blind-then-reveal protocol

Score in two passes. The 1-page sheet is built for this — the ground truth is **hidden** in
the top half and **revealed** in the bottom half.

1. **Blind pass.** Read only the *reviewer view* (summary, generated resources, risk
   narrative, findings). Do **not** scroll to the reveal. Answer the open questions and
   commit your five 1–5 scores. This is where "toy smell" is detectable — you're seeing what
   an analyst or a scanner would see, with no answer key.
2. **Reveal pass.** Read the *reveal* section (the ground-truth critical path, the expected
   findings and why, and — for a mutated scenario — which resource is a benign decoy). Then
   answer one final question: **was the scenario coherent?** i.e. does the revealed ground
   truth match the story you reconstructed blind, or did the reveal contradict what the
   resources implied?

Revealing first defeats the purpose: you'd score realism against the answer key instead of
against your own read of the estate.

## The five scales

Score each **1–5** using the anchors below. Anchors are deliberately concrete so two
reviewers calibrate to the same number, not to a vibe.

### 1. Realism — *would this happen in a real environment?*

| Score | Anchor |
|-------|--------|
| **1** | Toy. Resource names, wiring, or the risk itself could not occur in a real SaaS estate (e.g. a role that exists only to be misconfigured, no plausible business reason). |
| **3** | Plausible but generic. The shape is real, but it reads like a textbook example rather than a specific team's mistake. |
| **5** | Indistinguishable from a real estate. You could believe a specific engineering team shipped this on a Friday. Names, environments, and the risk chain all cohere. |

### 2. Clarity — *is the scenario legible?*

| Score | Anchor |
|-------|--------|
| **1** | Confusing. The resources, the narrative, and the findings don't line up; you can't tell what the scenario is about without the reveal. |
| **3** | Followable with effort. The story is there but you re-read to connect resources to findings. |
| **5** | Immediately legible. A reader knows the resources, the risk, and the findings on one pass, in under 5 minutes. |

### 3. Training usefulness — *would this help train an analyst?*

| Score | Anchor |
|-------|--------|
| **1** | Nothing to learn. Single obvious misconfiguration with no chain and no decoy; a checkbox, not a lesson. |
| **3** | One solid teaching point (e.g. one non-obvious chain step) plus filler. |
| **5** | Rich. A multi-step chain an analyst must reason through, a convincing false-positive to *not* chase, and a defensible remediation order — a scenario you'd assign as an exercise. |

### 4. Scanner-benchmark usefulness — *would this help benchmark a scanner?*

| Score | Anchor |
|-------|--------|
| **1** | Measures nothing useful. Every finding is trivially visible (or trivially hidden), so a scanner's score on it is uninformative. |
| **3** | Discriminating on one axis — e.g. it separates scanners that catch the `PassRole` chain from those that don't. |
| **5** | A strong benchmark case: a mix of visible, partial, and effectively-hidden findings plus a documented false-positive, so a scanner's precision **and** recall are both measured. |

### 5. Ground-truth trust — *do you trust the answer key?*

| Score | Anchor |
|-------|--------|
| **1** | The reveal contradicts the resources — the "critical path" isn't actually reachable, or an expected finding points at the wrong resource. You would not trust this as a label. |
| **3** | Ground truth is defensible but you'd want a second opinion on one edge or one severity. |
| **5** | Airtight. Every edge in the critical path is justified by a resource in the graph; every expected finding maps to a real resource; the false-positive is genuinely benign. You'd trust this as a gold label. |

## Open questions (answer in prose on the sheet)

Blind pass — answer before the reveal:

- Would this happen in a real SaaS/cloud environment?
- Is the risk chain plausible end-to-end?
- Are the findings too toy-like?
- Is the remediation order correct — is that the sequence you'd actually enforce?
- Would this help **benchmark a scanner**?
- Would this help **train an analyst**?
- What is missing — what would make it more realistic or more useful?

Reveal pass — answer after the reveal:

- Was the scenario **coherent**? Did the revealed ground truth match the story the resources
  told, or did it contradict your blind read?

## Scoring in under 20 minutes

The rubric and the 1-page format are designed so a single scenario takes **under 20
minutes** end-to-end: ~10 min blind read + open questions + five scores, ~5 min reveal +
coherence check, ~5 min buffer. If a scenario routinely takes longer, that is itself a
clarity signal worth recording.

## Recording scores

Suggested per-scenario line (three of these — one per reviewer):

```
scenario_id, reviewer_role, realism, clarity, training, scanner, ground_truth, coherent(y/n), notes
```

Aggregate across reviewers **after** all three have scored independently. A scenario that
splits the panel (e.g. one 5 and one 2 on realism) is the most interesting outcome — that
disagreement is the product signal this rubric exists to surface.
