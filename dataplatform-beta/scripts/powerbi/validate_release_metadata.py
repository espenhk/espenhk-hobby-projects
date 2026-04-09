#!/usr/bin/env python3
"""Validate release metadata required for production promotion."""

from __future__ import annotations

import os
import re
import sys

TICKET_PATTERN = re.compile(r"^(CHG|RFC)-[0-9]{3,}$")


def main() -> int:
    ticket = os.environ.get("PBI_CHANGE_TICKET", "").strip()
    if not ticket:
        print("Missing PBI_CHANGE_TICKET environment variable", file=sys.stderr)
        return 2

    if not TICKET_PATTERN.match(ticket):
        print(
            "Invalid PBI_CHANGE_TICKET format. Expected CHG-<digits> or RFC-<digits>",
            file=sys.stderr,
        )
        return 3

    print(f"Release metadata validated for ticket: {ticket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
