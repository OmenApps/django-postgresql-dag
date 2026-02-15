# Working with Paths and Algorithms

Beyond basic ancestor/descendant traversal, django-postgresql-dag provides several graph algorithms — all implemented as PostgreSQL recursive CTEs or using the NetworkX library.

The examples on this page use the graph from the [Quickstart](quickstart.md):

```text
root → a1 → b1
     → a1 → b2
     → a2 → b2
     → a3 → b3 → c1
              → c2
          → b4 → c1
```

## Shortest path

`path()` finds the shortest path between two nodes. By default it searches downward (root toward leaf):

```python
>>> root.path(c1)
<QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: c1>]>

>>> root.distance(c1)
3
```

To search upward (or in both directions), set `directional=False`:

```python
>>> c1.path(root, directional=False)
<QuerySet [<NetworkNode: c1>, <NetworkNode: b3>, <NetworkNode: a3>, <NetworkNode: root>]>
```

Use `path_exists()` to check reachability without fetching the full path:

```python
>>> root.path_exists(c1)
True
>>> c1.path_exists(root)
False
>>> c1.path_exists(root, directional=False)
True
```

## All paths

`path()` returns only the shortest path. When you need every possible route between two nodes, use `all_paths()`:

```python
>>> paths = root.all_paths(c1)
>>> for p in paths:
...     print([str(n) for n in p])
['root', 'a3', 'b3', 'c1']
['root', 'a3', 'b4', 'c1']
```

For lightweight processing, `all_paths_as_pk_lists()` returns lists of primary keys instead of full querysets:

```python
>>> root.all_paths_as_pk_lists(c1)
[[1, 4, 7, 9], [1, 4, 8, 9]]
```

Use `max_results` to cap the number of paths returned — useful in dense graphs:

```python
>>> root.all_paths(c1, max_results=1)
```

## Weighted shortest path

If your edge model has a numeric weight field, you can find the minimum-weight path instead of the shortest-hop path.

Your edge model needs a weight field:

```python
class NetworkEdge(edge_factory("NetworkNode", concrete=False)):
    name = models.CharField(max_length=100)
    weight = models.FloatField(default=1.0)
    # ...
```

Then query the weighted shortest path:

```python
>>> path_qs, total_weight = node.weighted_path(target)
>>> print(total_weight)
4.5
>>> print(list(path_qs))
[<NetworkNode: root>, <NetworkNode: a1>, <NetworkNode: b2>]
```

`weighted_distance()` returns just the total weight:

```python
>>> node.weighted_distance(target)
4.5
```

By default the weight field is named `"weight"`. If yours is named differently, pass `weight_field="cost"` (or whatever the field name is).

## Topological sort

Topological ordering arranges nodes so that every parent appears before its children. This is useful for scheduling, dependency resolution, and build ordering.

At the manager level, sort all nodes in the graph:

```python
>>> NetworkNode.objects.topological_sort()
<QuerySet [<NetworkNode: root>, <NetworkNode: a1>, <NetworkNode: a2>, ...]>
```

At the instance level, get a node and its descendants in topological order:

```python
>>> a3.topological_descendants()
<QuerySet [<NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: b4>, <NetworkNode: c1>, <NetworkNode: c2>]>
```

## Critical path

The critical path is the longest weighted path from any root to any leaf in the DAG. This is useful for project scheduling — the critical path determines the minimum total duration.

```python
>>> path_qs, total_weight = NetworkNode.objects.critical_path(weight_field="weight")
>>> print(total_weight)
12.0
>>> print(list(path_qs))
[<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: c1>]
```

Without `weight_field`, each edge counts as 1 (hop count):

```python
>>> path_qs, total = NetworkNode.objects.critical_path()
>>> print(total)
3
```

## Lowest common ancestor

The lowest common ancestor (LCA) of two nodes is the deepest node that is an ancestor of both. In a DAG, there can be multiple LCAs (unlike in a tree).

```python
>>> b1.lowest_common_ancestors(b3)
<QuerySet [<NetworkNode: root>]>
```

Returns an empty QuerySet if the nodes are in disconnected components.

## Depth annotation

Annotate nodes with their distance from the current node:

```python
# Each tuple is (node, depth)
>>> root.descendants_with_depth()
[(<NetworkNode: a1>, 1), (<NetworkNode: a2>, 1), (<NetworkNode: b1>, 2), ...]

>>> c1.ancestors_with_depth()
[(<NetworkNode: b3>, 1), (<NetworkNode: b4>, 1), (<NetworkNode: a3>, 2), (<NetworkNode: root>, 3)]
```

`node_depth()` returns a single node's depth from its furthest root:

```python
>>> root.node_depth()
0
>>> c1.node_depth()
3
```

## Transitive reduction

Transitive reduction removes redundant edges. An edge A → C is redundant if C is already reachable from A through other paths (of length >= 2).

Dry run — find redundant edges without removing them:

```python
>>> NetworkNode.objects.transitive_reduction()
<QuerySet [...]>  # redundant edges

# Also available on the edge manager
>>> NetworkEdge.objects.redundant_edges()
<QuerySet [...]>
```

Delete redundant edges:

```python
>>> count = NetworkNode.objects.transitive_reduction(delete=True)
>>> print(count)
2
```

## Graph hashing

Graph hashing computes a structural fingerprint of a subgraph using the Weisfeiler-Lehman algorithm (via NetworkX). Useful for caching, change detection, and quick isomorphism checks.

```python
>>> node.graph_hash(scope="connected")
'a1b2c3d4e5f6...'

>>> node.graph_hash(scope="descendants")
'f6e5d4c3b2a1...'
```

Scope options: `"connected"`, `"descendants"`, `"ancestors"`, `"clan"`.

For per-node subgraph hashes:

```python
>>> node.subgraph_hashes(scope="connected")
{1: ['abc123...', 'def456...'], 2: ['ghi789...', ...], ...}
```

To compare two subgraphs:

```python
>>> from django_postgresql_dag.transformations import graphs_are_isomorphic
>>> graphs_are_isomorphic(node_a.clan(), node_b.clan())
True
```

Note: WL hashing is not collision-free. Hash equality is necessary but not sufficient for true isomorphism.

## Connected components

Find all disconnected subgraphs in the graph:

```python
>>> components = NetworkNode.objects.connected_components()
>>> len(components)
2  # two disconnected subgraphs
>>> components[0]
<QuerySet [<NetworkNode: root>, <NetworkNode: a1>, ...]>
```

## Graph statistics

Get aggregate metrics for the entire graph:

```python
>>> NetworkNode.objects.graph_stats()
{
    'node_count': 10,
    'edge_count': 11,
    'root_count': 1,
    'leaf_count': 3,
    'island_count': 0,
    'max_depth': 3,
    'avg_depth': 1.5,
    'density': 0.12,
    'component_count': 1,
}
```

Note: this calls `node_depth()` per node, so it runs O(N) queries. Suitable for analytics dashboards, not hot paths.

For the complete method signatures, see the [Node API Reference](node-reference.md) and [Edge API Reference](edge-reference.md).
