"""Renders a solver result as one self-contained HTML page.

No external assets: the CSS and the tab-switching script are inlined, so the
file opens from disk, survives being emailed, and renders the same in a year.

The page exists to answer one question — *which of these three schedules should
we use?* — so it leads with the score, then what each option is winning and
losing, then the calendar itself.

This is the presentation layer for the football-scheduler project: it only
turns an already-solved schedule into HTML. The enrichment (resolving team
and venue names, weekday strings, dual-club colors, the back-to-back-home-day
`paired` flag) lives in `terminliste.report.views` over in the
`football-scheduler/` project — the same view model backs both this page and
the JSON data contract (`football-scheduler/CONTRACT.md`) that a future
React/Vite frontend (see the follow-up issue) will consume instead.

This folder is a staging area, not a standalone package yet: it currently
depends on `football-scheduler/` being its sibling directory in the same
checkout (see the sys.path bootstrap below). That assumption goes away once
this becomes its own repo per the follow-up issue.
"""

from __future__ import annotations

import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

FRONTEND_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = FRONTEND_ROOT.parent / "football-scheduler"
sys.path.insert(0, str(BACKEND_ROOT))

from terminliste.model.loader import World  # noqa: E402
from terminliste.model.schema import Season  # noqa: E402
from terminliste.report.views import build_option, club_colors_for  # noqa: E402
from terminliste.solvers.base import SolverResult  # noqa: E402

TEMPLATE_DIR = FRONTEND_ROOT / "templates"


def render_report(
    world: World,
    season: Season,
    result: SolverResult,
    output_path: Path,
    title: str | None = None,
    full_diagnostics: bool = False,
    warnings: list[str] | None = None,
) -> Path:
    """Render a solver result (or a single scored schedule) as one HTML page.

    `full_diagnostics=True` is for scoring one externally supplied schedule
    rather than choosing between solver candidates: every negative-scoring
    rule is shown, not just the top few, and a dedicated section calls out
    broken hard rules by name. `warnings` surfaces non-fatal issues found while
    loading that schedule (e.g. a pair that never played) above the score.
    """
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("season.html.j2")

    club_colors = club_colors_for(world)
    options = [
        build_option(world, season, candidate, club_colors, full_diagnostics)
        for candidate in result.candidates
    ]

    html = template.render(
        title=title or f"{season.year} season schedule",
        season=season,
        result=result,
        options=options,
        club_colors=club_colors,
        dual_clubs=sorted(world.dual_clubs(), key=lambda c: c.name),
        warnings=warnings or [],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
