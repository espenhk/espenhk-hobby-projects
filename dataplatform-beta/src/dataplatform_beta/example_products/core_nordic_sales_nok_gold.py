from __future__ import annotations

import argparse
import logging
from decimal import Decimal

from dataplatform_beta.example_products.core_nordic_sales_nok_common import (
    configure_logging,
    deserialize_silver_rows,
    money,
    read_json,
    serialize_rows,
    write_json,
)

LOGGER = logging.getLogger(__name__)


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
        net_sales_nok = money(current["net_sales_nok"])
        gold_rows.append(
            {
                "order_month": current["order_month"],
                "country_code": current["country_code"],
                "product_category": current["product_category"],
                "order_count": order_count,
                "units_sold": current["units_sold"],
                "gross_sales_nok": money(current["gross_sales_nok"]),
                "discount_amount_nok": money(current["discount_amount_nok"]),
                "net_sales_nok": net_sales_nok,
                "avg_order_value_nok": money(net_sales_nok / Decimal(order_count)),
            }
        )

    gold_rows.sort(key=lambda item: (item["order_month"], item["country_code"], item["product_category"]))
    return gold_rows


def main() -> int:
    configure_logging()

    parser = argparse.ArgumentParser(description="Transform Silver Nordic sales data into Gold artifacts.")
    parser.add_argument("--silver-input", required=True, help="Path to Silver JSON input")
    parser.add_argument("--output", required=True, help="Path to Gold JSON output")
    args = parser.parse_args()

    silver_rows = deserialize_silver_rows(read_json(args.silver_input))
    gold_rows = to_gold_sales_monthly_nok(silver_rows)
    write_json(args.output, serialize_rows(gold_rows))

    LOGGER.info("Gold stage wrote %d curated rows", len(gold_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())