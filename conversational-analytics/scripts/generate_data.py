#!/usr/bin/env python3
"""Generate ~2 years of synthetic Fjord Roast point-of-sale data.

Writes a Kimball star schema (fact_sales + four dimensions) as Parquet
files under ../data/, so the rest of the project can run fully offline.
Deterministic: re-running with the same DATE_START/DATE_END/SEED always
reproduces byte-identical output.

Run with:  python scripts/generate_data.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20240101
DATE_START = dt.date(2024, 1, 1)
DATE_END = dt.date(2025, 12, 31)
OUT_DIR = Path(__file__).resolve().parent.parent / "data"

rng = np.random.default_rng(SEED)


# --------------------------------------------------------------------------
# dim_store
# --------------------------------------------------------------------------

STORES = [
    # store_id, store_name,              city,        opening_date,          seating, base_receipts/day
    ("ST01", "Tromsø Sentrum", "Tromsø", dt.date(2018, 3, 1), 34, 52),
    ("ST02", "Tromsø Nord", "Tromsø", dt.date(2021, 9, 15), 22, 30),
    ("ST03", "Bergen Bryggen", "Bergen", dt.date(2016, 6, 1), 40, 58),
    ("ST04", "Bergen Torgallmenningen", "Bergen", dt.date(2019, 11, 1), 28, 38),
    ("ST05", "Oslo Sentrum", "Oslo", dt.date(2015, 1, 10), 46, 65),
    ("ST06", "Trondheim Solsiden", "Trondheim", dt.date(2020, 4, 20), 30, 40),
]


def build_dim_store() -> pd.DataFrame:
    df = pd.DataFrame(
        STORES,
        columns=["store_id", "store_name", "city", "opening_date", "seating_capacity", "_base_receipts"],
    )
    df["opening_date"] = pd.to_datetime(df["opening_date"])
    return df


# --------------------------------------------------------------------------
# dim_product
# --------------------------------------------------------------------------

# name, category, size, unit_cost, unit_price
PRODUCTS = [
    ("Espresso", "Coffee", "Small", 6.0, 32.0),
    ("Americano", "Coffee", "Medium", 8.0, 42.0),
    ("Americano", "Coffee", "Large", 9.5, 48.0),
    ("Cappuccino", "Coffee", "Medium", 10.5, 48.0),
    ("Cappuccino", "Coffee", "Large", 12.0, 54.0),
    ("Latte", "Coffee", "Medium", 11.0, 49.0),
    ("Latte", "Coffee", "Large", 12.5, 55.0),
    ("Flat White", "Coffee", "Medium", 11.0, 50.0),
    ("Mocha", "Coffee", "Medium", 12.5, 55.0),
    ("Black Tea", "Tea", "Medium", 6.5, 38.0),
    ("Green Tea", "Tea", "Medium", 6.5, 38.0),
    ("Chai Latte", "Tea", "Medium", 10.5, 48.0),
    ("Iced Coffee", "Cold Drink", "Medium", 10.5, 46.0),
    ("Iced Latte", "Cold Drink", "Medium", 12.0, 52.0),
    ("Cold Brew", "Cold Drink", "Medium", 11.5, 50.0),
    ("Lemonade", "Cold Drink", "Medium", 8.0, 40.0),
    ("Berry Smoothie", "Cold Drink", "Medium", 14.0, 58.0),
    ("Cinnamon Bun", "Food", "N/A", 9.0, 45.0),
    ("Croissant", "Food", "N/A", 8.0, 38.0),
    ("Carrot Cake", "Food", "N/A", 11.0, 52.0),
    ("Sandwich", "Food", "N/A", 18.0, 79.0),
    ("Waffle", "Food", "N/A", 9.5, 49.0),
    ("House Blend Beans 250g", "Retail Bean", "N/A", 38.0, 129.0),
    ("Dark Roast Beans 250g", "Retail Bean", "N/A", 40.0, 135.0),
    ("Filter Roast Beans 500g", "Retail Bean", "N/A", 68.0, 219.0),
]


def build_dim_product() -> pd.DataFrame:
    df = pd.DataFrame(PRODUCTS, columns=["name", "category", "size", "unit_cost", "unit_price"])
    df.insert(0, "product_id", [f"P{i+1:03d}" for i in range(len(df))])
    return df


# --------------------------------------------------------------------------
# dim_date  (with Norwegian public holidays)
# --------------------------------------------------------------------------


def _easter_sunday(year: int) -> dt.date:
    """Meeus/Jones/Butcher Gregorian Easter algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 -- matches the reference algorithm's naming
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def _norwegian_holidays(year: int) -> dict[dt.date, str]:
    easter = _easter_sunday(year)
    holidays = {
        dt.date(year, 1, 1): "Nyttårsdag",
        easter - dt.timedelta(days=3): "Skjærtorsdag",
        easter - dt.timedelta(days=2): "Langfredag",
        easter: "1. påskedag",
        easter + dt.timedelta(days=1): "2. påskedag",
        dt.date(year, 5, 1): "Arbeidernes dag",
        dt.date(year, 5, 17): "Grunnlovsdag",
        easter + dt.timedelta(days=39): "Kristi himmelfartsdag",
        easter + dt.timedelta(days=49): "1. pinsedag",
        easter + dt.timedelta(days=50): "2. pinsedag",
        dt.date(year, 12, 25): "1. juledag",
        dt.date(year, 12, 26): "2. juledag",
    }
    return holidays


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    return "Autumn"


def build_dim_date(start: dt.date, end: dt.date) -> pd.DataFrame:
    holidays: dict[dt.date, str] = {}
    for year in range(start.year, end.year + 1):
        holidays.update(_norwegian_holidays(year))

    dates = pd.date_range(start, end, freq="D")
    rows = []
    for d in dates:
        pydate = d.date()
        holiday_name = holidays.get(pydate, "")
        rows.append(
            {
                "date": d,
                "day_of_week": d.strftime("%A"),
                "is_weekend": d.dayofweek >= 5,
                "month": d.strftime("%B"),
                "quarter": f"Q{((d.month - 1) // 3) + 1}",
                "year": d.year,
                "season": _season(d.month),
                "is_holiday": pydate in holidays,
                "holiday_name": holiday_name,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# dim_member
# --------------------------------------------------------------------------

N_MEMBERS = 1400
TIER_WEIGHTS = {"None": 0.55, "Silver": 0.32, "Gold": 0.13}


def build_dim_member(dim_store: pd.DataFrame) -> pd.DataFrame:
    cities = dim_store["city"].unique().tolist()
    member_ids = [f"M{i+1:05d}" for i in range(N_MEMBERS)]
    tiers = rng.choice(list(TIER_WEIGHTS.keys()), size=N_MEMBERS, p=list(TIER_WEIGHTS.values()))
    home_cities = rng.choice(cities, size=N_MEMBERS)
    span_days = (DATE_END - DATE_START).days
    signup_offsets = rng.integers(0, span_days + 1, size=N_MEMBERS)
    signup_dates = [DATE_START + dt.timedelta(days=int(o)) for o in signup_offsets]
    return pd.DataFrame(
        {
            "member_id": member_ids,
            "loyalty_tier": tiers,
            "signup_date": pd.to_datetime(signup_dates),
            "home_city": home_cities,
        }
    )


# --------------------------------------------------------------------------
# fact_sales
# --------------------------------------------------------------------------

DRINK_CATEGORIES = ("Coffee", "Tea", "Cold Drink")

# Hour-of-day weights: morning peak (8-10), lunch peak (12-14), mild afternoon (15-16).
HOURS = list(range(7, 19))
HOUR_WEIGHTS = np.array(
    [1.0, 2.6, 3.4, 2.8, 1.6, 1.4, 2.2, 3.0, 2.4, 1.8, 1.5, 1.0]
)
HOUR_WEIGHTS = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()


def _season_category_weights(season: str) -> dict[str, float]:
    """Category selection weights, shifted by season: hot drinks favoured
    in winter, cold drinks bumped in summer."""
    base = {"Coffee": 0.46, "Tea": 0.12, "Cold Drink": 0.14, "Food": 0.20, "Retail Bean": 0.08}
    if season == "Winter":
        base["Coffee"] += 0.06
        base["Tea"] += 0.03
        base["Cold Drink"] -= 0.08
        base["Food"] += 0.01
        base["Retail Bean"] -= 0.02
    elif season == "Summer":
        base["Cold Drink"] += 0.16
        base["Coffee"] -= 0.10
        base["Tea"] -= 0.02
        base["Food"] -= 0.02
        base["Retail Bean"] -= 0.02
    total = sum(base.values())
    return {k: max(v, 0.01) / total for k, v in base.items()}


def _basket_size(tier: str, is_weekend: bool) -> int:
    base = 1 + rng.poisson(0.55)
    if is_weekend:
        base += rng.binomial(1, 0.25)
    if tier == "Gold":
        base += 1 + rng.binomial(1, 0.5)
    elif tier == "Silver":
        base += rng.binomial(1, 0.35)
    return int(min(max(base, 1), 6))


def generate_fact_sales(
    dim_store: pd.DataFrame, dim_product: pd.DataFrame, dim_member: pd.DataFrame, dim_date: pd.DataFrame
) -> pd.DataFrame:
    products_by_cat: dict[str, pd.DataFrame] = {
        cat: dim_product[dim_product["category"] == cat].reset_index(drop=True)
        for cat in dim_product["category"].unique()
    }
    members_by_city: dict[str, np.ndarray] = {
        city: dim_member.loc[dim_member["home_city"] == city, "member_id"].to_numpy()
        for city in dim_member["home_city"].unique()
    }
    member_tier = dim_member.set_index("member_id")["loyalty_tier"].to_dict()
    all_member_ids = dim_member["member_id"].to_numpy()

    date_meta = dim_date.set_index(dim_date["date"].dt.date)[["is_weekend", "season", "is_holiday", "holiday_name"]]

    rows: list[dict] = []
    receipt_counter = 0

    for _, store in dim_store.iterrows():
        store_id = store["store_id"]
        store_open = store["opening_date"].date()
        base_receipts = store["_base_receipts"]
        local_members = members_by_city.get(store["city"], all_member_ids)

        for date in pd.date_range(DATE_START, DATE_END, freq="D"):
            pydate = date.date()
            if pydate < store_open:
                continue
            meta = date_meta.loc[pydate]
            is_weekend = bool(meta["is_weekend"])
            season = str(meta["season"])
            is_holiday = bool(meta["is_holiday"])
            holiday_name = str(meta["holiday_name"])

            multiplier = 1.0
            dow = date.dayofweek  # 0=Mon .. 6=Sun
            if dow == 5:  # Saturday
                multiplier *= 1.30
            elif dow == 6:  # Sunday
                multiplier *= 0.80
            else:
                multiplier *= 0.95

            if is_holiday:
                multiplier *= 1.55 if holiday_name == "Grunnlovsdag" else 0.45

            # mild multi-year growth trend
            days_since_start = (pydate - DATE_START).days
            multiplier *= 1.0 + 0.00012 * days_since_start

            expected_receipts = base_receipts * multiplier
            n_receipts = int(rng.poisson(max(expected_receipts, 1)))
            if n_receipts == 0:
                continue

            cat_weights = _season_category_weights(season)
            cats = list(cat_weights.keys())
            cat_probs = list(cat_weights.values())

            hours = rng.choice(HOURS, size=n_receipts, p=HOUR_WEIGHTS)
            has_member = rng.random(n_receipts) < 0.46

            for i in range(n_receipts):
                receipt_counter += 1
                receipt_id = f"R{receipt_counter:08d}"
                hour = int(hours[i])

                member_id = None
                tier = "None"
                if has_member[i] and len(local_members) > 0:
                    member_id = str(rng.choice(local_members))
                    tier = member_tier.get(member_id, "None")

                n_items = _basket_size(tier, is_weekend)
                has_drink = False
                has_food = False

                for _item in range(n_items):
                    # Cross-sell nudge: once a drink is in the basket, food
                    # becomes more likely (stronger for Gold members).
                    local_probs = cat_probs.copy()
                    if has_drink and not has_food:
                        food_idx = cats.index("Food")
                        boost = 0.35 if tier == "Gold" else (0.20 if tier == "Silver" else 0.10)
                        local_probs = [p * (1 - boost) for p in local_probs]
                        local_probs[food_idx] += boost * sum(cat_probs)
                        s = sum(local_probs)
                        local_probs = [p / s for p in local_probs]

                    category = rng.choice(cats, p=local_probs)
                    cat_products = products_by_cat[category]
                    product = cat_products.iloc[rng.integers(0, len(cat_products))]

                    if category in DRINK_CATEGORIES:
                        has_drink = True
                    if category == "Food":
                        has_food = True

                    quantity = 1 if rng.random() < 0.88 else 2
                    unit_price = float(product["unit_price"])

                    discount = 0.0
                    discount_roll = rng.random()
                    if tier == "Gold" and discount_roll < 0.15:
                        discount = round(rng.uniform(5, 20), 1)
                    elif tier == "Silver" and discount_roll < 0.08:
                        discount = round(rng.uniform(5, 15), 1)
                    elif tier == "None" and discount_roll < 0.02:
                        discount = round(rng.uniform(5, 10), 1)
                    discount = min(discount, unit_price * quantity - 1)

                    rows.append(
                        {
                            "sale_id": f"S{len(rows) + 1:09d}",
                            "receipt_id": receipt_id,
                            "date": date,
                            "hour": hour,
                            "store_id": store_id,
                            "product_id": product["product_id"],
                            "member_id": member_id,
                            "quantity": quantity,
                            "unit_price": unit_price,
                            "discount": round(discount, 1),
                        }
                    )

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dim_store = build_dim_store()
    dim_product = build_dim_product()
    dim_date = build_dim_date(DATE_START, DATE_END)
    dim_member = build_dim_member(dim_store)

    print("Generating fact_sales (this can take a minute)...")
    fact_sales = generate_fact_sales(dim_store, dim_product, dim_member, dim_date)

    dim_store_out = dim_store.drop(columns=["_base_receipts"])

    dim_store_out.to_parquet(OUT_DIR / "dim_store.parquet", index=False)
    dim_product.to_parquet(OUT_DIR / "dim_product.parquet", index=False)
    dim_date.to_parquet(OUT_DIR / "dim_date.parquet", index=False)
    dim_member.to_parquet(OUT_DIR / "dim_member.parquet", index=False)
    fact_sales.to_parquet(OUT_DIR / "fact_sales.parquet", index=False)

    print(f"dim_store:   {len(dim_store_out):>8,} rows")
    print(f"dim_product: {len(dim_product):>8,} rows")
    print(f"dim_date:    {len(dim_date):>8,} rows")
    print(f"dim_member:  {len(dim_member):>8,} rows")
    print(f"fact_sales:  {len(fact_sales):>8,} rows")


if __name__ == "__main__":
    main()
