# Performance & Efficiency Roadmap

This document maps the option space for making `django-postgresql-dag` faster, with
honest trade-offs and a recommended sequence. It exists so we can pick up any of these
ideas later without re-deriving the analysis.

## The key fact that frames everything

This library is a thin Python shell that formats SQL strings and hands recursive CTEs to
PostgreSQL. Every traversal (`ancestors()`, `descendants()`, `path()`, `connected_graph()`,
the graph-wide manager methods) is computed entirely inside Postgres. The Python side does
three cheap things: format a query template, call `.raw()` / a cursor, and marshal result
rows.

Consequence: **Python is not on the hot path; the database is.** Rewriting the Python layer
in C/C++/Rust would speed up almost nothing. Native code only pays off at one specific layer
(traversal inside the database), and cheaper SQL/schema wins usually dominate. The roadmap
below is ordered accordingly.

## Distribution constraint

The library installs with `pip install` + `migrate` and must keep working on managed
Postgres (AWS RDS, Cloud SQL, Heroku, Supabase, Azure), where users cannot install arbitrary
extensions. Decision (2026-06-13): **the pure-SQL path stays the default/fallback for
everyone; native code is only ever an optional opt-in fast path** for users who control their
database.

## Tier 1 - SQL & schema (pip-only, default path, biggest wins)

Ships to every user with a migration. No native code. Works everywhere.

### 1.1 Composite / covering indexes on the edge table
The edge model only has Django's auto single-column FK indexes on `parent_id` and `child_id`.
The recursive CTEs join on these columns every iteration. Adding `(parent_id, child_id)` and
`(child_id, parent_id)` lets the planner use composite indexes for the CTE self-joins (a true
index-only scan is plan- and visibility-map-dependent, not guaranteed). The win is
workload-dependent and should be measured with `EXPLAIN (ANALYZE, BUFFERS)` rather than assumed.
The composites are shipped additively over the existing single-column FK indexes, so they carry
a real write cost (more indexes maintained per edge insert); see the Edge Reference for the
`db_index=False` opt-in. Lowest-hanging fruit.

### 1.2 Materialized transitive-closure table
The classic read-optimization for DAGs: maintain an `(ancestor, descendant, depth)` table,
updated incrementally via the existing `post_edge_create` / `post_edge_delete` signals.
`ancestors()` / `descendants()` collapse from a recursive traversal into a single indexed
lookup. This is the biggest architectural lever for read-heavy, deep graphs and the thing
that actually holds up at millions of nodes. Cost: write amplification (one edge insert can
fan out to many closure rows), storage, and invalidation logic - so it ships as an opt-in
mixin, not a default.

### 1.3 Query-shape tuning  *(future)*
Several CTEs carry an `ARRAY path` column and test `x <> ALL(path)` per row (O(path length)
per node) for cycle-safety. A DAG has no cycles by definition, so for `ancestors()` /
`descendants()` a plain `UNION` visited-set is sufficient; path arrays are only genuinely
needed for path-enumeration queries. Postgres 14+ native `CYCLE` and `SEARCH` clauses can
also replace hand-rolled array tracking. Free and portable, but needs per-query benchmarking
before changing battle-tested SQL.

## Tier 2 - Result marshaling (Python, modest)

### 2.4 PK-only marshaling on the traversal path
Today `ancestors()` runs the CTE, instantiates a full model object per row just to read
`.pk`, **then** runs a second `filter(pk__in=...)` that builds the same instances again -
two instantiations where one would do. Returning PKs straight from a cursor (no model
instantiation in step one) removes the redundant pass. This is the only place native code in
the Python layer could help, and it is cheaper to simply not build the throwaway objects than
to rewrite anything in Rust.

## Tier 3 - Native Postgres extension (opt-in fast path only)

Default stays pure-SQL; these are for power users who control their DB.

### 3.5 Custom Rust extension via `pgrx`  *(future, gated on benchmarks)*
Native traversal functions (e.g. `dag_descendants(edge_table, start) -> setof bigint`) that
load adjacency into a cache-friendly CSR structure and walk it in compiled code, avoiding
per-iteration SQL/planner overhead. For very large/deep graphs this can dominate CTEs.
`pgrx` (Rust) is the modern path; raw C is more pain for no advantage. Cost: build toolchain,
a binary per Postgres major version, deployment friction. **Do not build this until a
benchmark proves the CTE ceiling is actually being hit** - otherwise it is effort at the
wrong layer.

### 3.6 Lean on existing allowlisted extensions  *(future)*
`pgRouting` (battle-tested C, Dijkstra/path algorithms) could back weighted-path and
all-paths queries; it is on several managed-Postgres allowlists. `Apache AGE` is the heavier
"graph database inside Postgres" option but changes the storage model - more a different
library than a fast path.

## Tier 4 - Out-of-database (different architecture, name-only)

### 4.7 In-process graph mirror  *(probably out of scope)*
Load the edge list into a resident `rustworkx` / `petgraph` graph (optionally via PyO3) and
answer repeated traversals in-memory. Blazing fast, but consistency/staleness and memory turn
it into a cache-server design - a different product than a Django app library.

## Recommended sequence

1. **Benchmark harness (prerequisite).** There is currently no way to know which operation is
   slow at which graph size. A reproducible harness (graph generators varying size / depth /
   fan-out + timing across operations) should exist before Tier 3+ is even considered. Every
   option above is a guess until measured.
2. **Tier 1.1 (indexes) + Tier 2.4 (PK-only marshaling).** Small, safe, universal wins.
3. **Tier 1.2 (opt-in closure table).** The headline scale feature.
4. **Tier 1.3 (query-shape tuning).** Once the harness can prove a change is a win.
5. **Tier 3 (`pgrx`)** only after benchmarks prove CTEs are the bottleneck.

## Status

| ID  | Item                              | Tier | Status             |
|-----|-----------------------------------|------|--------------------|
| 1.1 | Composite/covering edge indexes   | 1    | Plan written       |
| 1.2 | Materialized closure table        | 1    | Deferred (no spec) |
| 1.3 | Query-shape tuning                | 1    | Idea               |
| 2.4 | PK-only marshaling                | 2    | Plan written       |
| 3.5 | `pgrx` Rust extension             | 3    | Idea               |
| 3.6 | pgRouting / Apache AGE            | 3    | Idea               |
| 4.7 | In-process graph mirror           | 4    | Idea               |

Plans live in `docs/superpowers/plans/`. Items 1.1 and 2.4 are covered by
`docs/superpowers/plans/2026-06-13-performance-phase-1-indexes-and-marshaling.md`.
