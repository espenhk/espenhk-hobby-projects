from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

TWOPLACES = Decimal("0.01")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def to_decimal(value: str | None, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        return default
    return Decimal(str(value))


def serialize_rows(rows: list[dict]) -> list[dict]:
    serialized: list[dict] = []
    for row in rows:
        normalized = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                normalized[key] = format(value, ".2f")
            elif isinstance(value, set):
                normalized[key] = sorted(value)
            elif hasattr(value, "isoformat"):
                normalized[key] = value.isoformat()
            else:
                normalized[key] = value
        serialized.append(normalized)
    return serialized


def write_json(path: str | Path, payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def deserialize_bronze_rows(rows: list[dict]) -> list[dict]:
    deserialized: list[dict] = []
    for row in rows:
        deserialized.append(
            {
                **row,
                "order_ts": datetime.fromisoformat(row["order_ts"]) if row.get("order_ts") else None,
                "quantity": int(row["quantity"]) if row.get("quantity") is not None else None,
                "unit_price_local": Decimal(row["unit_price_local"]) if row.get("unit_price_local") not in (None, "") else None,
                "discount_pct": Decimal(row["discount_pct"]) if row.get("discount_pct") not in (None, "") else None,
                "source_row_number": int(row["source_row_number"]) if row.get("source_row_number") is not None else None,
            }
        )
    return deserialized


def deserialize_silver_rows(rows: list[dict]) -> list[dict]:
    deserialized: list[dict] = []
    decimal_fields = {
        "fx_rate_to_nok",
        "gross_amount_local",
        "discount_amount_local",
        "net_amount_local",
        "gross_amount_nok",
        "discount_amount_nok",
        "net_amount_nok",
    }
    for row in rows:
        deserialized.append(
            {
                key: (Decimal(value) if key in decimal_fields and value not in (None, "") else value)
                for key, value in row.items()
            }
        )
    for row in deserialized:
        row["quantity"] = int(row["quantity"])
    return deserialized


def build_fx_lookup(raw_fx_rows: list[dict[str, str]]) -> dict[tuple[str, str], Decimal]:
    return {
        (row["rate_date"], row["currency_code"]): Decimal(row["nok_rate"])
        for row in raw_fx_rows
    }