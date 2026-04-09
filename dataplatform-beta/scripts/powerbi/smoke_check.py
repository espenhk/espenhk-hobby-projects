#!/usr/bin/env python3
"""Run lightweight Power BI smoke checks after deployment."""

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


def verify_workspace(workspace_id: str, token: str) -> None:
    data = _request("GET", f"/groups/{workspace_id}", token)
    print(f"Workspace reachable: {data.get('name', workspace_id)}")


def trigger_dataset_refresh(workspace_id: str, dataset_id: str, token: str) -> None:
    _request("POST", f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes", token, {})
    print(f"Triggered dataset refresh: {dataset_id}")


def verify_report(workspace_id: str, report_id: str, token: str) -> None:
    data = _request("GET", f"/groups/{workspace_id}/reports/{report_id}", token)
    print(f"Report reachable: {data.get('name', report_id)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Power BI smoke checks")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--dataset-id")
    parser.add_argument("--report-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("PBI_ACCESS_TOKEN")
    if not token:
        print("Missing PBI_ACCESS_TOKEN environment variable", file=sys.stderr)
        return 2

    verify_workspace(args.workspace_id, token)
    if args.dataset_id:
        trigger_dataset_refresh(args.workspace_id, args.dataset_id, token)
    if args.report_id:
        verify_report(args.workspace_id, args.report_id, token)
    print("Smoke checks completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
