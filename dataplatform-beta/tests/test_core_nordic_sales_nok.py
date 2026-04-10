import unittest
from pathlib import Path

from dataplatform_beta.example_products.core_nordic_sales_nok_bronze import to_bronze_orders
from dataplatform_beta.example_products.core_nordic_sales_nok_common import (
    build_fx_lookup,
    deserialize_bronze_rows,
    deserialize_silver_rows,
    serialize_rows,
)
from dataplatform_beta.example_products.core_nordic_sales_nok_gold import to_gold_sales_monthly_nok
from dataplatform_beta.example_products.core_nordic_sales_nok_raw import run_raw_stage
from dataplatform_beta.example_products.core_nordic_sales_nok_silver import to_silver_sales_lines
from dataplatform_beta.example_products.core_nordic_sales_nok import run_pipeline


def _stringify_money(rows):
    normalized = []
    for row in rows:
        normalized.append(
            {
                key: (format(value, ".2f") if hasattr(value, "quantize") else value)
                for key, value in row.items()
            }
        )
    return normalized


class TestCoreNordicSalesNok(unittest.TestCase):
    def setUp(self):
        sample_dir = (
            Path(__file__).resolve().parents[1]
            / "databricks"
            / "sample_data"
            / "core_nordic_sales_nok"
        )
        self.result = run_pipeline(
            sample_dir / "orders.csv",
            sample_dir / "fx_rates_to_nok.csv",
        )

    def test_bronze_quarantines_invalid_raw_rows(self):
        quarantined = {
            row["order_line_id"]: row["quarantine_reason"]
            for row in self.result["bronze_quarantine"]
        }
        self.assertEqual(quarantined["L1005"], "non_positive_quantity")
        self.assertEqual(quarantined["L1006"], "missing_currency_code")

    def test_silver_deduplicates_and_computes_nok_amounts(self):
        silver_by_line = {
            row["order_line_id"]: row for row in self.result["silver_rows"]
        }
        helmets_line = silver_by_line["L1002"]

        self.assertEqual(helmets_line["quantity"], 1)
        self.assertEqual(format(helmets_line["gross_amount_local"], ".2f"), "950.00")
        self.assertEqual(format(helmets_line["discount_amount_local"], ".2f"), "47.50")
        self.assertEqual(format(helmets_line["net_amount_nok"], ".2f"), "866.40")

    def test_silver_quarantines_missing_fx_rates(self):
        quarantined = {
            row["order_line_id"]: row["quarantine_reason"]
            for row in self.result["silver_quarantine"]
        }
        self.assertEqual(quarantined, {"L1007": "missing_fx_rate"})

    def test_gold_output_matches_expected_monthly_nok_rows(self):
        expected = [
            {
                "order_month": "2026-01",
                "country_code": "NO",
                "product_category": "Skates",
                "order_count": 1,
                "units_sold": 2,
                "gross_sales_nok": "2400.00",
                "discount_amount_nok": "240.00",
                "net_sales_nok": "2160.00",
                "avg_order_value_nok": "2160.00",
            },
            {
                "order_month": "2026-01",
                "country_code": "SE",
                "product_category": "Helmets",
                "order_count": 1,
                "units_sold": 1,
                "gross_sales_nok": "912.00",
                "discount_amount_nok": "45.60",
                "net_sales_nok": "866.40",
                "avg_order_value_nok": "866.40",
            },
            {
                "order_month": "2026-02",
                "country_code": "DK",
                "product_category": "Apparel",
                "order_count": 1,
                "units_sold": 3,
                "gross_sales_nok": "1162.50",
                "discount_amount_nok": "0.00",
                "net_sales_nok": "1162.50",
                "avg_order_value_nok": "1162.50",
            },
            {
                "order_month": "2026-02",
                "country_code": "FI",
                "product_category": "Skates",
                "order_count": 1,
                "units_sold": 1,
                "gross_sales_nok": "1755.00",
                "discount_amount_nok": "351.00",
                "net_sales_nok": "1404.00",
                "avg_order_value_nok": "1404.00",
            },
        ]

        self.assertEqual(_stringify_money(self.result["gold_rows"]), expected)

    def test_split_stage_modules_round_trip_across_json_boundaries(self):
        sample_dir = (
            Path(__file__).resolve().parents[1]
            / "databricks"
            / "sample_data"
            / "core_nordic_sales_nok"
        )

        raw_stage = run_raw_stage(
            sample_dir / "orders.csv",
            sample_dir / "fx_rates_to_nok.csv",
        )
        bronze_rows, _ = to_bronze_orders(raw_stage["raw_orders"])
        bronze_round_trip = deserialize_bronze_rows(serialize_rows(bronze_rows))

        silver_rows, _ = to_silver_sales_lines(
            bronze_round_trip,
            build_fx_lookup(raw_stage["raw_fx_rates"]),
        )
        silver_round_trip = deserialize_silver_rows(serialize_rows(silver_rows))
        gold_rows = to_gold_sales_monthly_nok(silver_round_trip)

        self.assertEqual(
            _stringify_money(gold_rows),
            _stringify_money(self.result["gold_rows"]),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)