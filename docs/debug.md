# Debugging DAG Queries

django-postgresql-dag builds complex recursive CTEs for graph traversal, but by default the generated SQL is invisible. The `log_queries` context manager lets you inspect the CTE SQL on demand, with zero overhead when not in use.

## Basic Usage

```python
from django_postgresql_dag.debug import log_queries

with log_queries() as log:
    descendants = node.descendants()
    path = node.path(other_node)

for q in log.queries:
    print(q["query_class"])  # e.g. "DescendantQuery", "DownwardPathQuery"
    print(q["sql"])          # Full CTE SQL
    print(q["params"])       # Parameter dict
```

## Quick Shell Debugging

Pass `print_queries=True` to automatically print all captured queries when the context exits:

```python
with log_queries(print_queries=True):
    node.descendants()
```

## Capturing Executed Queries

To also capture the actual queries executed by Django (with timing data), use `capture_executed=True`. This wraps Django's `CaptureQueriesContext` internally:

```python
with log_queries(capture_executed=True) as log:
    node.descendants()

for e in log.executed:
    print(f"{e['time']}s: {e['sql'][:100]}")
```

## Decorator Form

`log_queries` also works as a decorator:

```python
@log_queries(print_queries=True)
def debug_my_operation():
    node.descendants()
    node.ancestors()
```

## What Gets Captured

The following operations are captured when called inside a `log_queries` block:

- `ancestors()` / `ancestors_raw()` — records `AncestorQuery`
- `descendants()` / `descendants_raw()` — records `DescendantQuery`
- `path()` / `path_raw()` — records `DownwardPathQuery` and/or `UpwardPathQuery`
- `connected_graph()` / `connected_graph_raw()` — records `ConnectedGraphQuery`
- `node_depth()` — records `node_depth`

## `DAGQueryLog` Reference

The object returned by `log_queries().__enter__()` is a `DAGQueryLog` instance with:

- **`queries`** (`list[dict]`): Each entry has:
  - `query_class` (str): The query builder class name (e.g. `"DescendantQuery"`) or `"node_depth"`
  - `sql` (str): The formatted CTE SQL template
  - `params` (dict): The parameters passed to the query
- **`executed`** (`list[dict]`): Only populated when `capture_executed=True`. Each entry has:
  - `sql` (str): The actual SQL executed by Django
  - `time` (str): Execution time in seconds
