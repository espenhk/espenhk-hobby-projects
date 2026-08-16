#!/usr/bin/env python3
"""Terminliste — season scheduling for related football leagues.

    python cli.py validate                       # data integrity, no solving
    python cli.py generate --season 2026          # solve and write a report
    python cli.py score my_schedule.csv --season 2026
                                                   # score a real/proposed schedule
    python cli.py explain schedules/2026.json      # score breakdown in the terminal
    python cli.py export-frontend --season 2026    # publish the frontend data
                                                    # contract to ../football-scheduler-frontend

`validate` and `score` need no solver and run in well under a second.
`generate` runs the local-search solver by default (`--solver cpsat` needs
OR-Tools installed).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data"
SCHEDULES_ROOT = PROJECT_ROOT / "schedules"
# The frontend prep folder is a sibling project today (see CONTRACT.md); once
# it's extracted into its own repo, point --frontend-repo at that checkout.
DEFAULT_FRONTEND_ROOT = PROJECT_ROOT.parent / "football-scheduler-frontend"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(DEFAULT_FRONTEND_ROOT))

from render import render_report  # noqa: E402  (football-scheduler-frontend/render.py)
from terminliste.external_schedule import ExternalScheduleError, load_external_schedule  # noqa: E402
from terminliste.model.loader import DataError, World, load_world  # noqa: E402
from terminliste.model.schema import Season  # noqa: E402
from terminliste.model.travel import HaversineTravelModel  # noqa: E402
from terminliste.report.render import write_frontend_json, write_json  # noqa: E402
from terminliste.scoring.base import EvalContext, Score, evaluate  # noqa: E402
from terminliste.scoring.registry import build_constraints  # noqa: E402
from terminliste.solvers import Candidate, SolveRequest, SolverResult, get_scheduler  # noqa: E402


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        world = load_world(DATA_ROOT)
    except DataError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        f"OK: {len(world.venues)} venues, {len(world.clubs)} clubs, {len(world.teams)} teams, "
        f"{len(world.competitions)} competitions, {len(world.seasons)} season(s)."
    )
    dual = world.dual_clubs()
    print(f"     {len(dual)} dual clubs: {', '.join(c.name for c in dual)}")
    for competition in world.competitions.values():
        print(
            f"     {competition.name}: {competition.team_count} teams, "
            f"{competition.rounds} rounds, {competition.total_matches} matches"
        )
    return 0


def _solve_season(args: argparse.Namespace) -> tuple[World, Season, SolverResult] | None:
    """Load, solve, and return candidates — shared by `generate` and `export-frontend`."""
    world = _load_world_or_exit()
    season = _season_or_exit(world, args.season)
    competitions = [world.competition(c) for c in season.competitions]
    constraints = build_constraints(world, season, competitions)
    travel = HaversineTravelModel(world)
    ctx = EvalContext(world=world, season=season, travel=travel)

    scheduler = get_scheduler(args.solver)
    request = SolveRequest(
        world=world,
        season=season,
        competitions=competitions,
        constraints=constraints,
        ctx=ctx,
        seed=args.seed,
        top_n=args.top_n,
        time_budget_s=args.time_budget,
    )

    print(f"Solving with {scheduler.name} (budget {args.time_budget:.0f}s, seed {args.seed})...")
    try:
        result = scheduler.solve(request)
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return None

    if not result.candidates:
        print("FAIL: solver produced no candidates.", file=sys.stderr)
        for note in result.notes:
            print(f"  - {note}", file=sys.stderr)
        return None

    return world, season, result


def cmd_generate(args: argparse.Namespace) -> int:
    solved = _solve_season(args)
    if solved is None:
        return 1
    world, season, result = solved

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{season.id}.html"
    json_path = out_dir / f"{season.id}.json"

    render_report(world, season, result, html_path, title=f"{season.year} season schedule")
    write_json(result, json_path)

    _print_summary(result)
    print(f"\nWrote {html_path} and {json_path}")
    return 0


def cmd_export_frontend(args: argparse.Namespace) -> int:
    solved = _solve_season(args)
    if solved is None:
        return 1
    world, season, result = solved

    frontend_repo = Path(args.frontend_repo)
    if not frontend_repo.is_dir():
        print(f"FAIL: no such frontend project: {frontend_repo}", file=sys.stderr)
        return 1

    fixture_path = frontend_repo / "data" / f"{season.id}.frontend.json"
    write_frontend_json(world, season, result, fixture_path)
    print(f"Wrote {fixture_path}")

    subprocess.run(["git", "-C", str(frontend_repo), "add", str(fixture_path)], check=True)
    commit = subprocess.run(
        ["git", "-C", str(frontend_repo), "commit", "-m", f"chore: refresh {season.id} season fixture"],
        capture_output=True,
        text=True,
    )
    if commit.returncode != 0:
        # Most commonly "nothing to commit" — the fixture didn't change.
        print((commit.stdout + commit.stderr).strip())
        return 0

    print(commit.stdout.strip())
    if args.push:
        subprocess.run(["git", "-C", str(frontend_repo), "push"], check=True)
        print("Pushed.")
    else:
        print("Not pushed — rerun with --push, or push manually, when ready.")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    world = _load_world_or_exit()
    season = _season_or_exit(world, args.season)
    competitions = [world.competition(c) for c in season.competitions]
    constraints = build_constraints(world, season, competitions)
    travel = HaversineTravelModel(world)

    try:
        matches, warnings = load_external_schedule(Path(args.schedule), world)
    except ExternalScheduleError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if not matches:
        print("FAIL: schedule file contained no matches.", file=sys.stderr)
        return 1

    ctx = EvalContext(world=world, season=season, travel=travel, detail=True)
    score = evaluate(matches, constraints, ctx)

    print(f"Scored {len(matches)} matches from {args.schedule}\n")
    if warnings:
        print("Coverage notes:")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        print()

    _print_score(score)

    result = SolverResult(
        candidates=[Candidate(matches=matches, score=score, label="Imported schedule")],
        solver="external",
    )
    out_path = Path(args.out) if args.out else SCHEDULES_ROOT / f"{Path(args.schedule).stem}_scored.html"
    render_report(
        world,
        season,
        result,
        out_path,
        title=f"Score report — {Path(args.schedule).name}",
        full_diagnostics=True,
        warnings=warnings,
    )
    print(f"\nWrote {out_path}")

    return 0 if score.feasible else 2


def cmd_explain(args: argparse.Namespace) -> int:
    path = Path(args.schedule_json)
    if not path.exists():
        print(f"FAIL: no such file: {path}", file=sys.stderr)
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))

    options = payload.get("options", [])
    if args.option is not None:
        options = [o for o in options if o.get("label") == args.option]
    if not options:
        print("FAIL: no matching option in that file.", file=sys.stderr)
        return 1

    for option in options:
        print(f"=== {option['label']} (seed {option.get('seed', '?')}) ===")
        print(f"  hard violations: {option['hard_violations']}")
        print(f"  soft total:      {option['soft_total']}")
        for row in sorted(option["breakdown"], key=lambda r: (r["kind"] != "hard", -abs(r["total"]))):
            if not row["count"]:
                continue
            print(f"    {row['constraint']:<28} {row['total']:>9.1f}  (kind={row['kind']}, n={row['count']})")
        print()
    return 0


def _print_summary(result: SolverResult) -> None:
    print(f"\n{len(result.candidates)} option(s), {result.iterations} iterations, "
          f"{result.elapsed_s:.1f}s elapsed")
    for note in result.notes:
        print(f"  note: {note}")
    for candidate in result.candidates:
        badge = "feasible" if candidate.score.feasible else f"{candidate.score.hard_violations} HARD VIOLATIONS"
        print(f"  {candidate.label}: score={candidate.score.soft_total:.1f} ({badge})")


def _print_score(score: Score) -> None:
    if score.feasible:
        print("Feasible — no hard rules broken.\n")
    else:
        print(f"NOT FEASIBLE — {score.hard_violations} hard rule violation(s):\n")
        for result in score.hard_results():
            if not result.count:
                continue
            print(f"  ✗ {result.constraint_id} ({result.count})")
            for event in result.events[:5]:
                print(f"      {event.detail}")
            if len(result.events) > 5:
                print(f"      ...and {len(result.events) - 5} more")
        print()

    print(f"Soft score: {score.soft_total:.1f}\n")
    print("Soft rules, worst first:")
    for result in sorted(score.soft_results(), key=lambda r: r.total):
        marker = "✗" if result.total < 0 else ("·" if result.total == 0 else "✓")
        print(f"  {marker} {result.constraint_id:<28} {result.total:>9.1f}  (n={result.count})")


def _load_world_or_exit():
    try:
        return load_world(DATA_ROOT)
    except DataError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)


def _season_or_exit(world, season_id: str):
    try:
        return world.season(season_id)
    except DataError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="check data files for referential integrity")
    p_validate.set_defaults(func=cmd_validate)

    p_generate = sub.add_parser("generate", help="solve a season and write an HTML + JSON report")
    p_generate.add_argument("--season", default="2026")
    p_generate.add_argument("--solver", choices=["local", "cpsat"], default="local")
    p_generate.add_argument("--seed", type=int, default=42)
    p_generate.add_argument("--top-n", type=int, default=3)
    p_generate.add_argument("--time-budget", type=float, default=60.0, help="seconds")
    p_generate.add_argument("--out", default=str(SCHEDULES_ROOT))
    p_generate.set_defaults(func=cmd_generate)

    p_score = sub.add_parser("score", help="score a real or proposed schedule (CSV/JSON) against the rules")
    p_score.add_argument("schedule", help="path to a .csv or .json schedule file")
    p_score.add_argument("--season", default="2026")
    p_score.add_argument("--out", default=None, help="HTML report path")
    p_score.set_defaults(func=cmd_score)

    p_explain = sub.add_parser("explain", help="print a generated schedule's score breakdown")
    p_explain.add_argument("schedule_json")
    p_explain.add_argument("--option", default=None, help="only this option's label, e.g. 'Option 1'")
    p_explain.set_defaults(func=cmd_explain)

    p_export = sub.add_parser(
        "export-frontend",
        help="solve, write the frontend JSON contract, and commit it into the frontend project",
    )
    p_export.add_argument("--season", default="2026")
    p_export.add_argument("--solver", choices=["local", "cpsat"], default="local")
    p_export.add_argument("--seed", type=int, default=42)
    p_export.add_argument("--top-n", type=int, default=3)
    p_export.add_argument("--time-budget", type=float, default=60.0, help="seconds")
    p_export.add_argument(
        "--frontend-repo",
        default=str(DEFAULT_FRONTEND_ROOT),
        help="path to the football-scheduler-frontend checkout to publish into",
    )
    p_export.add_argument("--push", action="store_true", help="also `git push` the frontend repo (off by default)")
    p_export.set_defaults(func=cmd_export_frontend)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
