# Fjord Roast — Conversational Analytics (Fabric-in-a-box, native Python)

A local, dependency-light prototype that proves out a conversational
analytics architecture without Microsoft Fabric: a user asks a question in
natural language about a coffee-shop chain's sales, the system grounds it in
a **file-defined semantic model**, compiles it to SQL, executes it against
local Parquet with DuckDB, and emits a single self-contained **interactive
HTML dashboard**.

The point of the prototype is the architecture, not the domain — but the
domain is *Fjord Roast*, a fictional Norwegian coffee-shop chain with six
cafés across Tromsø, Bergen, Oslo, and Trondheim.

## Non-negotiable design rule

**The LLM produces structure only — a logical query and chart encodings —
never numbers and never raw SQL.** Numbers come solely from DuckDB executing
SQL that the query-builder compiled centrally from the semantic model. Every
Vega-Lite spec is schema-validated and field-whitelisted before it's allowed
near the data. This is what makes the output trustworthy, and it's the same
separation Fabric's data-agent architecture is built on.

## Architecture

```
question ──▶ [semantic model grounding] ──▶ Claude ──▶ LogicalQuery (JSON, structural only)
                                                            │
                                              validate against semantic model
                                              (one repair round-trip, else abort)
                                                            │
                                                 compile ──▶ DuckDB SQL
                                                            │
                                                    execute on Parquet
                                                            │
                                                       pandas DataFrame
                                                            │
                       (question, columns, 5 sample rows) ─┴──▶ Claude ──▶ Vega-Lite spec(s)
                                                            │
                                    jsonschema + field-whitelist validate
                                    (one repair round-trip, else table fallback)
                                                            │
                                          Jinja2 assembles dashboard.html
                                          (vega/vega-lite/vega-embed via CDN,
                                           data inlined, narrative caption)
                                                            │
                                    persisted to SQLite: {question, logical_query,
                                    sql, vega_spec, model_version, created_at}
```

`refresh <id>` re-runs the **stored logical query** (never the LLM) against
current data and regenerates the HTML — a pinned dashboard is deterministic
and frozen; only the data underneath it can move.

## Repository layout

```sh
conversational-analytics/
├── semantic_model/          # the single source of business meaning
│   ├── model.yml            # name, description, AI instructions/glossary
│   ├── tables/*.yml         # source, grain, columns, synonyms, hidden_from_ai
│   ├── relationships.yml    # fact_sales <-> dim_* joins
│   ├── metrics/*.yml        # net_revenue, units_sold, basket_count, ...
│   ├── verified_answers.yml # question -> canonical logical query, for trust + regression
│   └── access/row_filters.yml  # named identity -> SQL predicate (RLS analogue)
├── data/                    # generated Parquet (star schema), shipped so it runs offline
├── scripts/generate_data.py # ~2 years of synthetic Fjord Roast POS data
├── fjordroast/
│   ├── duck.py               # DuckDB connection helper
│   ├── semantic/
│   │   ├── schema.py         # Pydantic models mirroring the YAML files
│   │   ├── loader.py         # loads + validates referential integrity
│   │   ├── grounding.py      # compact schema-plus-glossary text block for the LLM
│   │   └── query_builder.py  # LogicalQuery -> DuckDB SQL (metrics expand here, centrally)
│   ├── agent/
│   │   ├── nl_to_query.py    # question -> LogicalQuery (structured output, 1 repair round-trip)
│   │   ├── dashboard_spec.py # (question, columns, sample rows) -> Vega-Lite spec(s)
│   │   └── narrative.py      # short caption for the dashboard header
│   ├── dashboard/
│   │   ├── render.py         # Jinja2 assembly of the self-contained HTML
│   │   ├── templates/        # dashboard.html.j2
│   │   └── schemas/          # pinned Vega-Lite v6 JSON schema (offline validation)
│   ├── store/persistence.py  # SQLite "living dashboard" store
│   └── server.py             # stretch: FastAPI chat + gallery
├── cli.py                    # ask / validate / refresh / serve
├── tests/
└── dashboards/                # generated dashboard.html files + dashboards.db
```

## Setup

From the repo root (this project shares the monorepo's Poetry environment):

```bash
poetry install --with conversational-analytics,conversational-analytics-test
```

The Parquet data under `data/` is already generated and committed, so
`validate` and `refresh` work completely offline. To regenerate it (e.g.
after changing the generator):

```bash
poetry run python conversational-analytics/scripts/generate_data.py
```

`ask` and `serve` call the Anthropic API and need `ANTHROPIC_API_KEY` set (or
any of the other credential sources the SDK resolves automatically).

## CLI

Run these from inside `conversational-analytics/`:

```bash
# Validate the semantic model files — CI / regression entry point, no network needed.
python cli.py validate

# Ask a question in natural language; writes dashboards/<id>.html and opens it.
python cli.py ask "How did cold drink sales trend last summer across cities?"
python cli.py ask "What is revenue by city?" --identity manager_bergen   # row-level access
python cli.py ask "..." --model claude-opus-4-8 --no-open

# Re-materialize a saved dashboard deterministically (re-runs the *logical query*,
# not the LLM) against current data.
python cli.py refresh <id>

# Stretch: a tiny FastAPI chat endpoint + gallery of pinned dashboards.
python cli.py serve --port 8420
```

## Example questions

Four questions, each exercising a different part of the semantic model and
producing a visibly distinct chart:

| Question | Metric(s) | Dimension(s) | Chart |
|---|---|---|---|
| "How did net revenue trend month by month in 2024, and can I brush a date range?" | `net_revenue` | `dim_date.date` (month grain) | Line chart with an interval-selection brush |
| "What is revenue by city?" | `net_revenue` | `dim_store.city` | Bar chart breakdown |
| "How does basket value compare to food attach rate by café?" | `avg_basket_value`, `food_attach_rate` | `dim_store.store_name` | Scatter, one point per café |
| "What are our top products by revenue, and what's total revenue and units sold?" | `net_revenue`, `units_sold` | `dim_product.name` | KPI tile (Vega-Lite aggregate transform over the full result) + top-10 bar chart (window/rank transform), both from one product-grouped query |

`semantic_model/verified_answers.yml` pins four more question → canonical
logical-query pairs for trust/regression testing (`tests/test_verified_answers.py`
compiles and executes all of them offline; a live-API variant, skipped
without `ANTHROPIC_API_KEY`, asserts the real agent reproduces the same
structure).

## Testing

```bash
poetry run python -m pytest conversational-analytics/tests/
```

Everything except the live-API regression test in `test_verified_answers.py`
runs offline against the shipped data — the semantic model loader, the
query-builder's SQL compilation and execution, Vega-Lite spec validation,
the persistence store, and the HTML renderer are all exercised directly or
against a stubbed Anthropic client.

## Fabric-concept mapping

| Fabric concept | This prototype |
|---|---|
| OneLake + Delta tables | DuckDB querying local Parquet files directly |
| Power BI semantic model | `/semantic_model/*.yml` (tables, relationships, metrics) |
| "Prep data for AI" instructions / schema | `model.yml` `ai_instructions` + the compiled grounding block (`fjordroast/semantic/grounding.py`) |
| DAX measures | `metrics/*.yml` — portable measure definitions with a declared SQL expression |
| Fabric data agent (NL → DAX) | The Python agent (NL → structured logical query), `fjordroast/agent/nl_to_query.py` |
| Row-level security | `access/row_filters.yml` — named identity → SQL predicate, injected engine-side |
| Verified answers | `semantic_model/verified_answers.yml` + regression tests |
| Vega-Lite render | Identical — Vega-Lite + vega-embed via CDN, generated not authored |

## Out of scope

Real Delta/OneLake, auth beyond the row-filter demo, multi-user concurrency,
and any React/JS frontend beyond the minimal glue `vegaEmbed(...)` calls
needed to mount each generated spec — HTML output only. Cross-filtering
*between* separately embedded specs on the same dashboard is also out of
scope for this prototype; interactivity (brushing, tooltips) works within
each individual chart, which is itself fully declarative Vega-Lite.
