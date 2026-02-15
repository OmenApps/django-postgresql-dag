# Edge API Reference

Complete reference for all methods available on the Edge manager. For practical examples, see [Filtering Graph Traversals](filtering.md) and [Working with Paths and Algorithms](paths-and-algorithms.md).

## Manager Methods

These are called on `MyEdge.objects`.

**from_nodes_queryset(self, nodes_queryset)**
: Given a QuerySet of nodes, returns a QuerySet of all edges where both parent and child are in the provided nodes.

**descendants(self, node, \*\*kwargs)**
: Returns a QuerySet of all edges descended from the given node.

**ancestors(self, node, \*\*kwargs)**
: Returns a QuerySet of all edges which are ancestors of the given node.

**clan(self, node, \*\*kwargs)**
: Returns a QuerySet of all edges for ancestors, self, and descendants of the given node.

**path(self, start_node, end_node, \*\*kwargs)**
: Returns a QuerySet of edges forming the shortest path from `start_node` to `end_node`. Accepts `directional` (default `True`).

**redundant_edges(self)**
: Returns a QuerySet of redundant edges — those removable by transitive reduction. An edge A→C is redundant if C is reachable from A via a path of length >= 2.

**transitive_reduction(self, delete=False)**
: Identifies redundant edges. With `delete=True`, removes them and returns the count. See also `NodeManager.transitive_reduction()`.

**validate_route(self, edges, \*\*kwargs)**
: Given an ordered list of edge instances, returns `True` if they form a contiguous route (each edge's child matches the next edge's parent). A single edge or empty list is always valid.

**sort(self, edges, \*\*kwargs)**
: Given a list or set of edge instances, sorts them from root-side to leaf-side using `node_depth()`.

## Inserting a Node into an Edge

**insert_node(self, edge, node, clone_to_rootside=False, clone_to_leafside=False, pre_save=None, post_save=None)**

Inserts a node into an existing edge, splitting it into two new edges. Returns a tuple of `(rootside_edge, leafside_edge)`.

The process:

1. Creates a new edge from the original edge's parent to the inserted node
2. Creates a new edge from the inserted node to the original edge's child
3. Deletes the original edge

After deletion, the original edge instance still exists in memory but not in the database. Run `del edge_instance` to clean up.

### Cloning edge properties

`clone_to_rootside=True` copies the original edge's field values to the new parent-to-inserted-node edge. `clone_to_leafside=True` does the same for the inserted-node-to-child edge.

Cloning fails if a field has `unique=True`. Use `pre_save` to clear or modify unique fields before saving:

```python
def pre_save(new_edge):
    new_edge.name = ""
    return new_edge
```

A `post_save` function can be used to rebuild relationships after the new edges are created.

### Example

Insert node `n2` into the edge between `n1` and `n3`, cloning the original edge's properties to the rootside edge:

```text
Original        Final

n1  o           n1  o
    |                 \
    |                  o n2
    |                 /
n3  o           n3  o
```

```python
from myapp.models import NetworkEdge, NetworkNode

n1 = NetworkNode.objects.create(name="n1")
n2 = NetworkNode.objects.create(name="n2")
n3 = NetworkNode.objects.create(name="n3")

# Connect n3 to n1
n1.add_child(n3)

e1 = NetworkEdge.objects.last()

# Clear the auto-generated `name` field (it's unique)
def pre_save(new_edge):
    new_edge.name = ""
    return new_edge

NetworkEdge.objects.insert_node(e1, n2, clone_to_rootside=True, pre_save=pre_save)
```
