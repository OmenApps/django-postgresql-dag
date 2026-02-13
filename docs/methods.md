# Methods on Node and Edge

*Listed below are the methods that are useful for building/manipulating/querying the graph. We ignore here the methods used only for internal functionality.*

## Node

### Manager Methods

**roots(self, node=None)**

Returns a Queryset of all root nodes (nodes with no parents) in the Node model. If a node instance is specified, returns only the roots for that node.

**leaves(self, node=None)**

Returns a Queryset of all leaf nodes (nodes with no children) in the Node model. If a node instance is specified, returns only the leaves for that node.

**connected_components(self)**

Returns a list of QuerySets, one per disconnected subgraph. Iteratively uses `connected_graph()` to discover all components. Each returned QuerySet is a standard Django QuerySet that can be further filtered.

**graph_stats(self)**

Returns a dict with aggregate graph metrics: `node_count`, `edge_count`, `root_count`, `leaf_count`, `island_count`, `max_depth`, `avg_depth`, `density`, `component_count`. Note: calls `node_depth()` per node, so O(N) queries — suitable for analytics, not hot paths.

### Model Methods

#### Methods used for building/manipulating

**add_child(self, child, \*\*kwargs)**

Provided with a Node instance, attaches that instance as a child to the current Node instance

**remove_child(self, child, delete_node=False)**

Removes the edge connecting this node to child if a child Node instance is provided, otherwise removes the edges connecting to all children. Optionally deletes the child(ren) node(s) as well.

**add_parent(self, parent, \*args, \*\*kwargs)**

Provided with a Node instance, attaches the current instance as a child to the provided Node instance

**remove_parent(self, parent, delete_node=False)**

Removes the edge connecting this node to parent if a parent Node instance is provided, otherwise removes the edges connecting to all parents. Optionally deletes the parent node(s) as well.

#### Methods used for querying

##### The `edge_type` parameter

All traversal and predicate methods (`ancestors`, `descendants`, `clan`, `path`, `connected_graph`, `is_ancestor_of`, `is_descendant_of`, `path_exists`, `distance`, and their variants) accept an optional `edge_type` keyword argument as a shorthand for `limiting_edges_set_fk`. Pass a model instance that has a ForeignKey on the edge model to limit traversal to edges matching that FK.

```python
from django.db import models
from django_postgresql_dag.models import edge_factory, node_factory

# A simple model whose instances categorize edges
class EdgeCategory(models.Model):
    name = models.CharField(max_length=100)

# Edge model with a ForeignKey for categorizing edges
class MyEdge(edge_factory("MyNode", concrete=False)):
    category = models.ForeignKey(EdgeCategory, null=True, blank=True, on_delete=models.CASCADE)

class MyNode(node_factory(MyEdge)):
    name = models.CharField(max_length=100)
```

```python
# Query only edges of a specific category
reports_to = EdgeCategory.objects.get(name="reports_to")
node.descendants(edge_type=reports_to)

# Equivalent to:
node.descendants(limiting_edges_set_fk=reports_to)
```

##### The `disallowed_edges_queryset` and `allowed_edges_queryset` parameters

All traversal methods (`ancestors`, `descendants`, `clan`, `path`, and their variants) accept optional edge-filtering keyword arguments:

- **`disallowed_edges_queryset`**: A queryset of Edge instances to exclude from traversal. The CTE will not traverse these edges, effectively removing them from the graph during the query.
- **`allowed_edges_queryset`**: A queryset of Edge instances to restrict traversal to. Only these edges will be used by the CTE; all other edges are ignored.

```python
# Exclude specific edges from traversal
bad_edges = MyEdge.objects.filter(deprecated=True)
node.descendants(disallowed_edges_queryset=bad_edges)

# Only traverse a specific subset of edges
approved_edges = MyEdge.objects.filter(approved=True)
node.ancestors(allowed_edges_queryset=approved_edges)
```

**ancestors(self, \*\*kwargs)**

Returns a QuerySet of all nodes in connected paths in a rootward direction

**ancestors_count(self)**

Returns an integer number representing the total number of ancestor nodes

**self_and_ancestors(self, \*\*kwargs)**

Returns a QuerySet of all nodes in connected paths in a rootward direction, prepending with self

**ancestors_and_self(self, \*\*kwargs)**

Returns a QuerySet of all nodes in connected paths in a rootward direction, appending with self

**descendants(self, \*\*kwargs)**

Returns a QuerySet of all nodes in connected paths in a leafward direction

**descendants_count(self)**

Returns an integer number representing the total number of descendant nodes

**self_and_descendants(self, \*\*kwargs)**

Returns a QuerySet of all nodes in connected paths in a leafward direction, prepending with self

**descendants_and_self(self, \*\*kwargs)**

Returns a QuerySet of all nodes in connected paths in a leafward direction, appending with self

**clan(self, \*\*kwargs)**

Returns a QuerySet with all ancestors nodes, self, and all descendant nodes

**clan_count(self)**

Returns an integer number representing the total number of clan nodes

**siblings(self)**

Returns a QuerySet of all nodes that share a parent with this node, excluding self

**siblings_count(self)**

Returns count of all nodes that share a parent with this node

**siblings_with_self(self)**

Returns a QuerySet of all nodes that share a parent with this node and self

**partners(self)**

Returns a QuerySet of all nodes that share a child with this node, excluding self

**partners_count(self)**

Returns count of all nodes that share a child with this node

**partners_with_self(self)**

Returns a QuerySet of all nodes that share a child with this node and self

**path_exists(self, ending_node, \*\*kwargs)**

Given an ending Node instance, returns a boolean value determining whether there is a path from the current Node instance to the ending Node instance

Optional keyword argument: directional (boolean: if True, path searching operates normally, in a leafward only direction. If False, search operates in both directions)

**path(self, ending_node, \*\*kwargs)**

Returns a QuerySet of the shortest path from self to ending node, optionally in either direction. The resulting Queryset is sorted from root-side, toward leaf-side, regardless of the relative position of starting and ending nodes.

Optional keyword argument: directional (boolean: if True, path searching operates normally, in a leafward only direction. If False, search operates in both directions)

**distance(self, ending_node, \*\*kwargs)**

Returns the shortest hops count to the target node

**is_root(self)**

Returns True if the current Node instance has children, but no parents

**is_leaf(self)**

Returns True if the current Node instance has parents, but no children

**is_island(self)**

Returns True if the current Node instance has no parents nor children

**is_ancestor_of(self, ending_node, \*\*kwargs)**

Provided an ending_node Node instance, returns True if the current Node instance and is an ancestor of the provided Node instance

Optional keyword argument: directional (boolean: if True, path searching operates normally, in a leafward only direction. If False, search operates in both directions)

**is_descendant_of(self, ending_node, \*\*kwargs)**

Provided an ending_node Node instance, returns True if the current Node instance and is a descendant of the provided Node instance

Optional keyword argument: directional (boolean: if True, path searching operates normally, in a leafward only direction. If False, search operates in both directions)

**is_sibling_of(self, ending_node)**

Provided an ending_node Node instance, returns True if the provided Node instance and the current Node instance share a parent Node

**is_partner_of(self, ending_node)**

Provided an ending_node Node instance, returns True if the provided Node instance and the current Node instance share a child Node

**node_depth(self)**

Returns an integer representing the depth of this Node instance from furthest root. Uses a recursive CTE to find the longest path to any root node. Returns 0 for root nodes and island nodes.

**connected_graph(self, \*\*kwargs)**

Returns a QuerySet of all nodes connected in any way to the current Node instance

**connected_graph_node_count(self, \*\*kwargs)**

Returns the number of nodes in the graph connected in any way to the current Node instance

**descendants_tree(self)**

Returns a tree-like structure with descendants for the current Node

**ancestors_tree(self)**

Returns a tree-like structure with ancestors for the current Node

**roots(self)**

Returns a QuerySet of all root nodes, if any, for the current Node

**leaves(self)**

Returns a QuerySet of all leaf nodes, if any, for the current Node

**descendants_edges(self)**

Returns a QuerySet of descendant Edge instances for the current Node, topologically sorted from root-side to leaf-side.

**ancestors_edges(self)**

Returns a QuerySet of ancestor Edge instances for the current Node, topologically sorted from root-side to leaf-side.

**clan_edges(self)**

Returns a QuerySet of all Edge instances associated with a given node

## Edge

### Manager Methods

**from_nodes_queryset(self, nodes_queryset)**

Provided a QuerySet of nodes, returns a QuerySet of all Edge instances where a parent and child Node are within the QuerySet of nodes

**descendants(self, node, \*\*kwargs)**

Returns a QuerySet of all Edge instances descended from the given Node instance

**ancestors(self, node, \*\*kwargs)**

Returns a QuerySet of all Edge instances which are ancestors of the given Node instance

**clan(self, node, \*\*kwargs)**

Returns a QuerySet of all Edge instances for ancestors, self, and descendants

**path(self, start_node, end_node, \*\*kwargs)**

Returns a QuerySet of all Edge instances for the shortest path from start_node to end_node

**validate_route(self, edges, \*\*kwargs)**

Given an ordered list of Edge instances, verify that they result in a contiguous route. Returns `True` if each edge's child matches the next edge's parent, `False` otherwise. A single edge or empty list is always valid.

**sort(self, edges, \*\*kwargs)**

Given a list or set of Edge instances, sort them from root-side to leaf-side. Uses `node_depth()` to determine topological position and returns a sorted list.

**insert_node(self, edge, node, clone_to_rootside=False, clone_to_leafside=False, pre_save=None, post_save=None)**

Inserts a node into an existing Edge instance. Returns a tuple of the newly created rootside_edge (parent to the inserted node) and leafside_edge (child to the inserted node).

Process:

1. Add a new Edge from the parent Node of the current Edge instance to the provided Node instance, optionally cloning properties of the existing Edge.
2. Add a new Edge from the provided Node instance to the child Node of the current Edge instance, optionally cloning properties of the existing Edge.
3. Remove the original Edge instance.

The instance will still exist in memory, though not in database (https://docs.djangoproject.com/en/3.1/ref/models/instances/#refreshing-objects-from-database). Recommend running the following after conducting the deletion:
    del instancename

Cloning will fail if a field has unique=True, so a pre_save function can be passed into this method. Likewise, a post_save function can be passed in to rebuild relationships. For instance, if you have a `name` field that is unique and generated automatically in the model's save() method, you could pass in a the following `pre_save` function to clear the name prior to saving the new Edge instance(s):

```python
def pre_save(new_edge):
    new_edge.name = ""
    return new_edge
```

A more complete example, where we have models named NetworkEdge & NetworkNode, and we want to insert a new Node (n2) into Edge e1, while copying e1's field properties (except `name`) to the newly created rootside Edge instance (n1 to n2) is shown below.

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

# function to clear the `name` field, which is autogenerated and must be unique
def pre_save(new_edge):
    new_edge.name = ""
    return new_edge

NetworkEdge.objects.insert_node(e1, n2, clone_to_rootside=True, pre_save=pre_save)
```
