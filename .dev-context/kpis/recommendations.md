# Debrief Recommendations Log

Prioritized call-to-action emitted by `/debrief` after each run. **P1** = act now,
**P2** = soon, **P3** = consider. Each entry names the artifact to change.

- **[TUNE]** recs are auto-applied (calibration factors / model-policy routing).
- **[CREATE]** recs need a human decision — surfaced via `AskUserQuestion` and filed
  as gated follow-up tickets, never auto-applied.

<!-- runs appended below -->

## debrief run

- **[TUNE] label:effort:M is overkill -> sonnet** (P3) -- 0 underpowered / 3 overkill / 0 well-matched over 3 runs [floor: sonnet]. Target: `kpis/model-policy.json`. Down-tier label:effort:M to sonnet (saves cost).
- **[TUNE] label:area:generation is overkill -> sonnet** (P3) -- 0 underpowered / 3 overkill / 0 well-matched over 3 runs [floor: sonnet]. Target: `kpis/model-policy.json`. Down-tier label:area:generation to sonnet (saves cost).

## debrief run

- **[TUNE] label:effort:M is overkill -> sonnet** (P3) -- 0 underpowered / 3 overkill / 1 well-matched over 4 runs [floor: sonnet]. Target: `kpis/model-policy.json`. Down-tier label:effort:M to sonnet (saves cost).
- **[TUNE] label:area:generation is overkill -> sonnet** (P3) -- 0 underpowered / 3 overkill / 1 well-matched over 4 runs [floor: sonnet]. Target: `kpis/model-policy.json`. Down-tier label:area:generation to sonnet (saves cost).

## debrief run

- **[TUNE] label:effort:M is overkill -> sonnet** (P3) -- 0 underpowered / 3 overkill / 1 well-matched over 4 runs [floor: sonnet]. Target: `kpis/model-policy.json`. Down-tier label:effort:M to sonnet (saves cost).
- **[TUNE] label:area:generation is overkill -> sonnet** (P3) -- 0 underpowered / 4 overkill / 1 well-matched over 5 runs [floor: sonnet]. Target: `kpis/model-policy.json`. Down-tier label:area:generation to sonnet (saves cost).
- **[TUNE] type:fix is overkill -> sonnet** (P3) -- 0 underpowered / 2 overkill / 1 well-matched over 3 runs [floor: sonnet]. Target: `kpis/model-policy.json`. Down-tier type:fix to sonnet (saves cost).

## debrief run

- **[TUNE] Estimator over-predicts type:feature** (P2) -- factor 0.383 over 15 runs (CI 0.279-0.487). Target: `scripts/estimator.py + kpis/calibration.json (auto-applied)`. Calibration factor applied; recheck next debrief.
- **[TUNE] Estimator over-predicts label:effort:M** (P2) -- factor 0.383 over 19 runs (CI 0.25-0.722). Target: `scripts/estimator.py + kpis/calibration.json (auto-applied)`. Calibration factor applied; recheck next debrief.
- **[TUNE] Estimator over-predicts label:area:corpus** (P2) -- factor 0.41 over 12 runs (CI 0.25-0.606). Target: `scripts/estimator.py + kpis/calibration.json (auto-applied)`. Calibration factor applied; recheck next debrief.
- **[TUNE] label:area:generation is overkill -> sonnet** (P3) -- 0 underpowered / 6 overkill / 3 well-matched over 9 runs [floor: sonnet]. Target: `kpis/model-policy.json`. Down-tier label:area:generation to sonnet (saves cost).
- **[TUNE] label:effort:S is overkill -> haiku** (P3) -- 0 underpowered / 2 overkill / 1 well-matched over 3 runs [floor: haiku]. Target: `kpis/model-policy.json`. Down-tier label:effort:S to haiku (saves cost).
