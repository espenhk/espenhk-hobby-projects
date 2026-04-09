"""Example Nordic sales data product with Bronze, Silver, and Gold transforms.

The transformation flow is intentionally small but non-trivial:
- Bronze: parse raw CSV rows and quarantine obviously bad records
- Silver: deduplicate order lines, attach FX rates, compute NOK amounts
- Gold: aggregate to a monthly mart for Power BI import
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

TWOPLACES = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _to_decimal(value: str | None, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        return default
    return Decimal(str(value))


def load_orders_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_fx_rates_csv(path: str | Path) -> dict[tuple[str, str], Decimal]:
    rows: dict[tuple[str, str], Decimal] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows[(row["rate_date"], row["currency_code"])] = Decimal(row["nok_rate"])
    return rows


def to_bronze_orders(raw_rows: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    bronze_rows: list[dict] = []
    quarantine_rows: list[dict] = []

    for row_number, row in enumerate(raw_rows, start=1):
        reasons: list[str] = []
        try:
            order_ts = datetime.fromisoformat(row["order_ts"])
        except (KeyError, TypeError, ValueError):
            reasons.append("invalid_order_ts")
            order_ts = None

        try:
            quantity = int(row["quantity"])
        except (KeyError, TypeError, ValueError):
            reasons.append("invalid_quantity")
            quantity = None

        try:
            unit_price_local = _to_decimal(row.get("unit_price_local"))
        except Exception:
            reasons.append("invalid_unit_price")
            unit_price_local = None

        try:
            discount_pct = _to_decimal(row.get("discount_pct"), Decimal("0"))
        except Exception:
            reasons.append("invalid_discount_pct")
            discount_pct = None

        currency_code = (row.get("currency_code") or "").strip()
        if not currency_code:
            reasons.append("missing_currency_code")
        if quantity is not None and quantity <= 0:
            reasons.append("non_positive_quantity")
        if unit_price_local is not None and unit_price_local <= 0:
            reasons.append("non_positive_unit_price")
        if discount_pct is not None and (discount_pct < 0 or discount_pct > 1):
            reasons.append("discount_pct_out_of_range")

        normalized = {
            "order_id": row.get("order_id", "").strip(),
            "order_line_id": row.get("order_line_id", "").strip(),
            "order_ts": order_ts,
            "country_code": row.get("country_code", "").strip(),
            "product_category": row.get("product_category", "").strip(),
            "quantity": quantity,
            "unit_price_local": unit_price_local,
            "currency_code": currency_code,
            "discount_pct": discount_pct,
            "source_row_number": row_number,
        }

        if reasons or not normalized["order_line_id"]:
            if not normalized["order_line_id"]:
                reasons.append("missing_order_line_id")
            quarantine_rows.append(
                {
                    **normalized,
                    "quarantine_reason": ",".join(sorted(set(reasons))),
                }
            )
            continue

        bronze_rows.append(normalized)

    return bronze_rows, quarantine_rows


def to_silver_sales_lines(
    bronze_rows: list[dict],
    fx_rates: dict[tuple[str, str], Decimal],
) -> tuple[list[dict], list[dict]]:
    latest_by_line: dict[str, dict] = {}
    for row in bronze_rows:
        latest_by_line[row["order_line_id"]] = row

    silver_rows: list[dict] = []
    quarantine_rows: list[dict] = []

    for row in latest_by_line.values():
        order_date = row["order_ts"].date().isoformat()
        fx_key = (order_date, row["currency_code"])
        fx_rate = fx_rates.get(fx_key)
        if fx_rate is None:
            quarantine_rows.append({**row, "quarantine_reason": "missing_fx_rate"})
            continue

        gross_amount_local = _money(Decimal(row["quantity"]) * row["unit_price_local"])
        discount_amount_local = _money(gross_amount_local * row["discount_pct"])
        net_amount_local = _money(gross_amount_local - discount_amount_local)

        gross_amount_nok = _money(gross_amount_local * fx_rate)
        discount_amount_nok = _money(discount_amount_local * fx_rate)
        net_amount_nok = _money(net_amount_local * fx_rate)

        silver_rows.append(
            {
                "order_id": row["order_id"],
                "order_line_id": row["order_line_id"],
                "order_date": order_date,
                "order_month": order_date[:7],
                "country_code": row["country_code"],
                "product_category": row["product_category"],
                "currency_code": row["currency_code"],
                "quantity": row["quantity"],
                "fx_rate_to_nok": fx_rate,
                "gross_amount_local": gross_amount_local,
                "discount_amount_local": discount_amount_local,
                "net_amount_local": net_amount_local,
                "gross_amount_nok": gross_amount_nok,
                "discount_amount_nok": discount_amount_nok,
                "net_amount_nok": net_amount_nok,
            }
        )

    silver_rows.sort(key=lambda item: item["order_line_id"])
    quarantine_rows.sort(key=lambda item: item["order_line_id"])
    return silver_rows, quarantine_rows


def to_gold_sales_monthly_nok(silver_rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict] = {}

    for row in silver_rows:
        key = (row["order_month"], row["country_code"], row["product_category"])
        current = grouped.setdefault(
            key,
            {
                "order_month": row["order_month"],
                "country_code": row["country_code"],
                "product_category": row["product_category"],
                "order_ids": set(),
                "units_sold": 0,
                "gross_sales_nok": Decimal("0.00"),
                "discount_amount_nok": Decimal("0.00"),
                "net_sales_nok": Decimal("0.00"),
            },
        )
        current["order_ids"].add(row["order_id"])
        current["units_sold"] += row["quantity"]
        current["gross_sales_nok"] += row["gross_amount_nok"]
        current["discount_amount_nok"] += row["discount_amount_nok"]
        current["net_sales_nok"] += row["net_amount_nok"]

    gold_rows: list[dict] = []
    for current in grouped.values():
        order_count = len(current["order_ids"])
        net_sales_nok = _money(current["net_sales_nok"])
        gold_rows.append(
            {
                "order_month": current["order_month"],
                "country_code": current["country_code"],
                "product_category": current["product_category"],
                "order_count": order_count,
                "units_sold": current["units_sold"],
                "gross_sales_nok": _money(current["gross_sales_nok"]),
                "discount_amount_nok": _money(current["discount_amount_nok"]),
                "net_sales_nok": net_sales_nok,
                "avg_order_value_nok": _money(net_sales_nok / Decimal(order_count)),
            }
        )

    gold_rows.sort(key=lambda item: (item["order_month"], item["country_code"], item["product_category"]))
    return gold_rows


def run_pipeline(orders_path: str | Path, fx_rates_path: str | Path) -> dict[str, list[dict]]:
    raw_orders = load_orders_csv(orders_path)
    fx_rates = load_fx_rates_csv(fx_rates_path)
    bronze_rows, bronze_quarantine = to_bronze_orders(raw_orders)
    silver_rows, silver_quarantine = to_silver_sales_lines(bronze_rows, fx_rates)
    gold_rows = to_gold_sales_monthly_nok(silver_rows)
    return {
        "bronze_rows": bronze_rows,
        "bronze_quarantine": bronze_quarantine,
        "silver_rows": silver_rows,
        "silver_quarantine": silver_quarantine,
        "gold_rows": gold_rows,
    }


def _serialize_rows(rows: list[dict]) -> list[dict]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the example Nordic sales NOK ETL pipeline.")
    parser.add_argument("--orders", required=True, help="Path to raw orders CSV")
    parser.add_argument("--fx-rates", required=True, help="Path to FX rates CSV")
    parser.add_argument("--output", help="Optional path for Gold output JSON")
    args = parser.parse_args()

    result = run_pipeline(args.orders, args.fx_rates)
    gold_rows = _serialize_rows(result["gold_rows"])

    if args.output:
        Path(args.output).write_text(json.dumps(gold_rows, indent=2), encoding="utf-8")
    else:
        print(json.dumps(gold_rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())