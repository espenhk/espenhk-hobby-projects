from __future__ import annotations

import argparse
import logging
from decimal import Decimal

from dataplatform_beta.example_products.core_nordic_sales_nok_common import (
    build_fx_lookup,
    configure_logging,
    deserialize_bronze_rows,
    money,
    read_json,
    serialize_rows,
    write_json,
)

LOGGER = logging.getLogger(__name__)


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

        gross_amount_local = money(Decimal(row["quantity"]) * row["unit_price_local"])
        discount_amount_local = money(gross_amount_local * row["discount_pct"])
        net_amount_local = money(gross_amount_local - discount_amount_local)

        gross_amount_nok = money(gross_amount_local * fx_rate)
        discount_amount_nok = money(discount_amount_local * fx_rate)
        net_amount_nok = money(net_amount_local * fx_rate)

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


def main() -> int:
    configure_logging()

    parser = argparse.ArgumentParser(description="Transform Bronze Nordic sales data into Silver artifacts.")
    parser.add_argument("--bronze-input", required=True, help="Path to Bronze JSON input")
    parser.add_argument("--raw-fx-input", required=True, help="Path to raw FX JSON input")
    parser.add_argument("--silver-output", required=True, help="Path to Silver JSON output")
    parser.add_argument("--quarantine-output", required=True, help="Path to Silver quarantine JSON output")
    args = parser.parse_args()

    bronze_rows = deserialize_bronze_rows(read_json(args.bronze_input))
    raw_fx_rows = read_json(args.raw_fx_input)
    silver_rows, quarantine_rows = to_silver_sales_lines(bronze_rows, build_fx_lookup(raw_fx_rows))

    write_json(args.silver_output, serialize_rows(silver_rows))
    write_json(args.quarantine_output, serialize_rows(quarantine_rows))

    LOGGER.info(
        "Silver stage wrote %d clean rows and %d quarantined rows",
        len(silver_rows),
        len(quarantine_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())