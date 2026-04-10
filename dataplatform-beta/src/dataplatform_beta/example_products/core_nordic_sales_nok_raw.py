from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

from dataplatform_beta.example_products.core_nordic_sales_nok_common import configure_logging, write_json

LOGGER = logging.getLogger(__name__)


def load_orders_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_fx_rates_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run_raw_stage(orders_path: str | Path, fx_rates_path: str | Path) -> dict[str, list[dict[str, str]]]:
    return {
        "raw_orders": load_orders_csv(orders_path),
        "raw_fx_rates": load_fx_rates_csv_rows(fx_rates_path),
    }


def main() -> int:
    configure_logging()

    parser = argparse.ArgumentParser(description="Extract raw Nordic sales inputs into staged JSON artifacts.")
    parser.add_argument("--orders", required=True, help="Path to raw orders CSV")
    parser.add_argument("--fx-rates", required=True, help="Path to FX rates CSV")
    parser.add_argument("--output-dir", required=True, help="Directory for raw staged JSON outputs")
    args = parser.parse_args()

    result = run_raw_stage(args.orders, args.fx_rates)
    output_dir = Path(args.output_dir)
    write_json(output_dir / "raw_orders.json", result["raw_orders"])
    write_json(output_dir / "raw_fx_rates.json", result["raw_fx_rates"])

    LOGGER.info(
        "Raw stage wrote %d order rows and %d FX rows into %s",
        len(result["raw_orders"]),
        len(result["raw_fx_rates"]),
        output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())