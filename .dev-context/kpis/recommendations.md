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
