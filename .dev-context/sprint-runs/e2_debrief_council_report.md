
---
## 🟦 Antigravity (coherence-scope) - Gemini 3.5 Flash (High)
Here is the Coherence & Scope Review for the **FXL-E2 Learning-Corpus Epic — Debrief Summary**.

---

### **1. Contradictions & Classification Issues**

#### **[BLOCKER] Misclassification of Blocking Defect**
*   **Cited Passage:** 
    > **Known follow-ups (low priority, non-blocking)**
    > - **#90** — checkov adapter live-parse: the real policy-index page has an extra leading column, so the adapter extracts 0 records from a live fetch (the recorded fixture works). **Blocks a real second source until fixed.**
*   **Finding:** There is an internal contradiction in the severity classification. The ticket `#90` is placed under the "non-blocking" header, yet its description explicitly states that it *"blocks a real second source until fixed."* If integrating or verifying a second data source is required for the corpus's completeness or subsequent milestones, this defect is functionally a blocker and should not be marked as a low-priority, non-blocking follow-up.

---

### **2. Gaps Between Intent, Plan, and Execution**

#### **[NICE-TO-HAVE] Financial Tracking and Budget Gap**
*   **Cited Passage:**
    > **Known follow-ups (low priority, non-blocking)**
    > - **Fable pricing gap:** `claude-fable-5` isn't in `budgets.yml` pricing, so #98's build cost logged as $0 (duration captured correctly, which is what estimate calibration needs).
*   **Finding:** The epic successfully utilized a new model tier (`fable`) to author fragments for FXL-98, but the reporting infrastructure was not updated to support it. Bypassing pricing configuration led to a silent logging failure where the build cost was recorded as `$0`. While duration-based calibration still works, this gap undermines the accuracy of budget tracking for the epic.

#### **[NICE-TO-HAVE] Process Bypasses in the Learning Loop**
*   **Cited Passage:**
    > **Learning-loop outcome**
    > - **Quantitative calibration:** `debrief.py` analyzed **23 runs** (E2 actuals backfilled into the ledger, since the build agents were dispatched directly rather than via `/sprint execute`, so the SessionEnd/SUBAGENT_LEDGER_CAPTURE hooks did not auto-record them).
*   **Finding:** The development team bypassed the standard execution pipeline (`/sprint execute`) in favor of direct dispatch. Although the data was backfilled manually for the debrief, bypassing these automation hooks introduces execution risks and extra manual overhead, indicating a process gap between planned execution workflows and actual developer behavior.

---

### **3. Scope & Coherence Verification**

*   **Fragment Count Alignment (Verified):** The scope states that FXL-98 hand-authored 14 fragments. The export gate (FXL-71) filtered out 2 of those fragments due to falling below the 0.70 quality bar, resulting in a 12/14 export bundle. This is coherent and correctly demonstrates that the quality gates worked as designed without gaming the metrics.
*   **Backlog Status (Verified):** The summary states that the backlog re-seed found only the closed E2 trio, meaning no unexpected scope was left open or silently deferred to the backlog outside of the noted follow-ups.


---
## 🔳 Codex (correctness-falsifiability) - gpt-5.5
**Findings**

**BLOCKER: Evidence claims are not falsifiable from the summary.**  
Section: **Scope / What shipped / Governance boundary / Learning-loop outcome**  
Passages: “all merged to master (`af475aa`)”, “Each passed a fresh-context Opus review gate”, “green on first CI run”, “24 adversarial probes”, “all 8 checks executed”, “debrief.py analyzed 23 runs”, “lemmings fit fitted 2 knobs”.  
These are checkable claims, but the document does not provide CI run IDs, review artifact paths, PR review links, command transcripts, ledger paths, or exact commits beyond a short hash. PR numbers alone are not enough to verify the specific assertions.

**BLOCKER: The key semantic claim depends on unshown evidence.**  
Section: **The headline outcome**  
Passage: “honest 12/14 training bundle… excluded via `below_quality_bar`, not gamed… both the author's tests and the review gate recomputed this live against the real catalog.”  
This is the central correctness claim, but it gives no command, output, artifact path, catalog version, export file checksum, or exact quality scores for the two excluded seeds. “Not gamed” is also a judgment claim unless tied to concrete invariants.

**BLOCKER: The #96 failure narrative is presented as fact without enough provenance.**  
Section: **The pivotal lesson**  
Passage: “An earlier attempt (#96) auto-built graph fragments that passed all mechanical validation while encoding semantically FALSE cloud relationships…”  
This may be true, but the summary needs a verifiable reference to the failed artifacts or review finding. Without that, the causal lesson rests on an anecdote that cannot be independently checked.

**BLOCKER: Governance safety claim is too absolute for the cited evidence.**  
Section: **Governance boundary (FXL-71)**  
Passage: “The absolute exclusion (`unsafe_operational`) is checked first… so it cannot be bypassed… No leaks.”  
The ordering test supports one bypass path, but “cannot be bypassed” and “No leaks” are universal claims. The document names one adversarial probe but does not enumerate all 24, so the boundary of what was tested is unclear.

**BLOCKER: Quantitative calibration lacks reproducibility details.**  
Section: **Learning-loop outcome**  
Passages: “`debrief.py` analyzed 23 runs”, “factor 0.383”, “CI 0.279–0.487”, “0 underpowered”, “10 well-matched / 2 overkill”.  
These metrics are falsifiable in principle, but the summary omits the ledger location, command invocation, input revision, confidence-interval method, and definitions for “underpowered”, “well-matched”, and “overkill.”

**Nice-to-have: Some wording is evaluative rather than measurable.**  
Sections: **Headline outcome / Pivotal lesson / Takeaway**  
Passages: “real, honestly-gated corpus”, “genuinely-simple”, “legitimately edge-less”, “careful semantic authoring”, “adversarial meaning review”.  
These may be accurate, but they are not acceptance criteria. Prefer pairing them with measurable checks already mentioned elsewhere: fragment count, exclusion reasons, quality scores, forbidden edge assertions, and review commands.

**Nice-to-have: The model/cost claims need clearer boundaries.**  
Section: **Learning-loop outcome / Known follow-ups**  
Passages: “everything is `sonnet`-sufficient or lower”, “Fable pricing gap… build cost logged as $0”.  
The summary correctly flags the pricing gap, but this also means any cost-related conclusions involving #98 are incomplete. The document should avoid implying complete model economics while one model family has missing pricing.

**Nice-to-have: “All three green on first CI run” should define CI scope.**  
Section: **What shipped**  
Passage: “All three delivered green on first CI run (0 fix cycles), `ruff` + `mypy --strict` clean…”  
It is unclear whether “CI” includes only required GitHub checks, local validation, review-gate execution, or all of them. The claim is useful but underspecified.

**Overall**

The summary is directionally concrete and contains many falsifiable claims, but it does not include enough evidence handles to independently verify its strongest assertions. The main issue is not proposed scope; it is traceability. As written, the reader must trust the author for the review gates, corpus counts, safety boundary, calibration metrics, and simulator results.



---
## Synthesis

**Consensus**

Both reviewers agree the summary contains strong directional claims that lack sufficient traceability. The core shared finding: the document asserts correctness ("not gamed," "no leaks," "green on first CI run") without providing the artifact handles, paths, or command transcripts that would let a reader independently verify those assertions. The Fable pricing gap and backfill workaround are noted by both as process weaknesses, though neither treats them as blockers independently.

**Divergence**

The two reviewers diverge on one point that matters for action: Antigravity flags the `#90` checkov-adapter issue as a misclassified blocker (the document calls it non-blocking yet its description says it blocks a second source). Codex does not mention `#90` at all — its blockers are entirely about evidence traceability, not operational scope. This divergence is relevant because it affects what must be fixed: Antigravity would require reclassifying `#90` before acting on the summary; Codex's blockers can be resolved by adding artifact references without touching scope.

**Blockers**

1. **Misclassified severity of `#90`**: The document lists `#90` as "non-blocking" while its own text states it blocks a real second source. The classification must be corrected — either promote it to a tracked blocker or explicitly argue why the second source is out of scope for acting on this summary.

2. **Missing evidence handles for central correctness claims**: The "honest 12/14 bundle / not gamed" claim, the governance "no leaks" assertion, the `#96` pivotal-lesson narrative, and the calibration metrics (`factor 0.383`, CI bounds, 23-run ledger) are all stated without artifact paths, command transcripts, PR review links, or checksums. A reader cannot verify them from the document as written.

**Recommendation**

Add a compact "Evidence appendix" section (can be a bullet list) that maps each major claim to its artifact: the ledger file path, the export file or checksum, the PR review comment URLs, the `debrief.py` invocation, and a pointer to the `#96` failed-artifact review finding. Then reclassify `#90` — promote it to a tracked follow-up with a blocker label, or scope it out explicitly. Both fixes are low-effort edits to the document itself; no re-work of the code is implied. Once those two changes are made, the summary is sound enough to act on.

> This council review is advisory. It does not approve the document; a human owner decides.

```council-autofix
[
  {
    "file": ".dev-context/sprint-runs/e2_debrief_summary.md",
    "change": "Reclassify ticket #90 from 'non-blocking follow-up' to a tracked blocker (or add an explicit statement that a second source is out of scope for this summary's acceptance), removing the internal contradiction between the section header and the ticket's own description."
  },
  {
    "file": ".dev-context/sprint-runs/e2_debrief_summary.md",
    "change": "Add an 'Evidence' or 'Artifact references' section mapping each major claim to a verifiable handle: (a) ledger file path + debrief.py invocation for the 23-run calibration metrics; (b) export file path or checksum for the 12/14 bundle; (c) PR review comment URL(s) or review-gate artifact path for the 'not gamed' and 'no leaks' governance claims; (d) a pointer to the #96 failed-artifact or review finding that grounds the pivotal-lesson narrative."
  }
]
```
