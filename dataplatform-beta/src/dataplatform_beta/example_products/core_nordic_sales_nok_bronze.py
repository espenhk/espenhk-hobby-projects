from __future__ import annotations

import argparse
import logging

from dataplatform_beta.example_products.core_nordic_sales_nok_common import read_json, serialize_rows, to_decimal, write_json

LOGGER = logging.getLogger(__name__)


def to_bronze_orders(raw_rows: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    from datetime import datetime

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
            unit_price_local = to_decimal(row.get("unit_price_local"))
        except Exception:
            reasons.append("invalid_unit_price")
            unit_price_local = None

        try:
            discount_pct = to_decimal(row.get("discount_pct"), default=to_decimal("0"))
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
            quarantine_rows.append({**normalized, "quarantine_reason": ",".join(sorted(set(reasons)))})
            continue

        bronze_rows.append(normalized)

    return bronze_rows, quarantine_rows


def main() -> int:
    from dataplatform_beta.example_products.core_nordic_sales_nok_common import configure_logging

    configure_logging()

    parser = argparse.ArgumentParser(description="Transform raw Nordic sales data into Bronze artifacts.")
    parser.add_argument("--raw-orders-input", required=True, help="Path to raw_orders.json")
    parser.add_argument("--bronze-output", required=True, help="Path to Bronze JSON output")
    parser.add_argument("--quarantine-output", required=True, help="Path to Bronze quarantine JSON output")
    args = parser.parse_args()

    raw_orders = read_json(args.raw_orders_input)
    bronze_rows, quarantine_rows = to_bronze_orders(raw_orders)
    write_json(args.bronze_output, serialize_rows(bronze_rows))
    write_json(args.quarantine_output, serialize_rows(quarantine_rows))

    LOGGER.info(
        "Bronze stage wrote %d clean rows and %d quarantined rows",
        len(bronze_rows),
        len(quarantine_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())