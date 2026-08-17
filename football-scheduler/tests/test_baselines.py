"""The committed baselines load, score, and match their committed reports.

Two jobs. The first is a data guard: a baseline CSV whose team ids have gone
stale, or a sidecar someone added without provenance, should fail here rather
than at the next refresh. The second is the staleness check — if a constraint
is added or re-weighted and `baselines/reports/` is not regenerated, the
committed number is quietly lying about the current ruleset, and that is
exactly the failure a baseline exists to prevent.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from terminliste.baseline import (
    BaselineError,
    discover_baselines,
    evaluate_baseline,
    load_baseline,
)
from terminliste.model.loader import load_world

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = PROJECT_ROOT / "baselines" / "sources"
REPORTS_DIR = PROJECT_ROOT / "baselines" / "reports"


@pytest.fixture(scope="module")
def world():
    return load_world(PROJECT_ROOT / "data")


@pytest.fixture(scope="module")
def sources():
    return discover_baselines(SOURCES_DIR)


def test_at_least_one_baseline_is_committed(sources):
    assert sources, "baselines/sources/ should hold at least one real schedule"


def test_every_baseline_scores(world, sources):
    for source in sources:
        evaluation = evaluate_baseline(source, world)
        assert evaluation.matches, f"{source.id} produced no matches"
        assert evaluation.score.num_matches == len(evaluation.matches)


def test_every_baseline_has_a_committed_report(sources):
    for source in sources:
        assert (REPORTS_DIR / f"{source.id}.json").exists()
        assert (REPORTS_DIR / f"{source.id}.md").exists()


def test_reports_are_up_to_date():
    """`--check` is the contract; run it rather than re-deriving it here."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "refresh_baselines.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "baselines/reports/ is out of date — run "
        f"`python scripts/refresh_baselines.py`.\n{result.stdout}\n{result.stderr}"
    )


def test_every_hard_violation_is_declared_in_the_sidecar(world, sources):
    """A baseline may only break hard rules its sidecar owns up to.

    This is what keeps `expected_hard_violations` honest. Left unchecked it
    would rot into a stale paragraph that explains away violations nobody
    re-read; tied to the score, an undeclared violation is a test failure that
    forces a decision — either the schedule data is wrong, or the sidecar owes
    the reader an explanation.
    """
    for source in sources:
        evaluation = evaluate_baseline(source, world)
        broken = {r.constraint_id for r in evaluation.score.hard_results() if r.count}
        declared = " ".join(source.expected_hard_violations)
        undeclared = sorted(c for c in broken if c not in declared)
        assert not undeclared, (
            f"{source.id} breaks {undeclared}, which its sidecar does not mention. "
            "Either the fixture data is wrong or expected_hard_violations needs updating."
        )


def test_sidecar_is_required(tmp_path):
    (tmp_path / "orphan.csv").write_text("competition,date,home_team,away_team\n", encoding="utf-8")
    assert discover_baselines(tmp_path) == []


def test_missing_required_field_is_rejected(tmp_path):
    sidecar = tmp_path / "bad.yml"
    sidecar.write_text(yaml.safe_dump({"id": "bad", "name": "Bad"}), encoding="utf-8")
    with pytest.raises(BaselineError, match="missing required field"):
        load_baseline(sidecar)


def test_missing_schedule_file_is_rejected(tmp_path):
    sidecar = tmp_path / "bad.yml"
    sidecar.write_text(
        yaml.safe_dump(
            {
                "id": "bad",
                "name": "Bad",
                "season": "2026",
                "schedule_file": "nope.csv",
                "verified": False,
                "retrieved": "2026-08-16",
                "sources": ["somewhere"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BaselineError, match="does not exist"):
        load_baseline(sidecar)
