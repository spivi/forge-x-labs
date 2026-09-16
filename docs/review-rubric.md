# Scenario Quality Rubric

Tests prove a scenario is engineering-valid (schema, graph, ground truth).
They cannot prove it is useful: realistic, good for training and scanner
benchmarking, and hard to fake. This rubric is the human check for
"toy-scenario smell." Score one scenario at a time using the sheets in
[`review-pack-template.md`](review-pack-template.md).

## Reviewer roles

Each scenario is scored independently by three reviewers. Do not confer
before scoring. Disagreement is useful.

| Role | Reads for |
|------|-----------|
| Cloud-security engineer | Would this configuration exist in a real SaaS/cloud estate? Would you fix this chain in a real review? |
| CSPM / detection engineer | Would a scanner plausibly flag these findings? Is the visible/partial/hidden split honest? |
| Red-team / cloud-assessment | Is the critical path exploitable end to end? Is the remediation order what an attacker would force? Are the false positives convincing? |

This repo ships the rubric, the template, and a sample pack. It does not
simulate reviewers.

## Blind then reveal

1. **Blind pass.** Read only the reviewer view. Do not scroll to the reveal.
   Answer the open questions and commit five 1-5 scores.
2. **Reveal pass.** Read the ground-truth path, expected findings, and (for
   a mutated scenario) which resource is a benign decoy. Then answer: was
   the scenario coherent? Did the reveal match the story you reconstructed?

Revealing first defeats the purpose.

## The five scales

Score each 1-5 using the anchors below.

### 1. Realism: would this happen in a real environment?

| Score | Anchor |
|-------|--------|
| **1** | Toy. Names, wiring, or the risk could not occur in a real SaaS estate. |
| **3** | Plausible but generic. Reads like a textbook example. |
| **5** | You could believe a specific team shipped this on a Friday. |

### 2. Clarity: is the scenario legible?

| Score | Anchor |
|-------|--------|
| **1** | Confusing. You cannot tell what it is about without the reveal. |
| **3** | Followable with effort. |
| **5** | A reader knows the resources, the risk, and the findings in one pass. |

### 3. Training usefulness: would this help train an analyst?

| Score | Anchor |
|-------|--------|
| **1** | Nothing to learn. One obvious misconfiguration, no chain, no decoy. |
| **3** | One solid teaching point plus filler. |
| **5** | A multi-step chain, a convincing false positive, and a defensible remediation order. |

### 4. Scanner-benchmark usefulness: would this help benchmark a scanner?

| Score | Anchor |
|-------|--------|
| **1** | Measures nothing useful. Every finding is trivially visible or trivially hidden. |
| **3** | Discriminating on one axis (for example scanners that catch PassRole vs those that do not). |
| **5** | Mix of visible, partial, and hidden findings plus a documented false positive. |

### 5. Ground-truth trust: do you trust the answer key?

| Score | Anchor |
|-------|--------|
| **1** | The reveal contradicts the resources. You would not trust this as a label. |
| **3** | Defensible, but you would want a second opinion on one edge or severity. |
| **5** | Every critical-path edge is justified. Every finding maps to a real resource. The false positive is genuinely benign. |

## Open questions

Blind pass:

- Would this happen in a real SaaS/cloud environment?
- Is the risk chain plausible end to end?
- Are the findings too toy-like?
- Is the remediation order the sequence you would actually enforce?
- Would this help benchmark a scanner?
- Would this help train an analyst?
- What is missing?

Reveal pass:

- Was the scenario coherent?

Target: under 20 minutes per scenario.

```
scenario_id, reviewer_role, realism, clarity, training, scanner, ground_truth, coherent(y/n), notes
```

Aggregate after all three have scored independently.
