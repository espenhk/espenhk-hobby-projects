#!/usr/bin/env python3
"""Validate PBIP repository conventions for dataplatform-beta."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POWERBI_DIR = ROOT / "powerbi"
DEPLOY_DIR = POWERBI_DIR / "deployment"

SEMANTIC_MODEL_PATTERN = re.compile(r"^sm_[a-z0-9]+(?:_[a-z0-9]+)+$")
REPORT_PATTERN = re.compile(r"^rpt_[a-z0-9]+(?:_[a-z0-9]+)+$")


class ValidationError(Exception):
    pass


def _expect_file(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"Missing required file: {path.relative_to(ROOT)}")


def _expect_dir(path: Path, errors: list[str]) -> None:
    if not path.is_dir():
        errors.append(f"Missing required directory: {path.relative_to(ROOT)}")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _validate_required_structure(errors: list[str]) -> None:
    _expect_dir(POWERBI_DIR / "domains", errors)
    _expect_file(DEPLOY_DIR / "workspace-map.yaml", errors)
    _expect_file(DEPLOY_DIR / "pipeline-rules.yaml", errors)


def _validate_domain_naming(errors: list[str]) -> None:
    domains_dir = POWERBI_DIR / "domains"
    if not domains_dir.exists():
        return

    for domain_dir in sorted([p for p in domains_dir.iterdir() if p.is_dir()]):
        semantic_dir = domain_dir / "semantic-model"
        reports_dir = domain_dir / "reports"
        _expect_dir(semantic_dir, errors)
        _expect_dir(reports_dir, errors)

        if semantic_dir.is_dir():
            for child in semantic_dir.iterdir():
                if child.name.startswith("README"):
                    continue
                if not child.is_dir():
                    continue
                if not SEMANTIC_MODEL_PATTERN.match(child.name):
                    errors.append(
                        f"Invalid semantic model folder name '{child.name}' in "
                        f"{semantic_dir.relative_to(ROOT)}"
                    )

        if reports_dir.is_dir():
            for child in reports_dir.iterdir():
                if child.name.startswith("README"):
                    continue
                if not child.is_dir():
                    continue
                if not REPORT_PATTERN.match(child.name):
                    errors.append(
                        f"Invalid report folder name '{child.name}' in "
                        f"{reports_dir.relative_to(ROOT)}"
                    )


def _validate_workspace_map_consistency(errors: list[str]) -> None:
    workspace_map = DEPLOY_DIR / "workspace-map.yaml"
    pipeline_rules = DEPLOY_DIR / "pipeline-rules.yaml"
    if not workspace_map.exists() or not pipeline_rules.exists():
        return

    wm_text = _read_text(workspace_map)
    pr_text = _read_text(pipeline_rules)

    expected_tokens = [
        "pbi-dpb-dev-core",
        "pbi-dpb-test-core",
        "pbi-dpb-prod-core",
        "dpb-core-bi",
    ]
    for token in expected_tokens:
        if token not in wm_text:
            errors.append(f"workspace-map.yaml missing token: {token}")
        if token not in pr_text:
            errors.append(f"pipeline-rules.yaml missing token: {token}")


def main() -> int:
    errors: list[str] = []
    _validate_required_structure(errors)
    _validate_domain_naming(errors)
    _validate_workspace_map_consistency(errors)

    if errors:
        print("PBIP validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PBIP validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
