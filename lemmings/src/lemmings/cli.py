"""`lemmings` CLI entrypoint.

Usage:
    lemmings list                         # list canned scenarios
    lemmings level <name> --seed S [--trace PATH]
    lemmings sweep <name> --knob path:lo:hi [--knob ...]
                          [--points N] [--seeds K]
                          [--sampler lhs|sobol] [--out CSV] [-j N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lemmings import scenarios
from lemmings.sim.scenario import run_scenario
from lemmings.sim.trace import Trace


def _cmd_list(_args: argparse.Namespace) -> int:
    for name in scenarios.all_names():
        print(name)
    return 0


def _cmd_level(args: argparse.Namespace) -> int:
    scenario = scenarios.get(args.name)
    trace = Trace(jsonl_path=Path(args.trace) if args.trace else None)
    result = run_scenario(scenario, seed=args.seed, trace=trace)
    print(f"scenario={scenario.name} seed={args.seed}")
    print(f"clock_end={result.clock.now:.2f} min")
    print(f"events={len(trace)}  ledger_rows={len(list(result.world.ledger_rows()))}")
    print(f"total_billed_usd={result.world.total_billed_usd():.4f}")
    print(f"sprint_budget={result.world.sprint_budget_usd():.2f}")
    print(f"budget_locked={result.world.is_budget_locked()}")
    if args.trace:
        print(f"trace_path={args.trace}")
    trace.close()
    return 0


def _parse_knob(spec: str) -> tuple[str, tuple[float, float]]:
    """Parse `path:lo:hi` into (path, (lo, hi))."""
    parts = spec.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"--knob expects path:lo:hi, got {spec!r}"
        )
    path, lo, hi = parts
    return path, (float(lo), float(hi))


def _cmd_fit(args: argparse.Namespace) -> int:
    """Fit SEM priors from a project's real KPI ledgers (loop B)."""
    from lemmings.sim import fit

    dev = Path(args.dev_context)
    ledger, bugs, reviews = fit.load_kpis(dev)
    result = fit.fit_priors(ledger, bugs, reviews, min_samples=args.min_samples)

    print(f"fitted {len(result['fitted'])} knob(s) from {dev}")
    for line in result["fitted"]:
        print(f"  + {line}")
    for knob, why in result["skipped"]:
        print(f"  - skipped {knob}: {why}")

    if not result["override"]:
        print("no knobs met the sample threshold -- synthetic defaults stand (cold start)")
        return 0
    if args.dry_run:
        print("(dry-run; nothing written)")
        return 0
    out = Path(args.out) if args.out else dev / "sim" / "priors.override.yml"
    fit.write_override(result["override"], out)
    print(f"wrote override -> {out}")
    return 0


def _cmd_sweep(args: argparse.Namespace) -> int:
    # Local import — `mc` extra is optional.
    try:
        from lemmings.sim.montecarlo import (
            ParameterSweep,
            records_to_csv,
            run_sweep,
        )
    except ImportError as exc:  # pragma: no cover
        print(f"sweep needs the [mc] extra: pip install -e .[mc]  ({exc})")
        return 2

    factory = scenarios.REGISTRY[args.name]
    knobs = dict(_parse_knob(k) for k in args.knob)
    sweep = ParameterSweep(
        name=f"{args.name}-sweep",
        knobs=knobs,
        points=args.points,
        seeds_per_point=args.seeds,
        sampler=args.sampler,
        sampler_seed=args.sampler_seed,
    )
    print(
        f"sweep={sweep.name} knobs={list(knobs)} "
        f"points={sweep.points} seeds={sweep.seeds_per_point} "
        f"runs={sweep.points * sweep.seeds_per_point}"
    )
    records = run_sweep(factory, sweep, n_jobs=args.jobs)
    out = Path(args.out)
    records_to_csv(records, out)
    print(f"wrote {len(records)} runs → {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lemmings")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list canned scenarios").set_defaults(func=_cmd_list)

    p_level = sub.add_parser("level", help="run a canned scenario")
    p_level.add_argument("name")
    p_level.add_argument("--seed", type=int, default=42)
    p_level.add_argument("--trace", type=str, default=None, help="path for JSONL trace")
    p_level.set_defaults(func=_cmd_level)

    p_fit = sub.add_parser("fit", help="fit SEM priors from real KPI ledgers")
    p_fit.add_argument(
        "--dev-context",
        default=".dev-context",
        help="path to the project's .dev-context dir (default: ./.dev-context)",
    )
    p_fit.add_argument("--min-samples", type=int, default=5)
    p_fit.add_argument(
        "--out", default=None, help="override path (default: <dev>/sim/priors.override.yml)"
    )
    p_fit.add_argument("--dry-run", action="store_true")
    p_fit.set_defaults(func=_cmd_fit)

    p_sweep = sub.add_parser("sweep", help="quasi-random parameter sweep")
    p_sweep.add_argument("name", help="scenario to sweep over")
    p_sweep.add_argument(
        "--knob",
        action="append",
        required=True,
        help="dotted-path:low:high (repeatable). e.g. retry.max_attempts:1:5",
    )
    p_sweep.add_argument("--points", type=int, default=32)
    p_sweep.add_argument("--seeds", type=int, default=10)
    p_sweep.add_argument("--sampler", choices=["lhs", "sobol"], default="lhs")
    p_sweep.add_argument("--sampler-seed", type=int, default=0)
    p_sweep.add_argument("--jobs", "-j", type=int, default=-1)
    p_sweep.add_argument("--out", type=str, required=True, help="CSV output path")
    p_sweep.set_defaults(func=_cmd_sweep)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
