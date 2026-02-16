# Debugging DAG Queries

django-postgresql-dag builds recursive CTEs for graph traversal, and by default the generated SQL is invisible. The `log_queries` context manager lets you inspect the CTE SQL on demand, with zero overhead when not in use.

## Basic usage

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

## Quick shell debugging

Pass `print_queries=True` to print all captured queries when the context exits:

```python
with log_queries(print_queries=True):
    node.descendants()
```

## Capturing executed queries

To capture the actual queries executed by Django (with timing data), use `capture_executed=True`. This wraps Django's `CaptureQueriesContext` internally:

```python
with log_queries(capture_executed=True) as log:
    node.descendants()

for e in log.executed:
    print(f"{e['time']}s: {e['sql'][:100]}")
```

## Decorator form

`log_queries` also works as a decorator:

```python
@log_queries(print_queries=True)
def debug_my_operation():
    node.descendants()
    node.ancestors()
```

## What gets captured

These operations are captured when called inside a `log_queries` block:

- `ancestors()` / `ancestors_raw()` - records `AncestorQuery`
- `descendants()` / `descendants_raw()` - records `DescendantQuery`
- `ancestors_with_depth()` - records `AncestorDepthQuery`
- `descendants_with_depth()` - records `DescendantDepthQuery`
- `path()` / `path_raw()` - records `DownwardPathQuery` and/or `UpwardPathQuery`
- `all_paths()` / `all_paths_as_pk_lists()` - records `AllDownwardPathsQuery` and/or `AllUpwardPathsQuery`
- `weighted_path()` / `weighted_path_raw()` - records `WeightedDownwardPathQuery` and/or `WeightedUpwardPathQuery`
- `connected_graph()` / `connected_graph_raw()` - records `ConnectedGraphQuery`
- `lowest_common_ancestors()` - records `LCAQuery`
- `topological_sort()` - records `TopologicalSortQuery`
- `critical_path()` - records `CriticalPathQuery`
- `transitive_reduction()` - records `TransitiveReductionQuery`
- `node_depth()` - records `node_depth`

## `DAGQueryLog` reference

The object returned by `log_queries().__enter__()` is a `DAGQueryLog` instance with:

- **`queries`** (`list[dict]`) - each entry has:
  - `query_class` (str): the query builder class name (e.g. `"DescendantQuery"`) or `"node_depth"`
  - `sql` (str): the formatted CTE SQL template
  - `params` (dict): the parameters passed to the query
- **`executed`** (`list[dict]`) - only populated when `capture_executed=True`. Each entry has:
  - `sql` (str): the actual SQL executed by Django
  - `time` (str): execution time in seconds
