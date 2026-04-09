#!/usr/bin/env python3
"""Validate JSON data contract files for dataplatform-beta."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT / "databricks" / "contracts"
REQUIRED_TOP_LEVEL = {
    "contractVersion",
    "dataset",
    "owner",
    "description",
    "schema",
    "keys",
    "freshness",
    "qualityChecks",
}
REQUIRED_SCHEMA_FIELDS = {"name", "type", "nullable"}
ALLOWED_TYPES = {
    "string",
    "integer",
    "long",
    "double",
    "boolean",
    "date",
    "timestamp",
}


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_contract(path: Path, payload: dict) -> list[str]:
    errors: list[str] = []

    missing_top = REQUIRED_TOP_LEVEL - set(payload)
    if missing_top:
        errors.append(f"missing top-level keys: {sorted(missing_top)}")
        return errors

    if payload.get("contractVersion") != "1.0":
        errors.append("contractVersion must be '1.0'")

    schema = payload.get("schema")
    if not isinstance(schema, list) or not schema:
        errors.append("schema must be a non-empty list")
    else:
        field_names: set[str] = set()
        for idx, field in enumerate(schema):
            if not isinstance(field, dict):
                errors.append(f"schema[{idx}] must be an object")
                continue
            missing_field_keys = REQUIRED_SCHEMA_FIELDS - set(field)
            if missing_field_keys:
                errors.append(
                    f"schema[{idx}] missing keys: {sorted(missing_field_keys)}"
                )
                continue
            name = field["name"]
            if name in field_names:
                errors.append(f"duplicate schema field name: {name}")
            field_names.add(name)
            if field["type"] not in ALLOWED_TYPES:
                errors.append(
                    f"schema[{idx}].type '{field['type']}' not in {sorted(ALLOWED_TYPES)}"
                )
            if not isinstance(field["nullable"], bool):
                errors.append(f"schema[{idx}].nullable must be a boolean")

    keys = payload.get("keys")
    if not isinstance(keys, dict):
        errors.append("keys must be an object")
    else:
        for required in ["primaryKey", "deduplicationKey"]:
            if required not in keys:
                errors.append(f"keys.{required} is required")

    freshness = payload.get("freshness")
    if not isinstance(freshness, dict):
        errors.append("freshness must be an object")
    else:
        for required in ["targetMinutes", "lateDataPolicy"]:
            if required not in freshness:
                errors.append(f"freshness.{required} is required")

    quality_checks = payload.get("qualityChecks")
    if not isinstance(quality_checks, list) or not quality_checks:
        errors.append("qualityChecks must be a non-empty list")

    return errors


def main() -> int:
    contract_files = sorted(CONTRACTS_DIR.rglob("*.contract.json"))
    if not contract_files:
        print("No contract files found under databricks/contracts", file=sys.stderr)
        return 1

    failures = 0
    for contract in contract_files:
        try:
            payload = _load(contract)
        except json.JSONDecodeError as exc:
            print(f"{contract.relative_to(ROOT)}: invalid JSON ({exc})")
            failures += 1
            continue

        errors = _validate_contract(contract, payload)
        if errors:
            failures += 1
            print(f"{contract.relative_to(ROOT)}: validation failed")
            for item in errors:
                print(f"  - {item}")
        else:
            print(f"{contract.relative_to(ROOT)}: ok")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
