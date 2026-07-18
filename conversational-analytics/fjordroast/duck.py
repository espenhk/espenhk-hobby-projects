"""DuckDB connection helper — the OneLake/Delta analogue for this prototype.

We query Parquet files directly with `read_parquet(...)`, so a "connection"
here is just an in-memory DuckDB engine; no catalog or persistent database
is needed.
"""

from __future__ import annotations

import duckdb


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(database=":memory:")
