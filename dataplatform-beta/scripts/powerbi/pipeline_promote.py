#!/usr/bin/env python3
"""Promote artifacts across Power BI deployment pipeline stages."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.powerbi.com/v1.0/myorg"


def _request(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Power BI API error {exc.code}: {body}", file=sys.stderr)
        raise


def promote(pipeline_id: str, source_stage_order: int, target_stage_order: int, token: str) -> None:
    payload = {
        "sourceStageOrder": source_stage_order,
        "targetStageOrder": target_stage_order,
        "options": {
            "allowCreateArtifact": True,
            "allowOverwriteArtifact": True,
        },
    }
    _request("POST", f"/pipelines/{pipeline_id}/deployAll", token, payload)
    print(
        f"Triggered deployment pipeline promotion: "
        f"pipeline={pipeline_id}, source={source_stage_order}, target={target_stage_order}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote Power BI pipeline stage")
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--source-stage-order", required=True, type=int)
    parser.add_argument("--target-stage-order", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("PBI_ACCESS_TOKEN")
    if not token:
        print("Missing PBI_ACCESS_TOKEN environment variable", file=sys.stderr)
        return 2

    promote(
        pipeline_id=args.pipeline_id,
        source_stage_order=args.source_stage_order,
        target_stage_order=args.target_stage_order,
        token=token,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
