# Filtering Graph Traversals

All traversal methods (`ancestors()`, `descendants()`, `clan()`, `path()`, `connected_graph()`, and their variants) accept filtering parameters that control which parts of the graph are explored. These filters operate at the CTE level — excluded edges are never traversed, not just hidden from results.

## Limiting depth with `max_depth`

Every traversal method accepts `max_depth` to cap how many levels deep the CTE recurses. The project-wide default is 20 (configurable via `DJANGO_POSTGRESQL_DAG_MAX_DEPTH` in your Django settings).

```python
# Only immediate children
>>> root.descendants(max_depth=1)
<QuerySet [<NetworkNode: a1>, <NetworkNode: a2>, <NetworkNode: a3>]>

# Children and grandchildren
>>> root.descendants(max_depth=2)
<QuerySet [<NetworkNode: a1>, <NetworkNode: a2>, <NetworkNode: a3>, <NetworkNode: b1>, <NetworkNode: b2>, <NetworkNode: b3>, <NetworkNode: b4>]>

# Path search fails if the target is beyond max_depth
>>> root.path(c1, max_depth=2)
# Raises NodeNotReachableException (c1 is 3 levels deep)
```

## Filtering by edge type with `edge_type`

If your edge model has a ForeignKey to a categorization model, `edge_type` provides a shorthand for restricting traversal to edges matching that FK value. This is equivalent to the longer `limiting_edges_set_fk` parameter.

First, set up an edge model with a ForeignKey:

```python
from django.db import models
from django_postgresql_dag.models import edge_factory, node_factory

class EdgeCategory(models.Model):
    name = models.CharField(max_length=100)

class MyEdge(edge_factory("MyNode", concrete=False)):
    category = models.ForeignKey(
        EdgeCategory, null=True, blank=True, on_delete=models.CASCADE
    )

class MyNode(node_factory(MyEdge)):
    name = models.CharField(max_length=100)
```

Then filter traversals by category:

```python
>>> reports_to = EdgeCategory.objects.get(name="reports_to")

# Only follow "reports_to" edges
>>> node.descendants(edge_type=reports_to)

# This is equivalent to:
>>> node.descendants(limiting_edges_set_fk=reports_to)
```

`edge_type` works with all traversal and predicate methods: `ancestors()`, `descendants()`, `clan()`, `path()`, `connected_graph()`, `is_ancestor_of()`, `is_descendant_of()`, `path_exists()`, and `distance()`.

## Excluding edges with `disallowed_edges_queryset`

Pass a queryset of edge instances to exclude from traversal. The CTE will skip these edges entirely, as if they don't exist.

```python
# Exclude deprecated edges
>>> bad_edges = MyEdge.objects.filter(deprecated=True)
>>> node.descendants(disallowed_edges_queryset=bad_edges)

# Exclude a specific edge
>>> edge_to_skip = MyEdge.objects.filter(pk=42)
>>> node.path(target, disallowed_edges_queryset=edge_to_skip)
```

This is useful for "what if" scenarios — exploring the graph as it would look with certain connections removed, without actually deleting them.

## Restricting to specific edges with `allowed_edges_queryset`

The inverse of `disallowed_edges_queryset`: only the edges in this queryset will be traversed. All other edges are ignored.

```python
# Only traverse approved edges
>>> approved = MyEdge.objects.filter(approved=True)
>>> node.ancestors(allowed_edges_queryset=approved)

# Only traverse edges in a specific edge set
>>> edge_set = EdgeSet.objects.get(name="production")
>>> relevant_edges = MyEdge.objects.filter(edge_set=edge_set)
>>> node.clan(allowed_edges_queryset=relevant_edges)
```

## Combining filters

Filters can be combined. For example, you can restrict to a specific edge type *and* limit depth:

```python
>>> node.descendants(edge_type=reports_to, max_depth=3)
```

Or restrict to allowed edges with a depth limit:

```python
>>> node.ancestors(allowed_edges_queryset=approved, max_depth=5)
```

For the complete list of methods that accept these parameters, see the [Node API Reference](node-reference.md) and [Edge API Reference](edge-reference.md).
