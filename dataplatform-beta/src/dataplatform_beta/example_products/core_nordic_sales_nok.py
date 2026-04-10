"""Compatibility facade for the staged Nordic sales example ETL.

The implementation lives in stage-specific modules for raw, bronze, silver, and gold,
while this module preserves the original `run_pipeline` and CLI entrypoint contract.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from dataplatform_beta.example_products.core_nordic_sales_nok_bronze import to_bronze_orders
from dataplatform_beta.example_products.core_nordic_sales_nok_common import build_fx_lookup
from dataplatform_beta.example_products.core_nordic_sales_nok_common import configure_logging, serialize_rows
from dataplatform_beta.example_products.core_nordic_sales_nok_gold import to_gold_sales_monthly_nok
from dataplatform_beta.example_products.core_nordic_sales_nok_raw import run_raw_stage
from dataplatform_beta.example_products.core_nordic_sales_nok_silver import to_silver_sales_lines

LOGGER = logging.getLogger(__name__)


def _execute_pipeline(raw_stage: dict[str, list[dict]]) -> dict[str, list[dict]]:
    bronze_rows, bronze_quarantine = to_bronze_orders(raw_stage["raw_orders"])
    silver_rows, silver_quarantine = to_silver_sales_lines(
        bronze_rows,
        build_fx_lookup(raw_stage["raw_fx_rates"]),
    )
    gold_rows = to_gold_sales_monthly_nok(silver_rows)
    return {
        "bronze_rows": bronze_rows,
        "bronze_quarantine": bronze_quarantine,
        "silver_rows": silver_rows,
        "silver_quarantine": silver_quarantine,
        "gold_rows": gold_rows,
    }


def run_pipeline(orders_path: str | Path, fx_rates_path: str | Path) -> dict[str, list[dict]]:
    return _execute_pipeline(run_raw_stage(orders_path, fx_rates_path))


def main() -> int:
    configure_logging()

    parser = argparse.ArgumentParser(description="Run the example Nordic sales NOK ETL pipeline.")
    parser.add_argument("--orders", required=True, help="Path to raw orders CSV")
    parser.add_argument("--fx-rates", required=True, help="Path to FX rates CSV")
    parser.add_argument("--output", help="Optional path for Gold output JSON")
    args = parser.parse_args()

    raw_stage = run_raw_stage(args.orders, args.fx_rates)
    result = _execute_pipeline(raw_stage)
    gold_rows_raw = result["gold_rows"]

    LOGGER.info(
        "Processed %d raw rows -> %d bronze, %d silver, %d gold (%d bronze quarantine, %d silver quarantine)",
        len(raw_stage["raw_orders"]),
        len(result["bronze_rows"]),
        len(result["silver_rows"]),
        len(gold_rows_raw),
        len(result["bronze_quarantine"]),
        len(result["silver_quarantine"]),
    )

    gold_rows = serialize_rows(gold_rows_raw)

    if args.output:
        Path(args.output).write_text(json.dumps(gold_rows, indent=2), encoding="utf-8")
        LOGGER.info("Wrote %d Gold rows to %s", len(gold_rows), args.output)
    else:
        LOGGER.info("No --output path provided; emitting Gold rows to stdout")
        print(json.dumps(gold_rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())